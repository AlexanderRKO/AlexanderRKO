"""
Main runner script for NSW Auction Results - Personal Tracker

Run your weekly auction check for tracked postcodes.
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
from config.my_postcodes import get_tracked_suburbs, validate_config, TRACKED_POSTCODES
from src.scraper import AuctionScraper, create_scraper
from src.storage import Database, CSVExporter
from src.aggregator import AuctionAggregator, generate_weekly_report

# Set up logging
log_dir = BASE_DIR / "logs"
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(levelname)s - %(message)s',
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


def run_scrape(export_csv: bool = True) -> dict:
    """
    Run the weekly scrape for YOUR tracked postcodes only.

    Args:
        export_csv: Whether to export results to CSV

    Returns:
        Dictionary with results summary
    """
    # Check configuration first
    if not validate_config():
        return {
            'status': 'error',
            'error': 'No postcodes configured. Edit config/my_postcodes.py first.'
        }

    week_ending = get_week_ending()
    suburbs = get_tracked_suburbs()

    logger.info("=" * 50)
    logger.info("NSW Auction Results - Weekly Check")
    logger.info("=" * 50)
    logger.info(f"Week ending: {week_ending}")
    logger.info(f"Tracking {len(suburbs)} suburb(s)")
    logger.info("")

    # Initialize
    db = Database()
    scraper = create_scraper()
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
        # Scrape only YOUR tracked suburbs
        summaries, results = scraper.scrape_my_suburbs()

        # Save to database
        if summaries:
            db.save_suburb_summaries(summaries)
        if results:
            db.save_auction_results(results)

        # Export to CSV
        exports = {}
        if export_csv and (summaries or results):
            exports = exporter.export_weekly_report(week_ending, db)

        # Update scrape run
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

        logger.info("")
        logger.info("=" * 50)
        logger.info("Weekly check complete!")
        logger.info(f"  Suburbs with data: {len(summaries)}/{len(suburbs)}")
        logger.info(f"  Individual results: {len(results)}")
        logger.info("=" * 50)

        return result

    except Exception as e:
        logger.error(f"Scrape failed: {e}", exc_info=True)

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


def show_config():
    """Show current configuration."""
    print("\nNSW Auction Results - Configuration")
    print("=" * 40)

    if not TRACKED_POSTCODES:
        print("\nNo postcodes configured!")
        print("\nEdit config/my_postcodes.py to add suburbs.")
        print("Example:")
        print('  TRACKED_POSTCODES = {')
        print('      "2021": "paddington",')
        print('      "2026": "bondi",')
        print('  }')
        return

    suburbs = get_tracked_suburbs()
    print(f"\nTracking {len(suburbs)} suburb(s):\n")

    for s in suburbs:
        print(f"  {s['suburb']:20} ({s['postcode']}) - {s['url']}")


def view_report(week_ending: Optional[date] = None):
    """View the report for a specific week."""
    db = Database()

    if week_ending is None:
        weeks = db.get_available_weeks()
        if not weeks:
            print("No data available yet. Run 'python runner.py scrape' first.")
            return
        week_ending = weeks[0]

    report = generate_weekly_report(db, week_ending)
    print(report)


def list_weeks():
    """List all weeks with data."""
    db = Database()
    weeks = db.get_available_weeks()

    if not weeks:
        print("No data collected yet.")
        print("Run 'python runner.py scrape' to collect your first week of data.")
        return

    print("\nWeeks with data:")
    print("-" * 40)
    for week in weeks:
        summaries = db.get_suburb_summaries_by_week(week)
        print(f"  {week}  ({len(summaries)} suburbs)")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='NSW Auction Results - Personal Tracker',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  config   Show your tracked postcodes
  scrape   Run weekly auction check (for YOUR postcodes only)
  report   View latest weekly report
  weeks    List all weeks with data

Examples:
  python runner.py config               # See what you're tracking
  python runner.py scrape               # Run weekly check
  python runner.py report               # View latest report
  python runner.py report --week 2024-12-07

First time? Edit config/my_postcodes.py to add your suburbs.
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Command')

    # Config command
    subparsers.add_parser('config', help='Show tracked postcodes')

    # Scrape command
    scrape_parser = subparsers.add_parser('scrape', help='Run weekly check')
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

    args = parser.parse_args()

    if args.command == 'config':
        show_config()

    elif args.command == 'scrape':
        result = run_scrape(export_csv=not args.no_csv)
        if result['status'] == 'error':
            print(f"\nError: {result['error']}")
            sys.exit(1)

    elif args.command == 'report':
        week = None
        if args.week:
            week = date.fromisoformat(args.week)
        view_report(week)

    elif args.command == 'weeks':
        list_weeks()

    else:
        # Default: show help
        parser.print_help()
        print("\n" + "=" * 50)
        print("Quick start:")
        print("  1. Edit config/my_postcodes.py to add your suburbs")
        print("  2. Run: python runner.py scrape")
        print("=" * 50)


if __name__ == "__main__":
    main()
