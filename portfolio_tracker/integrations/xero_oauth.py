"""
Xero OAuth 2.0 Authorization Handler with PKCE Support.

Implements the OAuth 2.0 Authorization Code flow with PKCE (Proof Key for Code
Exchange) as required by Xero for secure authorization.

PKCE Flow:
1. Generate a random code_verifier (43-128 chars)
2. Create code_challenge = base64url(sha256(code_verifier))
3. Include code_challenge in authorization URL
4. Exchange authorization code with code_verifier

This prevents authorization code interception attacks.

References:
- Xero OAuth 2.0 docs: https://developer.xero.com/documentation/guides/oauth2/auth-flow
- RFC 7636 (PKCE): https://tools.ietf.org/html/rfc7636
- RFC 6749 (OAuth 2.0): https://tools.ietf.org/html/rfc6749
"""

import base64
import hashlib
import logging
import secrets
import time
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Callable, Dict, Optional, Tuple
from urllib.parse import parse_qs, urlencode, urlparse

import requests

from .xero_config import XeroConfig, load_config

logger = logging.getLogger(__name__)


class AuthorizationError(Exception):
    """Raised when authorization fails."""

    def __init__(self, message: str, error_code: str = None, error_description: str = None):
        super().__init__(message)
        self.error_code = error_code
        self.error_description = error_description


class TokenError(Exception):
    """Raised when token operations fail."""

    def __init__(self, message: str, error_code: str = None, error_description: str = None):
        super().__init__(message)
        self.error_code = error_code
        self.error_description = error_description


@dataclass
class XeroTokens:
    """Container for Xero OAuth tokens."""

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = 1800  # 30 minutes
    scope: str = ""
    id_token: Optional[str] = None
    created_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()

    @property
    def expires_at(self) -> datetime:
        """Calculate token expiration time."""
        return self.created_at + timedelta(seconds=self.expires_in)

    @property
    def is_expired(self) -> bool:
        """Check if the access token has expired."""
        # Add 60 second buffer to avoid using token right at expiration
        return datetime.utcnow() >= (self.expires_at - timedelta(seconds=60))

    @property
    def time_until_expiry(self) -> timedelta:
        """Get time remaining until token expires."""
        return self.expires_at - datetime.utcnow()

    def to_dict(self) -> Dict:
        """Convert tokens to dictionary."""
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_type": self.token_type,
            "expires_in": self.expires_in,
            "scope": self.scope,
            "id_token": self.id_token,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "XeroTokens":
        """Create tokens from dictionary."""
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)

        return cls(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            token_type=data.get("token_type", "Bearer"),
            expires_in=data.get("expires_in", 1800),
            scope=data.get("scope", ""),
            id_token=data.get("id_token"),
            created_at=created_at,
        )


@dataclass
class XeroTenant:
    """Xero organisation/tenant information."""

    id: str
    auth_event_id: str
    tenant_id: str
    tenant_type: str
    tenant_name: str
    created_date_utc: Optional[datetime] = None
    updated_date_utc: Optional[datetime] = None

    @classmethod
    def from_dict(cls, data: Dict) -> "XeroTenant":
        """Create tenant from API response dictionary."""
        created = data.get("createdDateUtc")
        updated = data.get("updatedDateUtc")

        return cls(
            id=data.get("id", ""),
            auth_event_id=data.get("authEventId", ""),
            tenant_id=data.get("tenantId", ""),
            tenant_type=data.get("tenantType", ""),
            tenant_name=data.get("tenantName", ""),
            created_date_utc=datetime.fromisoformat(created.replace("Z", "+00:00"))
            if created
            else None,
            updated_date_utc=datetime.fromisoformat(updated.replace("Z", "+00:00"))
            if updated
            else None,
        )


