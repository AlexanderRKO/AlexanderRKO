"""
Main runner script for NSW Auction Results Scraper

This is the entry point for running the weekly scraping job.
"""
import sys
import logging
import argparse
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import BASE_DIR, LOG_LEVEL
from src.scraper import AuctionScraper, create_scraper
from src.storage import Database, CSVExporter
from src.aggregator import AuctionAggregator, generate_weekly_report

# Set up logging
log_dir = BASE_DIR / "logs"
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / "scraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def get_week_ending() -> date:
    """Get the Saturday date for the current auction week."""
    today = date.today()
    days_since_saturday = (today.weekday() + 2) % 7
    return today - timedelta(days=days_since_saturday)


def run_scrape(
    use_selenium: bool = False,
    limit: Optional[int] = None,
    export_csv: bool = True
) -> dict:
    """
    Run the weekly scraping job.

    Args:
        use_selenium: Whether to use Selenium for JS rendering
        limit: Optional limit on suburbs to scrape (for testing)
        export_csv: Whether to export results to CSV

    Returns:
        Dictionary with scraping results summary
    """
    week_ending = get_week_ending()
    logger.info(f"Starting scrape for week ending {week_ending}")

    # Initialize components
    db = Database()
    scraper = create_scraper(use_selenium)
    exporter = CSVExporter()

    # Log scrape start
    conn = db._get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO scrape_runs (week_ending, status)
        VALUES (?, 'running')
    """, (week_ending.isoformat(),))
    run_id = cursor.lastrowid
    conn.commit()
    conn.close()

    try:
        # Scrape all suburbs
        summaries, results = scraper.scrape_all_suburbs(limit=limit)

        # Save to database
        if summaries:
            db.save_suburb_summaries(summaries)
        if results:
            db.save_auction_results(results)

        # Export to CSV
        exports = {}
        if export_csv and (summaries or results):
            exports = exporter.export_weekly_report(week_ending, db)

        # Generate aggregations
        aggregator = AuctionAggregator(db)
        weekly_data = aggregator.aggregate_week(week_ending)

        # Generate report
        report = generate_weekly_report(db, week_ending)
        report_path = BASE_DIR / "data" / "processed" / f"weekly_report_{week_ending}.txt"
        report_path.write_text(report)
        logger.info(f"Weekly report saved to {report_path}")

        # Update scrape run status
        conn = db._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE scrape_runs
            SET completed_at = ?, suburbs_scraped = ?, results_collected = ?, status = 'completed'
            WHERE id = ?
        """, (datetime.now().isoformat(), len(summaries), len(results), run_id))
        conn.commit()
        conn.close()

        result = {
            'week_ending': week_ending,
            'suburbs_scraped': len(summaries),
            'results_collected': len(results),
            'exports': exports,
            'status': 'completed'
        }

        logger.info(f"Scrape completed: {result}")
        return result

    except Exception as e:
        logger.error(f"Scrape failed: {e}", exc_info=True)

        # Update scrape run status
        conn = db._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE scrape_runs
            SET completed_at = ?, status = 'failed', error_message = ?
            WHERE id = ?
        """, (datetime.now().isoformat(), str(e), run_id))
        conn.commit()
        conn.close()

        return {
            'week_ending': week_ending,
            'status': 'failed',
            'error': str(e)
        }


def view_report(week_ending: Optional[date] = None):
    """
    View the report for a specific week.

    Args:
        week_ending: The week to view. Uses most recent if not provided.
    """
    db = Database()

    if week_ending is None:
        weeks = db.get_available_weeks()
        if not weeks:
            print("No data available. Run a scrape first.")
            return
        week_ending = weeks[0]

    report = generate_weekly_report(db, week_ending)
    print(report)


def list_weeks():
    """List all available weeks in the database."""
    db = Database()
    weeks = db.get_available_weeks()

    if not weeks:
        print("No data available. Run a scrape first.")
        return

    print("Available weeks:")
    for week in weeks:
        summaries = db.get_suburb_summaries_by_week(week)
        print(f"  - {week} ({len(summaries)} suburbs)")


def main():
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description='NSW Auction Results Scraper',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python runner.py scrape              # Run weekly scrape
  python runner.py scrape --limit 10   # Test with 10 suburbs
  python runner.py report              # View latest report
  python runner.py report --week 2024-12-07  # View specific week
  python runner.py weeks               # List available weeks
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # Scrape command
    scrape_parser = subparsers.add_parser('scrape', help='Run the weekly scrape')
    scrape_parser.add_argument(
        '--selenium', action='store_true',
        help='Use Selenium for JavaScript rendering'
    )
    scrape_parser.add_argument(
        '--limit', type=int,
        help='Limit number of suburbs to scrape (for testing)'
    )
    scrape_parser.add_argument(
        '--no-csv', action='store_true',
        help='Skip CSV export'
    )

    # Report command
    report_parser = subparsers.add_parser('report', help='View weekly report')
    report_parser.add_argument(
        '--week', type=str,
        help='Week ending date (YYYY-MM-DD)'
    )

    # Weeks command
    subparsers.add_parser('weeks', help='List available weeks')

    # Test command
    test_parser = subparsers.add_parser('test', help='Test the scraper')
    test_parser.add_argument(
        '--url', type=str,
        help='Test fetching a specific URL'
    )

    args = parser.parse_args()

    if args.command == 'scrape':
        result = run_scrape(
            use_selenium=args.selenium,
            limit=args.limit,
            export_csv=not args.no_csv
        )
        print(f"\nScrape completed: {result['status']}")
        if result['status'] == 'completed':
            print(f"  Suburbs: {result['suburbs_scraped']}")
            print(f"  Results: {result['results_collected']}")

    elif args.command == 'report':
        week = None
        if args.week:
            week = date.fromisoformat(args.week)
        view_report(week)

    elif args.command == 'weeks':
        list_weeks()

    elif args.command == 'test':
        print("Testing scraper...")
        scraper = AuctionScraper()
        suburbs = scraper.get_suburb_list()
        print(f"Found {len(suburbs)} suburbs")
        if suburbs and args.url:
            summary, results = scraper.get_suburb_results(args.url)
            print(f"Summary: {summary}")
            print(f"Results: {len(results)}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
