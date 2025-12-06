"""
Data storage module for NSW Auction Results

Provides SQLite database storage and CSV export functionality.
"""
import csv
import sqlite3
import logging
from datetime import datetime, date
from pathlib import Path
from typing import List, Optional, Dict, Any

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import (
    DATABASE_PATH, RAW_DATA_DIR, PROCESSED_DATA_DIR, ARCHIVE_DIR,
    CSV_DATE_FORMAT, EXPORT_FILENAME_TEMPLATE
)
from src.models import AuctionResult, SuburbSummary, WeeklySummary, RegionalSummary

logger = logging.getLogger(__name__)


class Database:
    """
    SQLite database handler for auction results.

    Provides methods for storing and retrieving auction data with
    support for historical tracking.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file. Uses default if not provided.
        """
        self.db_path = db_path or DATABASE_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_database(self):
        """Initialize database tables if they don't exist."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Auction results table - individual property auction outcomes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS auction_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                address TEXT NOT NULL,
                suburb TEXT NOT NULL,
                postcode TEXT NOT NULL,
                state TEXT DEFAULT 'NSW',
                property_type TEXT,
                bedrooms INTEGER,
                bathrooms INTEGER,
                parking INTEGER,
                price INTEGER,
                price_undisclosed BOOLEAN DEFAULT 0,
                outcome TEXT NOT NULL,
                agent TEXT,
                auction_date DATE,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                listing_url TEXT,
                UNIQUE(address, suburb, auction_date)
            )
        """)

        # Suburb summaries table - weekly aggregates per suburb
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS suburb_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                suburb TEXT NOT NULL,
                postcode TEXT NOT NULL,
                region TEXT NOT NULL,
                week_ending DATE NOT NULL,
                total_auctions INTEGER DEFAULT 0,
                total_sold INTEGER DEFAULT 0,
                sold_at_auction INTEGER DEFAULT 0,
                sold_prior INTEGER DEFAULT 0,
                sold_after INTEGER DEFAULT 0,
                passed_in INTEGER DEFAULT 0,
                withdrawn INTEGER DEFAULT 0,
                clearance_rate REAL,
                median_price INTEGER,
                total_sales_value INTEGER,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(suburb, postcode, week_ending)
            )
        """)

        # Regional summaries table - weekly aggregates per region
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS regional_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                region TEXT NOT NULL,
                week_ending DATE NOT NULL,
                suburbs_count INTEGER DEFAULT 0,
                total_auctions INTEGER DEFAULT 0,
                total_sold INTEGER DEFAULT 0,
                clearance_rate REAL,
                median_price INTEGER,
                total_sales_value INTEGER,
                UNIQUE(region, week_ending)
            )
        """)

        # Weekly state-wide summaries
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS weekly_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                week_ending DATE NOT NULL UNIQUE,
                total_auctions INTEGER DEFAULT 0,
                total_sold INTEGER DEFAULT 0,
                clearance_rate REAL,
                median_price INTEGER,
                total_sales_value INTEGER,
                sydney_clearance_rate REAL,
                regional_clearance_rate REAL,
                suburbs_with_auctions INTEGER DEFAULT 0
            )
        """)

        # Scraping runs log
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scrape_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                week_ending DATE,
                suburbs_scraped INTEGER DEFAULT 0,
                results_collected INTEGER DEFAULT 0,
                status TEXT DEFAULT 'running',
                error_message TEXT
            )
        """)

        # Create indexes for common queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_results_suburb ON auction_results(suburb)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_results_postcode ON auction_results(postcode)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_results_date ON auction_results(auction_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_summaries_week ON suburb_summaries(week_ending)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_summaries_region ON suburb_summaries(region)")

        conn.commit()
        conn.close()
        logger.info(f"Database initialized at {self.db_path}")

    def save_auction_result(self, result: AuctionResult) -> int:
        """
        Save a single auction result to the database.

        Args:
            result: AuctionResult to save

        Returns:
            ID of the inserted/updated row
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO auction_results
            (address, suburb, postcode, state, property_type, bedrooms, bathrooms,
             parking, price, price_undisclosed, outcome, agent, auction_date,
             scraped_at, listing_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            result.address,
            result.suburb,
            result.postcode,
            result.state,
            result.property_type.value if result.property_type else None,
            result.bedrooms,
            result.bathrooms,
            result.parking,
            result.price,
            result.price_undisclosed,
            result.outcome.value,
            result.agent,
            result.auction_date.isoformat() if result.auction_date else None,
            result.scraped_at.isoformat(),
            result.listing_url
        ))

        row_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return row_id

    def save_auction_results(self, results: List[AuctionResult]) -> int:
        """
        Save multiple auction results to the database.

        Args:
            results: List of AuctionResult objects to save

        Returns:
            Number of rows saved
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        for result in results:
            cursor.execute("""
                INSERT OR REPLACE INTO auction_results
                (address, suburb, postcode, state, property_type, bedrooms, bathrooms,
                 parking, price, price_undisclosed, outcome, agent, auction_date,
                 scraped_at, listing_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result.address,
                result.suburb,
                result.postcode,
                result.state,
                result.property_type.value if result.property_type else None,
                result.bedrooms,
                result.bathrooms,
                result.parking,
                result.price,
                result.price_undisclosed,
                result.outcome.value,
                result.agent,
                result.auction_date.isoformat() if result.auction_date else None,
                result.scraped_at.isoformat(),
                result.listing_url
            ))

        conn.commit()
        conn.close()
        logger.info(f"Saved {len(results)} auction results")
        return len(results)

    def save_suburb_summary(self, summary: SuburbSummary) -> int:
        """Save a suburb summary to the database."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO suburb_summaries
            (suburb, postcode, region, week_ending, total_auctions, total_sold,
             sold_at_auction, sold_prior, sold_after, passed_in, withdrawn,
             clearance_rate, median_price, total_sales_value, scraped_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            summary.suburb,
            summary.postcode,
            summary.region,
            summary.week_ending.isoformat(),
            summary.total_auctions,
            summary.total_sold,
            summary.sold_at_auction,
            summary.sold_prior,
            summary.sold_after,
            summary.passed_in,
            summary.withdrawn,
            summary.clearance_rate,
            summary.median_price,
            summary.total_sales_value,
            summary.scraped_at.isoformat()
        ))

        row_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return row_id

    def save_suburb_summaries(self, summaries: List[SuburbSummary]) -> int:
        """Save multiple suburb summaries to the database."""
        for summary in summaries:
            self.save_suburb_summary(summary)
        logger.info(f"Saved {len(summaries)} suburb summaries")
        return len(summaries)

    def get_results_by_week(self, week_ending: date) -> List[AuctionResult]:
        """Get all auction results for a specific week."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM auction_results WHERE auction_date = ?
        """, (week_ending.isoformat(),))

        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_auction_result(row) for row in rows]

    def get_results_by_suburb(self, suburb: str, postcode: Optional[str] = None) -> List[AuctionResult]:
        """Get all auction results for a specific suburb."""
        conn = self._get_connection()
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

        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_auction_result(row) for row in rows]

    def get_suburb_summaries_by_week(self, week_ending: date) -> List[SuburbSummary]:
        """Get all suburb summaries for a specific week."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM suburb_summaries WHERE week_ending = ?
        """, (week_ending.isoformat(),))

        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_suburb_summary(row) for row in rows]

    def get_available_weeks(self) -> List[date]:
        """Get list of all weeks with data."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT DISTINCT week_ending FROM suburb_summaries
            ORDER BY week_ending DESC
        """)

        weeks = [date.fromisoformat(row['week_ending']) for row in cursor.fetchall()]
        conn.close()
        return weeks

    def _row_to_auction_result(self, row: sqlite3.Row) -> AuctionResult:
        """Convert database row to AuctionResult object."""
        from src.models import PropertyType, AuctionOutcome

        return AuctionResult(
            address=row['address'],
            suburb=row['suburb'],
            postcode=row['postcode'],
            state=row['state'],
            property_type=PropertyType(row['property_type']) if row['property_type'] else None,
            bedrooms=row['bedrooms'],
            bathrooms=row['bathrooms'],
            parking=row['parking'],
            price=row['price'],
            price_undisclosed=bool(row['price_undisclosed']),
            outcome=AuctionOutcome(row['outcome']),
            agent=row['agent'],
            auction_date=date.fromisoformat(row['auction_date']) if row['auction_date'] else None,
            scraped_at=datetime.fromisoformat(row['scraped_at']),
            listing_url=row['listing_url']
        )

    def _row_to_suburb_summary(self, row: sqlite3.Row) -> SuburbSummary:
        """Convert database row to SuburbSummary object."""
        return SuburbSummary(
            suburb=row['suburb'],
            postcode=row['postcode'],
            region=row['region'],
            week_ending=date.fromisoformat(row['week_ending']),
            total_auctions=row['total_auctions'],
            total_sold=row['total_sold'],
            sold_at_auction=row['sold_at_auction'],
            sold_prior=row['sold_prior'],
            sold_after=row['sold_after'],
            passed_in=row['passed_in'],
            withdrawn=row['withdrawn'],
            clearance_rate=row['clearance_rate'],
            median_price=row['median_price'],
            total_sales_value=row['total_sales_value'],
            scraped_at=datetime.fromisoformat(row['scraped_at'])
        )


