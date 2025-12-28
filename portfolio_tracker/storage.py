"""
Database storage for portfolio tracking.

Uses SQLite for persistent storage of portfolio snapshots and holdings.
"""

import sqlite3
import json
import logging
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

from .models import Holding, Portfolio, PortfolioSnapshot, AssetClass, Sector

logger = logging.getLogger(__name__)

# Default database path
DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "portfolio.db"


class PortfolioDatabase:
    """
    SQLite database for storing portfolio data.

    Stores:
    - Portfolio snapshots (point-in-time total values)
    - Individual holdings with full details
    - Historical data for tracking performance over time
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def initialize(self):
        """Initialize database schema."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Create portfolio snapshots table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                snapshot_date DATE NOT NULL,
                name TEXT,
                total_holdings INTEGER NOT NULL,
                total_cost_base REAL NOT NULL,
                total_market_value REAL NOT NULL,
                total_profit_loss REAL NOT NULL,
                total_profit_loss_percent REAL NOT NULL,
                total_dividends REAL DEFAULT 0,
                total_franking_credits REAL DEFAULT 0,
                source_file TEXT,
                import_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
        """)

        # Create holdings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS holdings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_id TEXT NOT NULL,
                code TEXT NOT NULL,
                name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                avg_cost REAL NOT NULL,
                current_price REAL NOT NULL,
                cost_base REAL NOT NULL,
                market_value REAL NOT NULL,
                profit_loss REAL NOT NULL,
                profit_loss_percent REAL NOT NULL,
                dividends_received REAL DEFAULT 0,
                franking_credits REAL DEFAULT 0,
                asset_class TEXT NOT NULL,
                sector TEXT,
                portfolio_weight REAL,
                notes TEXT,
                FOREIGN KEY (snapshot_id) REFERENCES portfolio_snapshots(snapshot_id)
            )
        """)

        # Create indexes for common queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_holdings_snapshot
            ON holdings(snapshot_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_holdings_code
            ON holdings(code)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_snapshots_date
            ON portfolio_snapshots(snapshot_date)
        """)

        # Migration: Add name column if it doesn't exist (for existing databases)
        cursor.execute("PRAGMA table_info(portfolio_snapshots)")
        columns = [col[1] for col in cursor.fetchall()]
        if "name" not in columns:
            cursor.execute("ALTER TABLE portfolio_snapshots ADD COLUMN name TEXT")
            logger.info("Migrated database: added 'name' column to portfolio_snapshots")

        conn.commit()
        logger.info(f"Database initialized at {self.db_path}")

    def save_portfolio(self, portfolio: Portfolio) -> str:
        """
        Save a portfolio to the database.

        Args:
            portfolio: Portfolio to save

        Returns:
            Snapshot ID of saved portfolio
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Insert portfolio snapshot
        cursor.execute("""
            INSERT OR REPLACE INTO portfolio_snapshots (
                snapshot_id, snapshot_date, name, total_holdings,
                total_cost_base, total_market_value,
                total_profit_loss, total_profit_loss_percent,
                total_dividends, total_franking_credits,
                source_file, import_timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            portfolio.snapshot_id,
            portfolio.snapshot_date.isoformat(),
            getattr(portfolio, 'name', None),
            len(portfolio.holdings),
            float(portfolio.total_cost_base),
            float(portfolio.total_market_value),
            float(portfolio.total_profit_loss),
            float(portfolio.total_profit_loss_percent),
            float(portfolio.total_dividends),
            float(portfolio.total_franking_credits),
            portfolio.source_file,
            portfolio.import_timestamp.isoformat(),
        ))

        # Delete existing holdings for this snapshot (for updates)
        cursor.execute("DELETE FROM holdings WHERE snapshot_id = ?", (portfolio.snapshot_id,))

        # Insert holdings
        for holding in portfolio.holdings:
            cursor.execute("""
                INSERT INTO holdings (
                    snapshot_id, code, name, quantity,
                    avg_cost, current_price, cost_base, market_value,
                    profit_loss, profit_loss_percent,
                    dividends_received, franking_credits,
                    asset_class, sector, portfolio_weight, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                portfolio.snapshot_id,
                holding.code,
                holding.name,
                holding.quantity,
                float(holding.avg_cost),
                float(holding.current_price),
                float(holding.cost_base),
                float(holding.market_value),
                float(holding.profit_loss),
                float(holding.profit_loss_percent),
                float(holding.dividends_received),
                float(holding.franking_credits),
                holding.asset_class.value,
                holding.sector.value,
                float(holding.portfolio_weight),
                holding.notes,
            ))

        conn.commit()
        logger.info(f"Saved portfolio snapshot {portfolio.snapshot_id} with {len(portfolio.holdings)} holdings")

        return portfolio.snapshot_id or ""

    def get_portfolio(self, snapshot_id: str) -> Optional[Portfolio]:
        """
        Load a portfolio by snapshot ID.

        Args:
            snapshot_id: ID of the snapshot to load

        Returns:
            Portfolio object or None if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Get snapshot
        cursor.execute(
            "SELECT * FROM portfolio_snapshots WHERE snapshot_id = ?",
            (snapshot_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None

        # Get holdings
        cursor.execute(
            "SELECT * FROM holdings WHERE snapshot_id = ?",
            (snapshot_id,)
        )
        holding_rows = cursor.fetchall()

        holdings = []
        for h in holding_rows:
            holdings.append(Holding(
                code=h["code"],
                name=h["name"],
                quantity=h["quantity"],
                avg_cost=Decimal(str(h["avg_cost"])),
                current_price=Decimal(str(h["current_price"])),
                cost_base=Decimal(str(h["cost_base"])),
                market_value=Decimal(str(h["market_value"])),
                profit_loss=Decimal(str(h["profit_loss"])),
                profit_loss_percent=Decimal(str(h["profit_loss_percent"])),
                dividends_received=Decimal(str(h["dividends_received"])),
                franking_credits=Decimal(str(h["franking_credits"])),
                asset_class=AssetClass(h["asset_class"]),
                sector=Sector(h["sector"]) if h["sector"] else Sector.UNKNOWN,
                portfolio_weight=Decimal(str(h["portfolio_weight"])),
                notes=h["notes"] or "",
            ))

        portfolio = Portfolio(
            holdings=holdings,
            snapshot_date=date.fromisoformat(row["snapshot_date"]),
            snapshot_id=row["snapshot_id"],
            source_file=row["source_file"] or "",
        )
        # Set name if available (may not exist in older databases)
        portfolio.name = row["name"] if "name" in row.keys() else None
        return portfolio

    def get_latest_portfolio(self) -> Optional[Portfolio]:
        """Get the most recent portfolio snapshot."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT snapshot_id FROM portfolio_snapshots
            ORDER BY snapshot_date DESC, import_timestamp DESC
            LIMIT 1
        """)
        row = cursor.fetchone()
        if row:
            return self.get_portfolio(row["snapshot_id"])
        return None

    def get_all_snapshots(self) -> List[PortfolioSnapshot]:
        """Get all portfolio snapshots (without holdings)."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM portfolio_snapshots
            ORDER BY snapshot_date DESC
        """)

        snapshots = []
        for row in cursor.fetchall():
            snapshots.append(PortfolioSnapshot(
                snapshot_id=row["snapshot_id"],
                snapshot_date=date.fromisoformat(row["snapshot_date"]),
                total_holdings=row["total_holdings"],
                total_market_value=Decimal(str(row["total_market_value"])),
                total_cost_base=Decimal(str(row["total_cost_base"])),
                total_profit_loss=Decimal(str(row["total_profit_loss"])),
                total_profit_loss_percent=Decimal(str(row["total_profit_loss_percent"])),
                name=row["name"] if "name" in row.keys() else None,
            ))

        return snapshots

    def get_holding_history(self, code: str) -> List[Dict[str, Any]]:
        """
        Get historical data for a specific holding across all snapshots.

        Args:
            code: Stock/ETF ticker code

        Returns:
            List of holding data sorted by date
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT h.*, ps.snapshot_date
            FROM holdings h
            JOIN portfolio_snapshots ps ON h.snapshot_id = ps.snapshot_id
            WHERE h.code = ?
            ORDER BY ps.snapshot_date ASC
        """, (code.upper(),))

        history = []
        for row in cursor.fetchall():
            history.append({
                "date": date.fromisoformat(row["snapshot_date"]),
                "quantity": row["quantity"],
                "avg_cost": Decimal(str(row["avg_cost"])),
                "current_price": Decimal(str(row["current_price"])),
                "market_value": Decimal(str(row["market_value"])),
                "profit_loss": Decimal(str(row["profit_loss"])),
                "profit_loss_percent": Decimal(str(row["profit_loss_percent"])),
            })

        return history

    def get_unique_holdings(self) -> List[str]:
        """Get list of all unique stock codes ever held."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT DISTINCT code FROM holdings ORDER BY code")
        return [row["code"] for row in cursor.fetchall()]

    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) as count FROM portfolio_snapshots")
        total_snapshots = cursor.fetchone()["count"]

        cursor.execute("SELECT COUNT(DISTINCT code) as count FROM holdings")
        unique_holdings = cursor.fetchone()["count"]

        cursor.execute("""
            SELECT MIN(snapshot_date) as min_date, MAX(snapshot_date) as max_date
            FROM portfolio_snapshots
        """)
        date_row = cursor.fetchone()

        # Get latest portfolio value
        latest = self.get_latest_portfolio()
        latest_value = float(latest.total_market_value) if latest else 0

        return {
            "total_snapshots": total_snapshots,
            "unique_holdings": unique_holdings,
            "date_range": {
                "min": date_row["min_date"],
                "max": date_row["max_date"],
            },
            "latest_portfolio_value": latest_value,
        }

    def rename_portfolio(self, snapshot_id: str, name: str) -> bool:
        """
        Rename a portfolio snapshot.

        Args:
            snapshot_id: ID of the snapshot to rename
            name: New name for the portfolio

        Returns:
            True if renamed successfully
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE portfolio_snapshots SET name = ? WHERE snapshot_id = ?",
            (name, snapshot_id)
        )
        conn.commit()

        success = cursor.rowcount > 0
        if success:
            logger.info(f"Renamed snapshot {snapshot_id} to '{name}'")
        return success

    def get_portfolio_by_name(self, name: str) -> Optional[Portfolio]:
        """Get portfolio by name."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT snapshot_id FROM portfolio_snapshots WHERE name = ? ORDER BY snapshot_date DESC LIMIT 1",
            (name,)
        )
        row = cursor.fetchone()
        if row:
            return self.get_portfolio(row["snapshot_id"])
        return None

    def delete_snapshot(self, snapshot_id: str) -> bool:
        """Delete a portfolio snapshot and its holdings."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM holdings WHERE snapshot_id = ?", (snapshot_id,))
        cursor.execute("DELETE FROM portfolio_snapshots WHERE snapshot_id = ?", (snapshot_id,))
        conn.commit()

        deleted = cursor.rowcount > 0
        if deleted:
            logger.info(f"Deleted snapshot {snapshot_id}")
        return deleted

    def close(self):
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None


def export_portfolio_to_csv(portfolio: Portfolio, output_path: Path):
    """Export portfolio holdings to CSV."""
    import csv

    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)

        # Header
        writer.writerow([
            "Code", "Name", "Quantity", "Avg Cost", "Current Price",
            "Cost Base", "Market Value", "P/L $", "P/L %",
            "Weight %", "Asset Class", "Sector"
        ])

        # Holdings
        for h in portfolio.top_holdings:
            writer.writerow([
                h.code,
                h.name,
                h.quantity,
                f"{float(h.avg_cost):.4f}",
                f"{float(h.current_price):.4f}",
                f"{float(h.cost_base):.2f}",
                f"{float(h.market_value):.2f}",
                f"{float(h.profit_loss):.2f}",
                f"{float(h.profit_loss_percent):.2f}",
                f"{float(h.portfolio_weight):.2f}",
                h.asset_class.value,
                h.sector.value,
            ])

        # Totals row
        writer.writerow([])
        writer.writerow([
            "TOTAL", "", "", "", "",
            f"{float(portfolio.total_cost_base):.2f}",
            f"{float(portfolio.total_market_value):.2f}",
            f"{float(portfolio.total_profit_loss):.2f}",
            f"{float(portfolio.total_profit_loss_percent):.2f}",
            "100.00", "", ""
        ])

    logger.info(f"Exported portfolio to {output_path}")
