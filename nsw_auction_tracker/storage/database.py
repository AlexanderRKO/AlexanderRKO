"""
SQLite database storage for auction results.

Provides persistent storage with:
- Full history of all auctions
- Weekly snapshots
- Query and export capabilities
"""

import sqlite3
import csv
import logging
from pathlib import Path
from datetime import date, datetime
from typing import List, Optional, Dict, Any, Tuple
from contextlib import contextmanager

from ..config import DATABASE_PATH, ensure_directories
from ..models import AuctionResult, AuctionOutcome, PropertyType, SuburbSummary

logger = logging.getLogger(__name__)


class AuctionDatabase:
    """
    SQLite database for storing auction results.

    Usage:
        db = AuctionDatabase()
        db.initialize()
        db.insert_results(results)
        results = db.get_results_by_week("2024-W01")
    """

    def __init__(self, db_path: Optional[Path] = None):
        ensure_directories()
        self.db_path = db_path or DATABASE_PATH
        self._connection: Optional[sqlite3.Connection] = None

    @contextmanager
    def get_connection(self):
        """Get a database connection with context management."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self):
        """Create database tables if they don't exist."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Main auction results table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS auction_results (
                    id TEXT PRIMARY KEY,
                    address TEXT NOT NULL,
                    suburb TEXT,
                    postcode TEXT,
                    state TEXT DEFAULT 'NSW',
                    region TEXT,
                    property_type TEXT,
                    bedrooms INTEGER,
                    bathrooms INTEGER,
                    parking INTEGER,
                    land_size INTEGER,
                    auction_date DATE,
                    outcome TEXT,
                    sold_price INTEGER,
                    guide_price_low INTEGER,
                    guide_price_high INTEGER,
                    reserve_price INTEGER,
                    agent_name TEXT,
                    agency_name TEXT,
                    source_url TEXT,
                    listing_id TEXT,
                    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    collection_week TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Weekly summaries table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS weekly_summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    week TEXT NOT NULL,
                    collection_date DATE,
                    suburb TEXT,
                    postcode TEXT,
                    region TEXT,
                    total_auctions INTEGER DEFAULT 0,
                    sold_count INTEGER DEFAULT 0,
                    passed_in_count INTEGER DEFAULT 0,
                    withdrawn_count INTEGER DEFAULT 0,
                    median_price INTEGER,
                    average_price INTEGER,
                    min_price INTEGER,
                    max_price INTEGER,
                    total_value INTEGER,
                    clearance_rate REAL,
                    houses_sold INTEGER DEFAULT 0,
                    units_sold INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(week, suburb, postcode)
                )
            """)

            # Collection runs table (for tracking scraping sessions)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS collection_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    week TEXT,
                    total_results INTEGER DEFAULT 0,
                    suburbs_scraped INTEGER DEFAULT 0,
                    errors INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'running',
                    notes TEXT
                )
            """)

            # Create indexes for common queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_results_week
                ON auction_results(collection_week)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_results_suburb
                ON auction_results(suburb, postcode)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_results_date
                ON auction_results(auction_date)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_summaries_week
                ON weekly_summaries(week)
            """)

            logger.info(f"Database initialized at {self.db_path}")

    def insert_result(self, result: AuctionResult) -> bool:
        """
        Insert a single auction result.

        Args:
            result: AuctionResult to insert

        Returns:
            True if inserted, False if duplicate
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO auction_results (
                        id, address, suburb, postcode, state, region,
                        property_type, bedrooms, bathrooms, parking, land_size,
                        auction_date, outcome, sold_price,
                        guide_price_low, guide_price_high, reserve_price,
                        agent_name, agency_name, source_url, listing_id,
                        collected_at, collection_week
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    result.id,
                    result.address,
                    result.suburb,
                    result.postcode,
                    result.state,
                    result.region,
                    result.property_type.value,
                    result.bedrooms,
                    result.bathrooms,
                    result.parking,
                    result.land_size,
                    result.auction_date.isoformat() if result.auction_date else None,
                    result.outcome.value,
                    result.sold_price,
                    result.guide_price_low,
                    result.guide_price_high,
                    result.reserve_price,
                    result.agent_name,
                    result.agency_name,
                    result.source_url,
                    result.listing_id,
                    result.collected_at.isoformat(),
                    result.collection_week,
                ))
                return True
            except sqlite3.IntegrityError:
                logger.debug(f"Duplicate result: {result.id}")
                return False

    def insert_results(self, results: List[AuctionResult]) -> Tuple[int, int]:
        """
        Insert multiple auction results.

        Args:
            results: List of AuctionResult objects

        Returns:
            Tuple of (inserted_count, duplicate_count)
        """
        inserted = 0
        duplicates = 0

        for result in results:
            if self.insert_result(result):
                inserted += 1
            else:
                duplicates += 1

        logger.info(f"Inserted {inserted} results, {duplicates} duplicates skipped")
        return inserted, duplicates

    def get_results_by_week(self, week: str) -> List[AuctionResult]:
        """
        Get all results for a specific week.

        Args:
            week: Week string in format "2024-W01"

        Returns:
            List of AuctionResult objects
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM auction_results
                WHERE collection_week = ?
                ORDER BY suburb, address
            """, (week,))

            return [self._row_to_result(row) for row in cursor.fetchall()]

    def get_results_by_suburb(
        self, suburb: str, postcode: Optional[str] = None
    ) -> List[AuctionResult]:
        """
        Get all results for a suburb.

        Args:
            suburb: Suburb name
            postcode: Optional postcode filter

        Returns:
            List of AuctionResult objects
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            if postcode:
                cursor.execute("""
                    SELECT * FROM auction_results
                    WHERE suburb = ? AND postcode = ?
                    ORDER BY auction_date DESC
                """, (suburb, postcode))
            else:
                cursor.execute("""
                    SELECT * FROM auction_results
                    WHERE suburb = ?
                    ORDER BY auction_date DESC
                """, (suburb,))

            return [self._row_to_result(row) for row in cursor.fetchall()]

    def get_results_by_date_range(
        self, start_date: date, end_date: date
    ) -> List[AuctionResult]:
        """
        Get results within a date range.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            List of AuctionResult objects
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM auction_results
                WHERE auction_date BETWEEN ? AND ?
                ORDER BY auction_date, suburb
            """, (start_date.isoformat(), end_date.isoformat()))

            return [self._row_to_result(row) for row in cursor.fetchall()]

    def _row_to_result(self, row: sqlite3.Row) -> AuctionResult:
        """Convert database row to AuctionResult."""
        return AuctionResult(
            id=row["id"],
            address=row["address"],
            suburb=row["suburb"] or "",
            postcode=row["postcode"] or "",
            state=row["state"] or "NSW",
            region=row["region"] or "",
            property_type=PropertyType(row["property_type"]) if row["property_type"] else PropertyType.OTHER,
            bedrooms=row["bedrooms"],
            bathrooms=row["bathrooms"],
            parking=row["parking"],
            land_size=row["land_size"],
            auction_date=date.fromisoformat(row["auction_date"]) if row["auction_date"] else None,
            outcome=AuctionOutcome(row["outcome"]) if row["outcome"] else AuctionOutcome.UNKNOWN,
            sold_price=row["sold_price"],
            guide_price_low=row["guide_price_low"],
            guide_price_high=row["guide_price_high"],
            reserve_price=row["reserve_price"],
            agent_name=row["agent_name"],
            agency_name=row["agency_name"],
            source_url=row["source_url"],
            listing_id=row["listing_id"],
            collected_at=datetime.fromisoformat(row["collected_at"]) if row["collected_at"] else datetime.now(),
            collection_week=row["collection_week"],
        )

    def save_summary(self, summary: SuburbSummary) -> bool:
        """
        Save a suburb summary.

        Args:
            summary: SuburbSummary to save

        Returns:
            True if saved successfully
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO weekly_summaries (
                        week, collection_date, suburb, postcode, region,
                        total_auctions, sold_count, passed_in_count, withdrawn_count,
                        median_price, average_price, min_price, max_price, total_value,
                        clearance_rate, houses_sold, units_sold
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    summary.week,
                    date.today().isoformat(),
                    summary.suburb,
                    summary.postcode,
                    summary.region,
                    summary.total_auctions,
                    summary.sold_count,
                    summary.passed_in_count,
                    summary.withdrawn_count,
                    summary.median_price,
                    summary.average_price,
                    summary.min_price,
                    summary.max_price,
                    summary.total_value,
                    summary.clearance_rate,
                    summary.houses_sold,
                    summary.units_sold,
                ))
                return True
            except sqlite3.Error as e:
                logger.error(f"Failed to save summary: {e}")
                return False

    def get_summaries_by_week(self, week: str) -> List[Dict[str, Any]]:
        """Get all suburb summaries for a week."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM weekly_summaries
                WHERE week = ?
                ORDER BY suburb
            """, (week,))

            return [dict(row) for row in cursor.fetchall()]

    def get_available_weeks(self) -> List[str]:
        """Get list of all weeks with data."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT collection_week
                FROM auction_results
                WHERE collection_week IS NOT NULL
                ORDER BY collection_week DESC
            """)
            return [row[0] for row in cursor.fetchall()]

    def get_statistics(self) -> Dict[str, Any]:
        """Get overall database statistics."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            stats = {}

            cursor.execute("SELECT COUNT(*) FROM auction_results")
            stats["total_results"] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(DISTINCT suburb) FROM auction_results")
            stats["unique_suburbs"] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(DISTINCT collection_week) FROM auction_results")
            stats["weeks_collected"] = cursor.fetchone()[0]

            cursor.execute("""
                SELECT MIN(auction_date), MAX(auction_date)
                FROM auction_results
            """)
            row = cursor.fetchone()
            stats["date_range"] = {"min": row[0], "max": row[1]}

            return stats

    def start_collection_run(self, week: str) -> int:
        """Start a new collection run and return its ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO collection_runs (week, status)
                VALUES (?, 'running')
            """, (week,))
            return cursor.lastrowid

    def complete_collection_run(
        self, run_id: int, total_results: int, suburbs: int, errors: int = 0
    ):
        """Mark a collection run as complete."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE collection_runs
                SET completed_at = CURRENT_TIMESTAMP,
                    total_results = ?,
                    suburbs_scraped = ?,
                    errors = ?,
                    status = 'completed'
                WHERE id = ?
            """, (total_results, suburbs, errors, run_id))


def export_to_csv(
    results: List[AuctionResult],
    filepath: Path,
    include_header: bool = True
) -> Path:
    """
    Export auction results to CSV file.

    Args:
        results: List of AuctionResult objects
        filepath: Output file path
        include_header: Whether to include header row

    Returns:
        Path to created file
    """
    fieldnames = [
        "id", "address", "suburb", "postcode", "state", "region",
        "property_type", "bedrooms", "bathrooms", "parking",
        "auction_date", "outcome", "sold_price",
        "agent_name", "agency_name", "source_url", "collection_week"
    ]

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        if include_header:
            writer.writeheader()

        for result in results:
            row = {
                "id": result.id,
                "address": result.address,
                "suburb": result.suburb,
                "postcode": result.postcode,
                "state": result.state,
                "region": result.region,
                "property_type": result.property_type.value,
                "bedrooms": result.bedrooms,
                "bathrooms": result.bathrooms,
                "parking": result.parking,
                "auction_date": result.auction_date.isoformat() if result.auction_date else "",
                "outcome": result.outcome.value,
                "sold_price": result.sold_price or "",
                "agent_name": result.agent_name or "",
                "agency_name": result.agency_name or "",
                "source_url": result.source_url or "",
                "collection_week": result.collection_week or "",
            }
            writer.writerow(row)

    logger.info(f"Exported {len(results)} results to {filepath}")
    return filepath


def export_to_excel(
    results: List[AuctionResult],
    filepath: Path,
    include_summaries: bool = True
) -> Path:
    """
    Export auction results to Excel file with multiple sheets.

    Requires: openpyxl

    Args:
        results: List of AuctionResult objects
        filepath: Output file path
        include_summaries: Include summary sheets

    Returns:
        Path to created file
    """
    try:
        import pandas as pd
    except ImportError:
        raise ImportError("pandas required for Excel export. Run: pip install pandas openpyxl")

    # Convert results to DataFrame
    data = [r.to_dict() for r in results]
    df = pd.DataFrame(data)

    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        # Main results sheet
        df.to_excel(writer, sheet_name="Auction Results", index=False)

        if include_summaries and not df.empty:
            # Summary by suburb
            suburb_summary = df.groupby(["suburb", "postcode"]).agg({
                "id": "count",
                "sold_price": ["mean", "median", "min", "max"],
            }).round(0)
            suburb_summary.columns = ["count", "avg_price", "median_price", "min_price", "max_price"]
            suburb_summary.to_excel(writer, sheet_name="By Suburb")

            # Summary by outcome
            outcome_summary = df.groupby("outcome").agg({
                "id": "count",
                "sold_price": "mean",
            }).round(0)
            outcome_summary.columns = ["count", "avg_price"]
            outcome_summary.to_excel(writer, sheet_name="By Outcome")

    logger.info(f"Exported {len(results)} results to {filepath}")
    return filepath
