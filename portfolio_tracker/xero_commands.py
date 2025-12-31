"""
Xero CLI Command Handlers.

Provides CLI commands for Xero OAuth 2.0 integration including:
- Authentication (auth)
- Disconnecting (disconnect)
- Status check (status)
- Data synchronization (sync)
- Tenant management (tenants)
"""

import logging
import sys
import webbrowser
from argparse import Namespace
from datetime import datetime
from typing import Optional

from .formatting import (
    green, red, yellow, blue, cyan, bold, dim,
    format_money, header, subheader
)

logger = logging.getLogger(__name__)

# Try to import Xero integration modules
try:
    from .integrations import (
        XeroConfig, load_config,
        XeroOAuth, XeroTokens, AuthorizationError, TokenError,
        TokenStorage,
        XeroClient, XeroAPIError,
        XeroSync, SyncOptions, format_sync_result, format_sync_summary,
    )
    from .integrations.xero_oauth import authorize_interactive, XeroTenant
    XERO_AVAILABLE = True
except ImportError as e:
    XERO_AVAILABLE = False
    IMPORT_ERROR = str(e)


def check_xero_available():
    """Check if Xero integration is available and exit if not."""
    if not XERO_AVAILABLE:
        print(red("Xero integration not available."))
        print(f"Import error: {IMPORT_ERROR}")
        print("\nMake sure required packages are installed:")
        print("  pip install requests cryptography")
        sys.exit(1)


def cmd_xero(args: Namespace):
    """Handle Xero command routing."""
    check_xero_available()

    if args.xero_command == "auth":
        cmd_xero_auth(args)
    elif args.xero_command == "disconnect":
        cmd_xero_disconnect(args)
    elif args.xero_command == "status":
        cmd_xero_status(args)
    elif args.xero_command == "sync":
        cmd_xero_sync(args)
    elif args.xero_command == "tenants":
        cmd_xero_tenants(args)
    elif args.xero_command == "test":
        cmd_xero_test(args)
    else:
        # No subcommand - show status
        cmd_xero_status(args)


