"""
Xero OAuth 2.0 Configuration.

Handles configuration loading from environment variables and .env files.
Provides validation and sensible defaults for Xero API integration.
"""

import os
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Set

logger = logging.getLogger(__name__)

# Xero OAuth 2.0 endpoints
XERO_AUTHORIZATION_URL = "https://login.xero.com/identity/connect/authorize"
XERO_TOKEN_URL = "https://identity.xero.com/connect/token"
XERO_CONNECTIONS_URL = "https://api.xero.com/connections"
XERO_REVOKE_URL = "https://identity.xero.com/connect/revocation"

# Xero API base URLs
XERO_API_BASE_URL = "https://api.xero.com/api.xro/2.0"
XERO_ACCOUNTING_API = "https://api.xero.com/api.xro/2.0"
XERO_ASSETS_API = "https://api.xero.com/assets.xro/1.0"
XERO_PROJECTS_API = "https://api.xero.com/projects.xro/2.0"

# Available Xero OAuth scopes
XERO_SCOPES = {
    # OpenID Connect
    "openid": "OpenID authentication",
    "profile": "User profile information",
    "email": "User email address",
    "offline_access": "Refresh token for long-lived access",
    # Accounting API
    "accounting.transactions": "Invoices, credit notes, payments",
    "accounting.transactions.read": "Read-only transactions",
    "accounting.contacts": "Contacts and contact groups",
    "accounting.contacts.read": "Read-only contacts",
    "accounting.settings": "Organisation settings",
    "accounting.settings.read": "Read-only settings",
    "accounting.reports.read": "Financial reports",
    "accounting.journals.read": "Manual journals",
    "accounting.budgets.read": "Budgets",
    "accounting.attachments": "Attachments",
    "accounting.attachments.read": "Read-only attachments",
    # Assets API
    "assets": "Fixed assets",
    "assets.read": "Read-only assets",
    # Projects API
    "projects": "Projects and tasks",
    "projects.read": "Read-only projects",
    # Payroll API
    "payroll.employees": "Employee information",
    "payroll.employees.read": "Read-only employees",
    "payroll.timesheets": "Timesheets",
    "payroll.timesheets.read": "Read-only timesheets",
    "payroll.settings": "Payroll settings",
    "payroll.settings.read": "Read-only payroll settings",
}

# Default scopes for portfolio tracking
DEFAULT_SCOPES = [
    "openid",
    "profile",
    "email",
    "offline_access",
    "accounting.contacts.read",
    "accounting.transactions.read",
    "accounting.reports.read",
    "accounting.settings.read",
]


def load_dotenv():
    """Load environment variables from .env file if available."""
    env_paths = [
        Path.cwd() / ".env",
        Path(__file__).parent.parent.parent / ".env",
        Path.home() / ".portfolio_tracker" / ".env",
    ]

    for env_path in env_paths:
        if env_path.exists():
            logger.debug(f"Loading environment from: {env_path}")
            try:
                with open(env_path) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, _, value = line.partition("=")
                            key = key.strip()
                            value = value.strip().strip("\"'")
                            if key and key not in os.environ:
                                os.environ[key] = value
                logger.info(f"Loaded environment from: {env_path}")
                return True
            except Exception as e:
                logger.warning(f"Error loading .env file: {e}")

    return False


