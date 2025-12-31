"""
Xero OAuth 2.0 Integration Module.

This module provides OAuth 2.0 certified integration with the Xero API,
including PKCE (Proof Key for Code Exchange) support as required by Xero.

Features:
- OAuth 2.0 Authorization Code flow with PKCE
- Secure token storage with encryption
- Automatic token refresh
- Multi-tenant support
- Rate limiting and retry logic

Usage:
    from portfolio_tracker.integrations import XeroOAuth, XeroClient

    # Initialize OAuth handler
    oauth = XeroOAuth()

    # Start authorization flow
    auth_url = oauth.get_authorization_url()

    # After user authorization, exchange code for tokens
    tokens = oauth.exchange_code(authorization_code)

    # Use the Xero client
    client = XeroClient()
    contacts = client.get_contacts()
"""

from .xero_config import XeroConfig, load_config
from .xero_oauth import XeroOAuth, AuthorizationError, TokenError
from .xero_tokens import TokenStorage, XeroTokens
from .xero_client import XeroClient, XeroAPIError, RateLimitError
from .xero_sync import XeroSync, SyncResult

__all__ = [
    # Configuration
    "XeroConfig",
    "load_config",
    # OAuth
    "XeroOAuth",
    "AuthorizationError",
    "TokenError",
    # Token Storage
    "TokenStorage",
    "XeroTokens",
    # Client
    "XeroClient",
    "XeroAPIError",
    "RateLimitError",
    # Sync
    "XeroSync",
    "SyncResult",
]

__version__ = "1.0.0"
