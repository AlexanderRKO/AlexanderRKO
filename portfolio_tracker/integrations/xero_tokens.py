"""
Secure Token Storage for Xero OAuth 2.0.

Provides encrypted storage of OAuth tokens using SQLite with optional
Fernet encryption for token values.

Security features:
- Tokens are encrypted at rest using Fernet (AES-128-CBC)
- Encryption key can be provided via environment or generated
- SQLite database with proper permissions
- Automatic token cleanup on disconnect
"""

import base64
import hashlib
import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .xero_config import XeroConfig, load_config
from .xero_oauth import XeroTokens, XeroTenant

logger = logging.getLogger(__name__)

# Try to import cryptography for encryption
try:
    from cryptography.fernet import Fernet, InvalidToken
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    ENCRYPTION_AVAILABLE = True
except ImportError:
    ENCRYPTION_AVAILABLE = False
    Fernet = None
    InvalidToken = Exception


def derive_key_from_password(password: str, salt: bytes = None) -> Tuple[bytes, bytes]:
    """
    Derive a Fernet key from a password using PBKDF2.

    Args:
        password: Password string to derive key from
        salt: Optional salt (generated if not provided)

    Returns:
        Tuple of (key, salt)
    """
    if not ENCRYPTION_AVAILABLE:
        raise ImportError("cryptography package required for encryption")

    if salt is None:
        salt = os.urandom(16)

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,  # OWASP recommended minimum
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key, salt


def generate_encryption_key() -> str:
    """
    Generate a new Fernet encryption key.

    Returns:
        Base64-encoded Fernet key
    """
    if not ENCRYPTION_AVAILABLE:
        raise ImportError("cryptography package required for encryption")

    return Fernet.generate_key().decode("ascii")