class XeroOAuth:
    """
    Xero OAuth 2.0 Authorization Handler.

    Implements the complete OAuth 2.0 flow with PKCE for Xero certification.

    Usage:
        oauth = XeroOAuth()

        # Get authorization URL
        auth_url, state = oauth.get_authorization_url()

        # Open browser for user to authorize
        webbrowser.open(auth_url)

        # Exchange authorization code for tokens (after callback)
        tokens = oauth.exchange_code(auth_code, state)

        # Refresh tokens when expired
        new_tokens = oauth.refresh_tokens(tokens.refresh_token)

        # Get connected tenants
        tenants = oauth.get_connections(tokens.access_token)
    """

    def __init__(self, config: Optional[XeroConfig] = None):
        """
        Initialize OAuth handler.

        Args:
            config: Xero configuration (loads from environment if not provided)
        """
        self.config = config or load_config()
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "PortfolioTracker/1.0"})

        # PKCE state (stored during authorization flow)
        self._code_verifier: Optional[str] = None
        self._state: Optional[str] = None

    def _generate_code_verifier(self) -> str:
        """
        Generate a cryptographically random code verifier for PKCE.

        The code verifier must be 43-128 characters using only:
        [A-Z], [a-z], [0-9], "-", ".", "_", "~"

        Returns:
            Random code verifier string
        """
        # Use URL-safe base64 encoding which only uses A-Z, a-z, 0-9, -, _
        length = self.config.pkce_code_verifier_length
        random_bytes = secrets.token_bytes((length * 3) // 4 + 1)
        verifier = base64.urlsafe_b64encode(random_bytes).decode("ascii")
        # Strip padding and truncate to desired length
        verifier = verifier.rstrip("=")[:length]
        return verifier

    def _generate_code_challenge(self, code_verifier: str) -> str:
        """
        Generate code challenge from code verifier using S256 method.

        code_challenge = BASE64URL(SHA256(code_verifier))

        Args:
            code_verifier: The code verifier string

        Returns:
            Base64URL-encoded SHA256 hash of the verifier
        """
        sha256_hash = hashlib.sha256(code_verifier.encode("ascii")).digest()
        challenge = base64.urlsafe_b64encode(sha256_hash).decode("ascii")
        # Remove padding for URL safety
        return challenge.rstrip("=")

    def _generate_state(self) -> str:
        """
        Generate a random state parameter for CSRF protection.

        Returns:
            Random state string
        """
        return secrets.token_urlsafe(self.config.state_length)

    def get_authorization_url(self, state: Optional[str] = None) -> Tuple[str, str]:
        """
        Generate the Xero authorization URL with PKCE parameters.

        Args:
            state: Optional state parameter (generated if not provided)

        Returns:
            Tuple of (authorization_url, state)
        """
        # Generate PKCE code verifier and challenge
        self._code_verifier = self._generate_code_verifier()
        code_challenge = self._generate_code_challenge(self._code_verifier)

        # Generate or use provided state
        self._state = state or self._generate_state()

        # Build authorization URL with all required parameters
        params = {
            "response_type": "code",
            "client_id": self.config.client_id,
            "redirect_uri": self.config.redirect_uri,
            "scope": self.config.scope_string,
            "state": self._state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }

        auth_url = f"{self.config.authorization_url}?{urlencode(params)}"
        logger.info(f"Generated authorization URL with state: {self._state[:8]}...")

        return auth_url, self._state

    def exchange_code(
        self,
        authorization_code: str,
        expected_state: Optional[str] = None,
    ) -> XeroTokens:
        """
        Exchange authorization code for access and refresh tokens.

        Args:
            authorization_code: The authorization code from the callback
            expected_state: Expected state to validate (uses stored state if not provided)

        Returns:
            XeroTokens containing access and refresh tokens

        Raises:
            AuthorizationError: If state validation fails
            TokenError: If token exchange fails
        """
        # Validate state if provided
        if expected_state:
            if self._state and expected_state != self._state:
                raise AuthorizationError(
                    "State mismatch - possible CSRF attack",
                    error_code="invalid_state",
                )

        if not self._code_verifier:
            raise AuthorizationError(
                "Code verifier not found - authorization flow not started properly",
                error_code="missing_verifier",
            )

        # Prepare token request
        data = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": self.config.redirect_uri,
            "code_verifier": self._code_verifier,
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }

        # Include client credentials in request body (not all Xero apps use basic auth)
        auth = (self.config.client_id, self.config.client_secret)

        try:
            response = self._session.post(
                self.config.token_url,
                data=data,
                headers=headers,
                auth=auth,
                timeout=self.config.request_timeout,
            )

            if response.status_code != 200:
                error_data = response.json() if response.text else {}
                raise TokenError(
                    f"Token exchange failed: {response.status_code}",
                    error_code=error_data.get("error", "unknown"),
                    error_description=error_data.get("error_description", response.text),
                )

            token_data = response.json()
            tokens = XeroTokens(
                access_token=token_data["access_token"],
                refresh_token=token_data["refresh_token"],
                token_type=token_data.get("token_type", "Bearer"),
                expires_in=token_data.get("expires_in", 1800),
                scope=token_data.get("scope", ""),
                id_token=token_data.get("id_token"),
            )

            logger.info("Successfully exchanged authorization code for tokens")

            # Clear PKCE state after successful exchange
            self._code_verifier = None
            self._state = None

            return tokens

        except requests.RequestException as e:
            raise TokenError(f"Network error during token exchange: {e}")

    def refresh_tokens(self, refresh_token: str) -> XeroTokens:
        """
        Refresh access token using refresh token.

        Args:
            refresh_token: The refresh token

        Returns:
            New XeroTokens with fresh access token

        Raises:
            TokenError: If refresh fails
        """
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }

        auth = (self.config.client_id, self.config.client_secret)

        try:
            response = self._session.post(
                self.config.token_url,
                data=data,
                headers=headers,
                auth=auth,
                timeout=self.config.request_timeout,
            )

            if response.status_code != 200:
                error_data = response.json() if response.text else {}
                raise TokenError(
                    f"Token refresh failed: {response.status_code}",
                    error_code=error_data.get("error", "unknown"),
                    error_description=error_data.get("error_description", response.text),
                )

            token_data = response.json()
            tokens = XeroTokens(
                access_token=token_data["access_token"],
                refresh_token=token_data["refresh_token"],
                token_type=token_data.get("token_type", "Bearer"),
                expires_in=token_data.get("expires_in", 1800),
                scope=token_data.get("scope", ""),
                id_token=token_data.get("id_token"),
            )

            logger.info("Successfully refreshed tokens")
            return tokens

        except requests.RequestException as e:
            raise TokenError(f"Network error during token refresh: {e}")

    def get_connections(self, access_token: str) -> list:
        """
        Get list of authorized Xero tenants/organisations.

        Args:
            access_token: Valid access token

        Returns:
            List of XeroTenant objects

        Raises:
            TokenError: If request fails
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        try:
            response = self._session.get(
                self.config.connections_url,
                headers=headers,
                timeout=self.config.request_timeout,
            )

            if response.status_code != 200:
                error_data = response.json() if response.text else {}
                raise TokenError(
                    f"Failed to get connections: {response.status_code}",
                    error_code=error_data.get("error", "unknown"),
                    error_description=error_data.get("error_description", response.text),
                )

            connections = response.json()
            tenants = [XeroTenant.from_dict(conn) for conn in connections]

            logger.info(f"Found {len(tenants)} connected tenant(s)")
            return tenants

        except requests.RequestException as e:
            raise TokenError(f"Network error getting connections: {e}")

    def revoke_token(self, token: str) -> bool:
        """
        Revoke a token (access or refresh).

        Args:
            token: The token to revoke

        Returns:
            True if revocation succeeded

        Raises:
            TokenError: If revocation fails
        """
        data = {
            "token": token,
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }

        auth = (self.config.client_id, self.config.client_secret)

        try:
            response = self._session.post(
                self.config.revoke_url,
                data=data,
                headers=headers,
                auth=auth,
                timeout=self.config.request_timeout,
            )

            # Revocation endpoint returns 200 on success
            if response.status_code == 200:
                logger.info("Successfully revoked token")
                return True
            else:
                error_data = response.json() if response.text else {}
                raise TokenError(
                    f"Token revocation failed: {response.status_code}",
                    error_code=error_data.get("error", "unknown"),
                    error_description=error_data.get("error_description", response.text),
                )

        except requests.RequestException as e:
            raise TokenError(f"Network error during token revocation: {e}")

    def disconnect_tenant(self, connection_id: str, access_token: str) -> bool:
        """
        Disconnect a specific tenant/organisation.

        Args:
            connection_id: The connection ID to disconnect
            access_token: Valid access token

        Returns:
            True if disconnection succeeded
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        try:
            response = self._session.delete(
                f"{self.config.connections_url}/{connection_id}",
                headers=headers,
                timeout=self.config.request_timeout,
            )

            if response.status_code in (200, 204):
                logger.info(f"Successfully disconnected tenant: {connection_id}")
                return True
            else:
                logger.error(f"Failed to disconnect tenant: {response.status_code}")
                return False

        except requests.RequestException as e:
            logger.error(f"Network error disconnecting tenant: {e}")
            return False


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP request handler for OAuth callback."""

    def __init__(self, *args, callback: Callable = None, **kwargs):
        self.callback = callback
        super().__init__(*args, **kwargs)

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass

    def do_GET(self):
        """Handle GET request to callback URL."""
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        # Extract authorization code and state
        code = params.get("code", [None])[0]
        state = params.get("state", [None])[0]
        error = params.get("error", [None])[0]
        error_description = params.get("error_description", [""])[0]

        if error:
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                f"""
                <html>
                <body style="font-family: sans-serif; text-align: center; padding: 50px;">
                <h1>Authorization Failed</h1>
                <p>Error: {error}</p>
                <p>{error_description}</p>
                <p>You can close this window.</p>
                </body>
                </html>
                """.encode()
            )
            if self.callback:
                self.callback(None, state, error, error_description)
        elif code:
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"""
                <html>
                <body style="font-family: sans-serif; text-align: center; padding: 50px;">
                <h1>Authorization Successful!</h1>
                <p>You have successfully connected to Xero.</p>
                <p>You can close this window and return to the application.</p>
                </body>
                </html>
                """
            )
            if self.callback:
                self.callback(code, state, None, None)
        else:
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"Missing authorization code")


def run_local_server(
    port: int = 8080,
    timeout: int = 300,
    on_callback: Callable = None,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Run a local HTTP server to receive the OAuth callback.

    Args:
        port: Port to listen on
        timeout: Server timeout in seconds
        on_callback: Callback function for authorization result

    Returns:
        Tuple of (authorization_code, state) or (None, None) on failure
    """
    result = {"code": None, "state": None, "error": None}

    def callback_handler(code, state, error, error_description):
        result["code"] = code
        result["state"] = state
        result["error"] = error
        result["error_description"] = error_description

    # Create custom handler class with callback
    class Handler(OAuthCallbackHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, callback=callback_handler, **kwargs)

    server = HTTPServer(("localhost", port), Handler)
    server.timeout = timeout

    logger.info(f"Waiting for OAuth callback on port {port}...")

    # Handle single request
    server.handle_request()
    server.server_close()

    if result["error"]:
        raise AuthorizationError(
            f"Authorization failed: {result['error']}",
            error_code=result["error"],
            error_description=result.get("error_description"),
        )

    if on_callback and result["code"]:
        on_callback(result["code"], result["state"])

    return result["code"], result["state"]