@dataclass
class XeroConfig:
    """
    Xero OAuth 2.0 Configuration.

    Attributes:
        client_id: Xero app client ID (required)
        client_secret: Xero app client secret (required for confidential apps)
        redirect_uri: OAuth callback URL
        scopes: List of OAuth scopes to request
        state_length: Length of random state parameter
        token_encryption_key: Key for encrypting stored tokens
        token_storage_path: Path to token storage file
        rate_limit_delay: Delay between API requests (seconds)
        max_retries: Maximum retry attempts for failed requests
        request_timeout: HTTP request timeout (seconds)
    """

    # Required credentials
    client_id: str = ""
    client_secret: str = ""

    # OAuth configuration
    redirect_uri: str = "http://localhost:8080/callback"
    scopes: List[str] = field(default_factory=lambda: DEFAULT_SCOPES.copy())

    # Security settings
    state_length: int = 32
    pkce_code_verifier_length: int = 128  # 43-128 chars per RFC 7636
    token_encryption_key: Optional[str] = None

    # Storage
    token_storage_path: Path = field(
        default_factory=lambda: Path(__file__).parent.parent.parent
        / "data"
        / "xero_tokens.db"
    )

    # API settings
    rate_limit_delay: float = 0.5  # Xero allows 60 calls/minute
    max_retries: int = 3
    request_timeout: int = 30
    retry_backoff_factor: float = 2.0

    # URLs (usually don't need to change)
    authorization_url: str = XERO_AUTHORIZATION_URL
    token_url: str = XERO_TOKEN_URL
    connections_url: str = XERO_CONNECTIONS_URL
    revoke_url: str = XERO_REVOKE_URL
    api_base_url: str = XERO_API_BASE_URL

    def __post_init__(self):
        """Validate configuration after initialization."""
        if isinstance(self.token_storage_path, str):
            self.token_storage_path = Path(self.token_storage_path)

        if isinstance(self.scopes, str):
            self.scopes = self.scopes.split()

    def validate(self) -> List[str]:
        """
        Validate the configuration.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        if not self.client_id:
            errors.append("XERO_CLIENT_ID is required")

        if not self.client_secret:
            errors.append("XERO_CLIENT_SECRET is required")

        if not self.redirect_uri:
            errors.append("XERO_REDIRECT_URI is required")

        # Validate scopes
        invalid_scopes = set(self.scopes) - set(XERO_SCOPES.keys())
        if invalid_scopes:
            errors.append(f"Invalid scopes: {invalid_scopes}")

        # PKCE verifier length must be 43-128
        if not 43 <= self.pkce_code_verifier_length <= 128:
            errors.append("PKCE code verifier length must be 43-128")

        return errors

    def is_valid(self) -> bool:
        """Check if configuration is valid."""
        return len(self.validate()) == 0

    @property
    def scope_string(self) -> str:
        """Get scopes as space-separated string."""
        return " ".join(self.scopes)

    def get_scope_descriptions(self) -> dict:
        """Get descriptions for configured scopes."""
        return {scope: XERO_SCOPES.get(scope, "Unknown scope") for scope in self.scopes}


def load_config() -> XeroConfig:
    """
    Load Xero configuration from environment variables.

    Environment variables:
        XERO_CLIENT_ID: Xero app client ID (required)
        XERO_CLIENT_SECRET: Xero app client secret (required)
        XERO_REDIRECT_URI: OAuth callback URL (default: http://localhost:8080/callback)
        XERO_SCOPES: Space-separated list of scopes
        XERO_TOKEN_ENCRYPTION_KEY: Key for encrypting stored tokens
        XERO_TOKEN_STORAGE_PATH: Path to token storage file

    Returns:
        XeroConfig instance
    """
    # Try to load from .env file
    load_dotenv()

    # Parse scopes from environment
    scopes_str = os.getenv("XERO_SCOPES", "")
    scopes = scopes_str.split() if scopes_str else DEFAULT_SCOPES.copy()

    # Parse token storage path
    token_path_str = os.getenv("XERO_TOKEN_STORAGE_PATH", "")
    token_path = (
        Path(token_path_str)
        if token_path_str
        else Path(__file__).parent.parent.parent / "data" / "xero_tokens.db"
    )

    config = XeroConfig(
        client_id=os.getenv("XERO_CLIENT_ID", ""),
        client_secret=os.getenv("XERO_CLIENT_SECRET", ""),
        redirect_uri=os.getenv("XERO_REDIRECT_URI", "http://localhost:8080/callback"),
        scopes=scopes,
        token_encryption_key=os.getenv("XERO_TOKEN_ENCRYPTION_KEY"),
        token_storage_path=token_path,
        rate_limit_delay=float(os.getenv("XERO_RATE_LIMIT_DELAY", "0.5")),
        max_retries=int(os.getenv("XERO_MAX_RETRIES", "3")),
        request_timeout=int(os.getenv("XERO_REQUEST_TIMEOUT", "30")),
    )

    return config


def get_available_scopes() -> dict:
    """Get all available Xero OAuth scopes with descriptions."""
    return XERO_SCOPES.copy()


def validate_scopes(scopes: List[str]) -> tuple:
    """
    Validate a list of scopes.

    Args:
        scopes: List of scope strings to validate

    Returns:
        Tuple of (valid_scopes, invalid_scopes)
    """
    valid = [s for s in scopes if s in XERO_SCOPES]
    invalid = [s for s in scopes if s not in XERO_SCOPES]
    return valid, invalid