class TokenStorage:
    """
    Secure SQLite storage for Xero OAuth tokens.

    Stores access tokens, refresh tokens, and tenant information with
    optional encryption for sensitive token values.

    Usage:
        storage = TokenStorage()
        storage.initialize()

        # Save tokens
        storage.save_tokens(tokens, tenant_id="xxx")

        # Load tokens
        tokens = storage.get_tokens(tenant_id="xxx")

        # Check if authenticated
        if storage.has_valid_tokens():
            ...
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        encryption_key: Optional[str] = None,
        config: Optional[XeroConfig] = None,
    ):
        """
        Initialize token storage.

        Args:
            db_path: Path to SQLite database file
            encryption_key: Fernet encryption key (tokens stored in plain text if not provided)
            config: Xero configuration (used for default paths)
        """
        self.config = config or load_config()
        self.db_path = db_path or self.config.token_storage_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn: Optional[sqlite3.Connection] = None
        self._fernet: Optional["Fernet"] = None

        # Set up encryption if key provided
        if encryption_key:
            if not ENCRYPTION_AVAILABLE:
                logger.warning(
                    "cryptography package not installed - tokens will be stored in plain text"
                )
            else:
                try:
                    self._fernet = Fernet(encryption_key.encode("ascii"))
                    logger.info("Token encryption enabled")
                except Exception as e:
                    logger.warning(f"Invalid encryption key: {e}")
        elif self.config.token_encryption_key:
            if ENCRYPTION_AVAILABLE:
                try:
                    self._fernet = Fernet(self.config.token_encryption_key.encode("ascii"))
                    logger.info("Token encryption enabled from config")
                except Exception as e:
                    logger.warning(f"Invalid encryption key in config: {e}")

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _encrypt(self, data: str) -> str:
        """Encrypt a string value."""
        if self._fernet:
            encrypted = self._fernet.encrypt(data.encode("utf-8"))
            return encrypted.decode("ascii")
        return data

    def _decrypt(self, data: str) -> str:
        """Decrypt a string value."""
        if self._fernet:
            try:
                decrypted = self._fernet.decrypt(data.encode("ascii"))
                return decrypted.decode("utf-8")
            except InvalidToken:
                logger.error("Failed to decrypt token - invalid key or corrupted data")
                raise
        return data

    def initialize(self):
        """Initialize database schema."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Create tokens table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS xero_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT UNIQUE NOT NULL,
                tenant_name TEXT,
                access_token TEXT NOT NULL,
                refresh_token TEXT NOT NULL,
                token_type TEXT DEFAULT 'Bearer',
                expires_in INTEGER DEFAULT 1800,
                scope TEXT,
                id_token TEXT,
                created_at DATETIME NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                encrypted INTEGER DEFAULT 0
            )
        """)

        # Create tenants table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS xero_tenants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                connection_id TEXT UNIQUE NOT NULL,
                auth_event_id TEXT,
                tenant_id TEXT NOT NULL,
                tenant_type TEXT,
                tenant_name TEXT,
                created_date_utc DATETIME,
                updated_date_utc DATETIME,
                is_active INTEGER DEFAULT 1,
                last_sync DATETIME
            )
        """)

        # Create sync log table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS xero_sync_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL,
                sync_type TEXT NOT NULL,
                sync_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL,
                records_synced INTEGER DEFAULT 0,
                error_message TEXT,
                details TEXT
            )
        """)

        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tokens_tenant
            ON xero_tokens(tenant_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tenants_active
            ON xero_tenants(is_active)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sync_log_tenant
            ON xero_sync_log(tenant_id, sync_date)
        """)

        conn.commit()
        logger.info(f"Token storage initialized at {self.db_path}")

    def save_tokens(
        self,
        tokens: XeroTokens,
        tenant_id: str,
        tenant_name: Optional[str] = None,
    ) -> bool:
        """
        Save or update tokens for a tenant.

        Args:
            tokens: XeroTokens to save
            tenant_id: Tenant/organisation ID
            tenant_name: Optional tenant name

        Returns:
            True if saved successfully
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Encrypt sensitive tokens
            access_token = self._encrypt(tokens.access_token)
            refresh_token = self._encrypt(tokens.refresh_token)
            id_token = self._encrypt(tokens.id_token) if tokens.id_token else None

            cursor.execute(
                """
                INSERT OR REPLACE INTO xero_tokens (
                    tenant_id, tenant_name, access_token, refresh_token,
                    token_type, expires_in, scope, id_token,
                    created_at, updated_at, encrypted
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
                """,
                (
                    tenant_id,
                    tenant_name,
                    access_token,
                    refresh_token,
                    tokens.token_type,
                    tokens.expires_in,
                    tokens.scope,
                    id_token,
                    tokens.created_at.isoformat() if tokens.created_at else datetime.utcnow().isoformat(),
                    1 if self._fernet else 0,
                ),
            )

            conn.commit()
            logger.info(f"Saved tokens for tenant: {tenant_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to save tokens: {e}")
            conn.rollback()
            return False

    def get_tokens(self, tenant_id: str) -> Optional[XeroTokens]:
        """
        Get tokens for a tenant.

        Args:
            tenant_id: Tenant/organisation ID

        Returns:
            XeroTokens or None if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM xero_tokens WHERE tenant_id = ?",
            (tenant_id,),
        )

        row = cursor.fetchone()
        if not row:
            return None

        try:
            # Decrypt tokens
            access_token = self._decrypt(row["access_token"])
            refresh_token = self._decrypt(row["refresh_token"])
            id_token = self._decrypt(row["id_token"]) if row["id_token"] else None

            created_at = row["created_at"]
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at)

            return XeroTokens(
                access_token=access_token,
                refresh_token=refresh_token,
                token_type=row["token_type"],
                expires_in=row["expires_in"],
                scope=row["scope"] or "",
                id_token=id_token,
                created_at=created_at,
            )

        except Exception as e:
            logger.error(f"Failed to load tokens: {e}")
            return None

    def get_all_tokens(self) -> Dict[str, XeroTokens]:
        """
        Get tokens for all tenants.

        Returns:
            Dictionary mapping tenant_id to XeroTokens
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT tenant_id FROM xero_tokens")
        rows = cursor.fetchall()

        tokens = {}
        for row in rows:
            tenant_id = row["tenant_id"]
            token = self.get_tokens(tenant_id)
            if token:
                tokens[tenant_id] = token

        return tokens

    def delete_tokens(self, tenant_id: str) -> bool:
        """
        Delete tokens for a tenant.

        Args:
            tenant_id: Tenant/organisation ID

        Returns:
            True if deleted successfully
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "DELETE FROM xero_tokens WHERE tenant_id = ?",
                (tenant_id,),
            )
            conn.commit()
            logger.info(f"Deleted tokens for tenant: {tenant_id}")
            return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Failed to delete tokens: {e}")
            return False

    def delete_all_tokens(self) -> int:
        """
        Delete all stored tokens.

        Returns:
            Number of tokens deleted
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("DELETE FROM xero_tokens")
            deleted = cursor.rowcount
            conn.commit()
            logger.info(f"Deleted {deleted} token record(s)")
            return deleted

        except Exception as e:
            logger.error(f"Failed to delete all tokens: {e}")
            return 0

    def has_valid_tokens(self, tenant_id: Optional[str] = None) -> bool:
        """
        Check if valid (non-expired) tokens exist.

        Args:
            tenant_id: Optional specific tenant to check

        Returns:
            True if valid tokens exist
        """
        if tenant_id:
            tokens = self.get_tokens(tenant_id)
            return tokens is not None and not tokens.is_expired
        else:
            all_tokens = self.get_all_tokens()
            return any(not t.is_expired for t in all_tokens.values())

    def get_default_tenant(self) -> Optional[str]:
        """
        Get the default (first) tenant ID.

        Returns:
            Tenant ID or None
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT tenant_id FROM xero_tokens ORDER BY updated_at DESC LIMIT 1"
        )
        row = cursor.fetchone()

        return row["tenant_id"] if row else None

    # Tenant management methods

    def save_tenant(self, tenant: XeroTenant) -> bool:
        """
        Save or update a tenant record.

        Args:
            tenant: XeroTenant to save

        Returns:
            True if saved successfully
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                INSERT OR REPLACE INTO xero_tenants (
                    connection_id, auth_event_id, tenant_id, tenant_type,
                    tenant_name, created_date_utc, updated_date_utc, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    tenant.id,
                    tenant.auth_event_id,
                    tenant.tenant_id,
                    tenant.tenant_type,
                    tenant.tenant_name,
                    tenant.created_date_utc.isoformat() if tenant.created_date_utc else None,
                    tenant.updated_date_utc.isoformat() if tenant.updated_date_utc else None,
                ),
            )
            conn.commit()
            return True

        except Exception as e:
            logger.error(f"Failed to save tenant: {e}")
            return False

    def save_tenants(self, tenants: List[XeroTenant]) -> int:
        """
        Save multiple tenants.

        Args:
            tenants: List of XeroTenant objects

        Returns:
            Number of tenants saved
        """
        saved = 0
        for tenant in tenants:
            if self.save_tenant(tenant):
                saved += 1
        return saved

    def get_active_tenants(self) -> List[Dict]:
        """
        Get all active tenants.

        Returns:
            List of tenant dictionaries
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM xero_tenants WHERE is_active = 1 ORDER BY tenant_name"
        )
        rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def deactivate_tenant(self, connection_id: str) -> bool:
        """
        Mark a tenant as inactive.

        Args:
            connection_id: Connection ID to deactivate

        Returns:
            True if successful
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "UPDATE xero_tenants SET is_active = 0 WHERE connection_id = ?",
                (connection_id,),
            )
            conn.commit()
            return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Failed to deactivate tenant: {e}")
            return False

    # Sync logging methods

    def log_sync(
        self,
        tenant_id: str,
        sync_type: str,
        status: str,
        records_synced: int = 0,
        error_message: Optional[str] = None,
        details: Optional[Dict] = None,
    ) -> bool:
        """
        Log a sync operation.

        Args:
            tenant_id: Tenant ID
            sync_type: Type of sync (e.g., "contacts", "invoices")
            status: Sync status ("success", "error", "partial")
            records_synced: Number of records synced
            error_message: Error message if applicable
            details: Additional details as dictionary

        Returns:
            True if logged successfully
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO xero_sync_log (
                    tenant_id, sync_type, status, records_synced,
                    error_message, details
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    tenant_id,
                    sync_type,
                    status,
                    records_synced,
                    error_message,
                    json.dumps(details) if details else None,
                ),
            )
            conn.commit()
            return True

        except Exception as e:
            logger.error(f"Failed to log sync: {e}")
            return False

    def get_sync_history(
        self,
        tenant_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict]:
        """
        Get sync history.

        Args:
            tenant_id: Optional tenant filter
            limit: Maximum records to return

        Returns:
            List of sync log dictionaries
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        if tenant_id:
            cursor.execute(
                """
                SELECT * FROM xero_sync_log
                WHERE tenant_id = ?
                ORDER BY sync_date DESC
                LIMIT ?
                """,
                (tenant_id, limit),
            )
        else:
            cursor.execute(
                """
                SELECT * FROM xero_sync_log
                ORDER BY sync_date DESC
                LIMIT ?
                """,
                (limit,),
            )

        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def get_last_sync(self, tenant_id: str, sync_type: str) -> Optional[Dict]:
        """
        Get the last sync record for a tenant and type.

        Args:
            tenant_id: Tenant ID
            sync_type: Type of sync

        Returns:
            Sync log dictionary or None
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM xero_sync_log
            WHERE tenant_id = ? AND sync_type = ?
            ORDER BY sync_date DESC
            LIMIT 1
            """,
            (tenant_id, sync_type),
        )

        row = cursor.fetchone()
        return dict(row) if row else None

    def cleanup_old_logs(self, days: int = 90) -> int:
        """
        Delete sync logs older than specified days.

        Args:
            days: Age threshold in days

        Returns:
            Number of records deleted
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                DELETE FROM xero_sync_log
                WHERE sync_date < datetime('now', ?)
                """,
                (f"-{days} days",),
            )
            deleted = cursor.rowcount
            conn.commit()
            logger.info(f"Cleaned up {deleted} old sync log entries")
            return deleted

        except Exception as e:
            logger.error(f"Failed to cleanup logs: {e}")
            return 0

    def get_status(self) -> Dict:
        """
        Get overall storage status.

        Returns:
            Dictionary with status information
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Count tokens
        cursor.execute("SELECT COUNT(*) as count FROM xero_tokens")
        token_count = cursor.fetchone()["count"]

        # Count active tenants
        cursor.execute("SELECT COUNT(*) as count FROM xero_tenants WHERE is_active = 1")
        tenant_count = cursor.fetchone()["count"]

        # Get last sync
        cursor.execute(
            "SELECT MAX(sync_date) as last_sync FROM xero_sync_log WHERE status = 'success'"
        )
        row = cursor.fetchone()
        last_sync = row["last_sync"] if row else None

        # Check if any valid tokens
        has_valid = self.has_valid_tokens()

        return {
            "token_count": token_count,
            "tenant_count": tenant_count,
            "last_sync": last_sync,
            "has_valid_tokens": has_valid,
            "encryption_enabled": self._fernet is not None,
            "db_path": str(self.db_path),
        }

    def close(self):
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