class CSVExporter:
    """
    CSV export functionality for auction data.

    Exports data to CSV files for external analysis and archival.
    """

    def __init__(self, output_dir: Optional[Path] = None):
        """
        Initialize CSV exporter.

        Args:
            output_dir: Directory for CSV exports. Uses default if not provided.
        """
        self.output_dir = output_dir or PROCESSED_DATA_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_results(self, results: List[AuctionResult], filename: Optional[str] = None) -> Path:
        """
        Export auction results to CSV.

        Args:
            results: List of AuctionResult objects
            filename: Optional filename. Auto-generated if not provided.

        Returns:
            Path to the created CSV file
        """
        if not filename:
            date_str = datetime.now().strftime(CSV_DATE_FORMAT)
            filename = EXPORT_FILENAME_TEMPLATE.format(date=date_str)

        filepath = self.output_dir / filename

        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            if not results:
                logger.warning("No results to export")
                return filepath

            fieldnames = [
                'address', 'suburb', 'postcode', 'state', 'property_type',
                'bedrooms', 'bathrooms', 'parking', 'price', 'price_undisclosed',
                'outcome', 'agent', 'auction_date', 'scraped_at', 'listing_url'
            ]

            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for result in results:
                row = result.to_dict()
                # Convert enum values to strings
                row['property_type'] = row['property_type'] if row['property_type'] else ''
                writer.writerow(row)

        logger.info(f"Exported {len(results)} results to {filepath}")
        return filepath

    def export_summaries(self, summaries: List[SuburbSummary], filename: Optional[str] = None) -> Path:
        """
        Export suburb summaries to CSV.

        Args:
            summaries: List of SuburbSummary objects
            filename: Optional filename. Auto-generated if not provided.

        Returns:
            Path to the created CSV file
        """
        if not filename:
            date_str = datetime.now().strftime(CSV_DATE_FORMAT)
            filename = f"nsw_suburb_summaries_{date_str}.csv"

        filepath = self.output_dir / filename

        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            if not summaries:
                logger.warning("No summaries to export")
                return filepath

            fieldnames = [
                'suburb', 'postcode', 'region', 'week_ending', 'total_auctions',
                'total_sold', 'sold_at_auction', 'sold_prior', 'sold_after',
                'passed_in', 'withdrawn', 'clearance_rate', 'median_price',
                'total_sales_value', 'scraped_at'
            ]

            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for summary in summaries:
                writer.writerow(summary.to_dict())

        logger.info(f"Exported {len(summaries)} summaries to {filepath}")
        return filepath

    def export_weekly_report(self, week_ending: date, db: Database) -> Dict[str, Path]:
        """
        Generate a complete weekly export package.

        Args:
            week_ending: The week to export
            db: Database instance to fetch data from

        Returns:
            Dictionary mapping export type to file path
        """
        date_str = week_ending.strftime(CSV_DATE_FORMAT)
        exports = {}

        # Export individual results
        results = db.get_results_by_week(week_ending)
        if results:
            exports['results'] = self.export_results(
                results,
                f"nsw_auction_results_{date_str}.csv"
            )

        # Export suburb summaries
        summaries = db.get_suburb_summaries_by_week(week_ending)
        if summaries:
            exports['summaries'] = self.export_summaries(
                summaries,
                f"nsw_suburb_summaries_{date_str}.csv"
            )

        return exports