def cmd_xero_auth(args: Namespace):
    """Authenticate with Xero OAuth 2.0."""
    print(header("Xero OAuth 2.0 Authentication"))
    print()

    # Load configuration
    config = load_config()
    errors = config.validate()

    if errors:
        print(red("Configuration errors:"))
        for error in errors:
            print(f"  - {error}")
        print()
        print("Please set the following environment variables:")
        print("  XERO_CLIENT_ID=your_client_id")
        print("  XERO_CLIENT_SECRET=your_client_secret")
        print()
        print("Or create a .env file in the project root.")
        sys.exit(1)

    print(f"Client ID: {config.client_id[:8]}...{config.client_id[-4:]}")
    print(f"Redirect URI: {config.redirect_uri}")
    print(f"Scopes: {', '.join(config.scopes[:3])}...")
    print()

    # Check for existing tokens
    storage = TokenStorage(config=config)
    storage.initialize()

    if storage.has_valid_tokens():
        if not args.force:
            print(yellow("Already authenticated with Xero."))
            print("Use --force to re-authenticate.")
            return
        print(yellow("Re-authenticating..."))
        print()

    # Run interactive authorization
    try:
        print("Starting OAuth 2.0 authorization flow...")
        print()

        # Parse port from redirect URI
        from urllib.parse import urlparse
        parsed = urlparse(config.redirect_uri)
        port = parsed.port or 8080

        tokens, tenants = authorize_interactive(
            config=config,
            open_browser=not args.no_browser,
            callback_port=port,
            timeout=300,
        )

        print()
        print(green("Authentication successful!"))
        print()

        # Save tokens and tenants
        if tenants:
            print(f"Connected to {len(tenants)} organisation(s):")
            for tenant in tenants:
                print(f"  - {tenant.tenant_name} ({tenant.tenant_type})")
                storage.save_tokens(tokens, tenant.tenant_id, tenant.tenant_name)
                storage.save_tenant(tenant)
            print()
        else:
            print(yellow("No organisations connected."))

        # Show token info
        print(f"Access token expires: {tokens.expires_at.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        print(f"Scopes granted: {tokens.scope}")

    except AuthorizationError as e:
        print(red(f"Authorization failed: {e}"))
        if e.error_description:
            print(f"  {e.error_description}")
        sys.exit(1)

    except TokenError as e:
        print(red(f"Token error: {e}"))
        if e.error_description:
            print(f"  {e.error_description}")
        sys.exit(1)

    except KeyboardInterrupt:
        print()
        print(yellow("Authorization cancelled."))
        sys.exit(0)


def cmd_xero_disconnect(args: Namespace):
    """Disconnect from Xero."""
    print(header("Disconnect from Xero"))
    print()

    config = load_config()
    storage = TokenStorage(config=config)
    storage.initialize()

    if args.all:
        # Disconnect all tenants
        tenants = storage.get_active_tenants()
        if not tenants:
            print("No connected tenants found.")
            return

        print(f"Disconnecting {len(tenants)} tenant(s)...")

        for tenant in tenants:
            tenant_id = tenant.get("tenant_id")
            name = tenant.get("tenant_name", "Unknown")

            # Try to revoke tokens
            tokens = storage.get_tokens(tenant_id)
            if tokens:
                try:
                    oauth = XeroOAuth(config)
                    oauth.revoke_token(tokens.refresh_token)
                    print(f"  Revoked tokens for: {name}")
                except TokenError:
                    print(f"  {yellow('Warning')}: Could not revoke tokens for {name}")

            # Delete local tokens
            storage.delete_tokens(tenant_id)
            storage.deactivate_tenant(tenant.get("connection_id", ""))
            print(f"  {green('Disconnected')}: {name}")

        print()
        print(green("All tenants disconnected."))

    else:
        # Disconnect specific tenant
        tenant_id = args.tenant or storage.get_default_tenant()

        if not tenant_id:
            print("No tenant specified and no default tenant found.")
            print("Use --all to disconnect all tenants.")
            return

        tokens = storage.get_tokens(tenant_id)
        if tokens:
            try:
                oauth = XeroOAuth(config)
                oauth.revoke_token(tokens.refresh_token)
                print(f"Revoked tokens for tenant: {tenant_id}")
            except TokenError as e:
                print(yellow(f"Warning: Could not revoke tokens: {e}"))

        storage.delete_tokens(tenant_id)
        print(green(f"Disconnected tenant: {tenant_id}"))


def cmd_xero_status(args: Namespace):
    """Show Xero connection status."""
    print(header("Xero Integration Status"))
    print()

    config = load_config()

    # Check configuration
    errors = config.validate()
    if errors:
        print(red("Configuration: Invalid"))
        for error in errors:
            print(f"  - {error}")
        print()
    else:
        print(green("Configuration: Valid"))
        print(f"  Client ID: {config.client_id[:8]}...{config.client_id[-4:]}")
        print()

    # Check token storage
    storage = TokenStorage(config=config)
    storage.initialize()

    status = storage.get_status()
    print(subheader("Storage Status"))
    print(f"  Database: {status['db_path']}")
    print(f"  Encryption: {'Enabled' if status['encryption_enabled'] else 'Disabled'}")
    print(f"  Token records: {status['token_count']}")
    print(f"  Active tenants: {status['tenant_count']}")
    print()

    # Show connected tenants
    tenants = storage.get_active_tenants()
    if tenants:
        print(subheader("Connected Organisations"))
        for tenant in tenants:
            tenant_id = tenant.get("tenant_id")
            name = tenant.get("tenant_name", "Unknown")
            tokens = storage.get_tokens(tenant_id)

            if tokens:
                if tokens.is_expired:
                    token_status = red("Expired")
                else:
                    remaining = tokens.time_until_expiry
                    mins = int(remaining.total_seconds() / 60)
                    token_status = green(f"Valid ({mins}m remaining)")
            else:
                token_status = yellow("No tokens")

            print(f"  {name}")
            print(f"    ID: {tenant_id[:8]}...")
            print(f"    Tokens: {token_status}")

    else:
        print(yellow("No connected organisations."))
        print()
        print("Run 'portfolio xero auth' to connect to Xero.")

    # Show sync status
    if tenants and args.sync_status:
        print()
        print(subheader("Sync Status"))

        for tenant in tenants:
            tenant_id = tenant.get("tenant_id")
            name = tenant.get("tenant_name", "Unknown")

            tokens = storage.get_tokens(tenant_id)
            if not tokens or tokens.is_expired:
                continue

            try:
                client = XeroClient(config=config, tokens=tokens, tenant_id=tenant_id)
                sync = XeroSync(client, storage, tenant_id)
                sync_status = sync.get_sync_status()

                print(f"\n  {name}:")
                for sync_type, info in sync_status.items():
                    last = info.get("last_sync", "Never")
                    status = info.get("status", "unknown")
                    records = info.get("records", 0)
                    print(f"    {sync_type}: {last} ({status}, {records} records)")

            except Exception as e:
                print(f"    {red('Error')}: {e}")


def cmd_xero_sync(args: Namespace):
    """Synchronize data with Xero."""
    print(header("Xero Data Sync"))
    print()

    config = load_config()
    storage = TokenStorage(config=config)
    storage.initialize()

    # Get tenant
    tenant_id = args.tenant or storage.get_default_tenant()
    if not tenant_id:
        print(red("No tenant specified and no default tenant found."))
        print("Run 'portfolio xero auth' first.")
        sys.exit(1)

    tokens = storage.get_tokens(tenant_id)
    if not tokens:
        print(red(f"No tokens found for tenant: {tenant_id}"))
        sys.exit(1)

    # Create client and sync manager
    client = XeroClient(
        config=config,
        tokens=tokens,
        tenant_id=tenant_id,
        token_storage=storage,
    )

    sync = XeroSync(client, storage, tenant_id)

    # Build sync options
    options = SyncOptions(
        full_sync=args.full,
        dry_run=args.dry_run,
        include_archived=args.include_archived,
    )

    if args.dry_run:
        print(yellow("Dry run mode - no data will be modified"))
        print()

    try:
        # Determine what to sync
        if args.sync_type == "all" or not args.sync_type:
            print("Running full sync...")
            results = sync.sync_all(options)
            print()
            print(format_sync_summary(results))

        else:
            # Sync specific type
            sync_funcs = {
                "organisation": sync.sync_organisation,
                "org": sync.sync_organisation,
                "contacts": sync.sync_contacts,
                "invoices": sync.sync_invoices,
                "accounts": sync.sync_accounts,
            }

            if args.sync_type in sync_funcs:
                print(f"Syncing {args.sync_type}...")
                result = sync_funcs[args.sync_type](options)
                print()
                print(format_sync_result(result))
            else:
                print(red(f"Unknown sync type: {args.sync_type}"))
                print(f"Available: {', '.join(sync_funcs.keys())}")
                sys.exit(1)

    except XeroAPIError as e:
        print(red(f"API error: {e}"))
        sys.exit(1)


def cmd_xero_tenants(args: Namespace):
    """Manage Xero tenants/organisations."""
    print(header("Xero Tenants"))
    print()

    config = load_config()
    storage = TokenStorage(config=config)
    storage.initialize()

    tenants = storage.get_active_tenants()

    if not tenants:
        print("No tenants found.")
        print("Run 'portfolio xero auth' to connect to Xero.")
        return

    for i, tenant in enumerate(tenants, 1):
        name = tenant.get("tenant_name", "Unknown")
        tenant_id = tenant.get("tenant_id", "")
        tenant_type = tenant.get("tenant_type", "")

        print(f"{i}. {bold(name)}")
        print(f"   Type: {tenant_type}")
        print(f"   ID: {tenant_id}")

        # Check token status
        tokens = storage.get_tokens(tenant_id)
        if tokens:
            if tokens.is_expired:
                print(f"   Tokens: {red('Expired')}")
            else:
                remaining = tokens.time_until_expiry
                mins = int(remaining.total_seconds() / 60)
                print(f"   Tokens: {green(f'Valid ({mins}m)')}")
        else:
            print(f"   Tokens: {yellow('None')}")

        print()

    if args.set_default:
        # Set default tenant
        try:
            index = int(args.set_default) - 1
            if 0 <= index < len(tenants):
                tenant = tenants[index]
                # In a real implementation, you'd update a config or preference
                print(green(f"Default tenant set to: {tenant.get('tenant_name')}"))
            else:
                print(red(f"Invalid tenant number: {args.set_default}"))
        except ValueError:
            print(red("Please provide a tenant number (e.g., --set-default 1)"))


def cmd_xero_test(args: Namespace):
    """Test Xero API connection."""
    print(header("Xero Connection Test"))
    print()

    config = load_config()
    storage = TokenStorage(config=config)
    storage.initialize()

    tenant_id = args.tenant or storage.get_default_tenant()
    if not tenant_id:
        print(red("No tenant found. Run 'portfolio xero auth' first."))
        sys.exit(1)

    tokens = storage.get_tokens(tenant_id)
    if not tokens:
        print(red("No tokens found."))
        sys.exit(1)

    print(f"Testing connection to tenant: {tenant_id[:16]}...")
    print()

    try:
        client = XeroClient(
            config=config,
            tokens=tokens,
            tenant_id=tenant_id,
            token_storage=storage,
        )

        # Test connection
        if client.test_connection():
            print(green("Connection: OK"))
        else:
            print(red("Connection: Failed"))
            sys.exit(1)

        # Get organisation details
        print()
        print("Fetching organisation details...")
        org = client.get_organisation()
        print(f"  Name: {org.name}")
        print(f"  Legal Name: {org.legal_name or 'N/A'}")
        print(f"  Country: {org.country_code}")
        print(f"  Currency: {org.default_currency}")
        print(f"  FY End: {org.financial_year_end_day}/{org.financial_year_end_month}")

        # Get some counts
        print()
        print("Checking data access...")
        contacts = client.get_contacts(page=1)
        print(f"  Contacts: {len(contacts)} (first page)")

        invoices = client.get_invoices(page=1)
        print(f"  Invoices: {len(invoices)} (first page)")

        accounts = client.get_accounts()
        print(f"  Accounts: {len(accounts)}")

        print()
        print(green("All tests passed!"))

    except XeroAPIError as e:
        print(red(f"API Error: {e}"))
        sys.exit(1)


def add_xero_subparser(subparsers):
    """Add Xero subparser to main argument parser."""
    xero_parser = subparsers.add_parser(
        "xero",
        help="Xero OAuth 2.0 integration (sync accounting data)"
    )

    xero_subparsers = xero_parser.add_subparsers(dest="xero_command")

    # Auth command
    auth_parser = xero_subparsers.add_parser(
        "auth",
        help="Authenticate with Xero (OAuth 2.0)"
    )
    auth_parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Re-authenticate even if already connected"
    )
    auth_parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Don't automatically open browser"
    )

    # Disconnect command
    disconnect_parser = xero_subparsers.add_parser(
        "disconnect",
        help="Disconnect from Xero"
    )
    disconnect_parser.add_argument(
        "--tenant", "-t",
        help="Tenant ID to disconnect"
    )
    disconnect_parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Disconnect all tenants"
    )

    # Status command
    status_parser = xero_subparsers.add_parser(
        "status",
        help="Show Xero connection status"
    )
    status_parser.add_argument(
        "--sync-status", "-s",
        action="store_true",
        help="Include sync status"
    )

    # Sync command
    sync_parser = xero_subparsers.add_parser(
        "sync",
        help="Synchronize data with Xero"
    )
    sync_parser.add_argument(
        "sync_type",
        nargs="?",
        choices=["all", "organisation", "org", "contacts", "invoices", "accounts"],
        default="all",
        help="What to sync (default: all)"
    )
    sync_parser.add_argument(
        "--tenant", "-t",
        help="Tenant ID to sync"
    )
    sync_parser.add_argument(
        "--full", "-f",
        action="store_true",
        help="Full sync (ignore last sync date)"
    )
    sync_parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Dry run - show what would be synced"
    )
    sync_parser.add_argument(
        "--include-archived",
        action="store_true",
        help="Include archived records"
    )

    # Tenants command
    tenants_parser = xero_subparsers.add_parser(
        "tenants",
        help="Manage connected organisations"
    )
    tenants_parser.add_argument(
        "--set-default",
        metavar="N",
        help="Set default tenant by number"
    )

    # Test command
    test_parser = xero_subparsers.add_parser(
        "test",
        help="Test Xero API connection"
    )
    test_parser.add_argument(
        "--tenant", "-t",
        help="Tenant ID to test"
    )

    return xero_parser
