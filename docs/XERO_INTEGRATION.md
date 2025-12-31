# Xero OAuth 2.0 Integration

This document describes the OAuth 2.0 certification-compliant integration with Xero for the Portfolio Tracker application.

## Overview

The integration provides:
- **OAuth 2.0 with PKCE**: Secure authorization flow using Proof Key for Code Exchange
- **Multi-tenant support**: Connect multiple Xero organisations
- **Automatic token refresh**: Seamlessly refresh expired tokens
- **Encrypted token storage**: Optional Fernet encryption for stored tokens
- **Rate limiting**: Respect Xero's API limits (60 calls/minute)
- **CLI and Web interfaces**: Authenticate via command line or web dashboard

## Prerequisites

1. **Xero Developer Account**: Register at [developer.xero.com](https://developer.xero.com)
2. **Xero App**: Create an app at [developer.xero.com/app/manage](https://developer.xero.com/app/manage)
3. **Python packages**: Install required dependencies

```bash
pip install requests cryptography flask
```

## Quick Start

### 1. Create a Xero App

1. Go to [Xero Developer Portal](https://developer.xero.com/app/manage)
2. Click "New App"
3. Choose "Web app" as the app type
4. Set the OAuth 2.0 redirect URI:
   - For CLI: `http://localhost:8080/callback`
   - For Web: `http://localhost:5000/xero/callback`
5. Copy your Client ID and Client Secret

### 2. Configure Environment

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` with your Xero credentials:

```env
XERO_CLIENT_ID=your_client_id
XERO_CLIENT_SECRET=your_client_secret
```

### 3. Authenticate

**Via CLI:**
```bash
python -m portfolio_tracker xero auth
```

**Via Web Dashboard:**
```bash
python -m portfolio_tracker web
# Then visit http://localhost:5000/xero
```

### 4. Test Connection

```bash
python -m portfolio_tracker xero test
```

## CLI Commands

### Authentication

```bash
# Start OAuth flow
python -m portfolio_tracker xero auth

# Re-authenticate (overwrite existing tokens)
python -m portfolio_tracker xero auth --force

# Don't open browser automatically
python -m portfolio_tracker xero auth --no-browser
```

### Status

```bash
# Check connection status
python -m portfolio_tracker xero status

# Include sync status
python -m portfolio_tracker xero status --sync-status
```

### Sync Data

```bash
# Sync all data
python -m portfolio_tracker xero sync

# Sync specific data type
python -m portfolio_tracker xero sync contacts
python -m portfolio_tracker xero sync invoices
python -m portfolio_tracker xero sync accounts

# Full sync (ignore last sync date)
python -m portfolio_tracker xero sync --full

# Dry run (see what would be synced)
python -m portfolio_tracker xero sync --dry-run
```

### Tenants

```bash
# List connected organisations
python -m portfolio_tracker xero tenants

# Set default tenant
python -m portfolio_tracker xero tenants --set-default 1
```

### Disconnect

```bash
# Disconnect specific tenant
python -m portfolio_tracker xero disconnect --tenant TENANT_ID

# Disconnect all tenants
python -m portfolio_tracker xero disconnect --all
```

## Web Dashboard

Access the Xero integration dashboard at:
- `http://localhost:5000/xero`

### API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /xero` | Integration dashboard |
| `GET /xero/auth` | Start OAuth flow |
| `GET /xero/callback` | OAuth callback handler |
| `GET /xero/disconnect` | Disconnect tenant |
| `GET /api/xero/status` | JSON status |
| `GET /api/xero/organisation` | Organisation details |

## OAuth 2.0 Flow

The integration implements the OAuth 2.0 Authorization Code flow with PKCE:

```
1. Generate code_verifier (random 128-char string)
2. Calculate code_challenge = BASE64URL(SHA256(code_verifier))
3. Redirect user to Xero authorization URL with:
   - client_id
   - redirect_uri
   - scope
   - state (CSRF protection)
   - code_challenge
   - code_challenge_method=S256

4. User authorizes the application
5. Xero redirects to callback with authorization code
6. Exchange code for tokens with:
   - authorization_code
   - code_verifier
   - client_id
   - client_secret

7. Receive access_token, refresh_token, id_token
8. Store tokens securely (encrypted)
```

## Available Scopes

| Scope | Description |
|-------|-------------|
| `openid` | OpenID authentication |
| `profile` | User profile information |
| `email` | User email address |
| `offline_access` | Refresh token for long-lived access |
| `accounting.transactions` | Full access to invoices, credit notes, payments |
| `accounting.transactions.read` | Read-only transactions |
| `accounting.contacts` | Full access to contacts |
| `accounting.contacts.read` | Read-only contacts |
| `accounting.settings` | Organisation settings |
| `accounting.settings.read` | Read-only settings |
| `accounting.reports.read` | Financial reports |
| `accounting.journals.read` | Manual journals |
| `assets` | Fixed assets |
| `assets.read` | Read-only assets |
| `projects` | Projects and tasks |
| `projects.read` | Read-only projects |

### Default Scopes

```
openid profile email offline_access
accounting.contacts.read accounting.transactions.read
accounting.reports.read accounting.settings.read
```

## Token Storage

Tokens are stored in a SQLite database with optional encryption.

### Encryption Setup

Generate a Fernet encryption key:

```python
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
```

Add to `.env`:

```env
XERO_TOKEN_ENCRYPTION_KEY=your_generated_key
```

### Database Schema

```sql
-- Token storage
CREATE TABLE xero_tokens (
    id INTEGER PRIMARY KEY,
    tenant_id TEXT UNIQUE NOT NULL,
    tenant_name TEXT,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    token_type TEXT DEFAULT 'Bearer',
    expires_in INTEGER DEFAULT 1800,
    scope TEXT,
    id_token TEXT,
    created_at DATETIME NOT NULL,
    updated_at DATETIME,
    encrypted INTEGER DEFAULT 0
);

-- Tenant information
CREATE TABLE xero_tenants (
    id INTEGER PRIMARY KEY,
    connection_id TEXT UNIQUE NOT NULL,
    tenant_id TEXT NOT NULL,
    tenant_type TEXT,
    tenant_name TEXT,
    is_active INTEGER DEFAULT 1,
    last_sync DATETIME
);

-- Sync history
CREATE TABLE xero_sync_log (
    id INTEGER PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    sync_type TEXT NOT NULL,
    sync_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL,
    records_synced INTEGER DEFAULT 0,
    error_message TEXT,
    details TEXT
);
```

## API Client Usage

### Basic Usage

```python
from portfolio_tracker.integrations import (
    XeroClient, TokenStorage, load_config
)

# Load configuration
config = load_config()

# Get stored tokens
storage = TokenStorage(config=config)
storage.initialize()

tenant_id = storage.get_default_tenant()
tokens = storage.get_tokens(tenant_id)

# Create client
client = XeroClient(
    config=config,
    tokens=tokens,
    tenant_id=tenant_id,
    token_storage=storage  # For automatic token refresh
)

# Make API calls
org = client.get_organisation()
contacts = client.get_contacts()
invoices = client.get_invoices(status="AUTHORISED")
```

### Available Methods

```python
# Organisation
client.get_organisation()

# Contacts
client.get_contacts(status=None, where=None, order=None, page=1)
client.get_contact(contact_id)
client.iter_contacts()  # Paginated iterator

# Invoices
client.get_invoices(status=None, invoice_type=None, page=1)
client.get_invoice(invoice_id)
client.iter_invoices()  # Paginated iterator

# Accounts
client.get_accounts(account_type=None)
client.get_account(account_id)

# Reports
client.get_profit_and_loss(from_date, to_date)
client.get_balance_sheet(report_date)
client.get_trial_balance(report_date)
client.get_bank_summary(from_date, to_date)

# Bank Transactions
client.get_bank_transactions(bank_account_id=None)
```

## Error Handling

```python
from portfolio_tracker.integrations import (
    XeroAPIError, RateLimitError, TokenError, AuthorizationError
)

try:
    contacts = client.get_contacts()
except RateLimitError as e:
    print(f"Rate limited. Retry after {e.retry_after} seconds")
except TokenError as e:
    print(f"Token error: {e}")
    # Re-authenticate
except XeroAPIError as e:
    print(f"API error {e.status_code}: {e}")
```

## Security Considerations

1. **Store credentials securely**: Use environment variables, not hardcoded values
2. **Enable token encryption**: Set `XERO_TOKEN_ENCRYPTION_KEY` in production
3. **Use HTTPS in production**: Xero requires HTTPS for non-localhost redirect URIs
4. **Limit scopes**: Only request scopes you need
5. **Secure the callback endpoint**: Validate state parameter to prevent CSRF

## Xero App Store Certification

This implementation follows Xero's OAuth 2.0 certification requirements:

- [x] Uses PKCE (Proof Key for Code Exchange)
- [x] Implements state parameter for CSRF protection
- [x] Handles token refresh automatically
- [x] Supports multi-tenant connections
- [x] Respects rate limits (60 calls/minute)
- [x] Implements proper error handling
- [x] Provides token revocation
- [x] Uses S256 challenge method (not plain)

## Troubleshooting

### "Configuration errors" on auth

Make sure your `.env` file has valid credentials:
```bash
cat .env | grep XERO
```

### "State mismatch" error

The CSRF state doesn't match. Try:
1. Clear browser cookies
2. Restart the auth flow

### "Token refresh failed"

The refresh token may have expired or been revoked:
```bash
python -m portfolio_tracker xero auth --force
```

### Rate limit errors

The API is rate-limited to 60 calls/minute. The client handles this automatically with exponential backoff.

## References

- [Xero OAuth 2.0 Documentation](https://developer.xero.com/documentation/guides/oauth2/auth-flow)
- [Xero API Reference](https://developer.xero.com/documentation/api/accounting/overview)
- [OAuth 2.0 RFC 6749](https://tools.ietf.org/html/rfc6749)
- [PKCE RFC 7636](https://tools.ietf.org/html/rfc7636)