def authorize_interactive(
    config: Optional[XeroConfig] = None,
    open_browser: bool = True,
    callback_port: int = 8080,
    timeout: int = 300,
) -> Tuple[XeroTokens, list]:
    """
    Run interactive OAuth authorization flow.

    This is a convenience function that handles the complete authorization flow:
    1. Generates authorization URL with PKCE
    2. Opens browser for user authorization
    3. Starts local server for callback
    4. Exchanges code for tokens
    5. Gets connected tenants

    Args:
        config: Xero configuration (loads from environment if not provided)
        open_browser: Whether to automatically open the browser
        callback_port: Port for callback server
        timeout: Timeout waiting for callback

    Returns:
        Tuple of (XeroTokens, list of XeroTenant)

    Raises:
        AuthorizationError: If authorization fails
        TokenError: If token exchange fails
    """
    oauth = XeroOAuth(config)

    # Ensure redirect URI matches callback port
    if callback_port != 8080:
        oauth.config.redirect_uri = f"http://localhost:{callback_port}/callback"

    # Generate authorization URL
    auth_url, state = oauth.get_authorization_url()

    print(f"\nPlease authorize the application by visiting:\n{auth_url}\n")

    if open_browser:
        webbrowser.open(auth_url)
        print("Opening browser...")
    else:
        print("Please open the URL above in your browser.")

    # Wait for callback
    code, returned_state = run_local_server(port=callback_port, timeout=timeout)

    if not code:
        raise AuthorizationError("No authorization code received")

    # Exchange code for tokens
    tokens = oauth.exchange_code(code, returned_state)

    # Get connected tenants
    tenants = oauth.get_connections(tokens.access_token)

    return tokens, tenants
