#!/usr/bin/env python3
"""
NSW Auction Tracker - Main Entry Point

Command-line interface for collecting and analyzing NSW auction data.

Usage:
    python -m nsw_auction_tracker collect [--max-suburbs N]
    python -m nsw_auction_tracker analyze --week 2024-W01
    python -m nsw_auction_tracker export --week 2024-W01 --format csv
    python -m nsw_auction_tracker stats
"""

import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path

from .config import ensure_directories, DATA_DIR, PROCESSED_DATA_DIR
from .storage import AuctionDatabase, export_to_csv, export_to_excel
from .scrapers import RealEstateAuctionScraper
from .aggregator import AuctionAnalyzer, generate_weekly_report
from .scheduler import WeeklyCollector


def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(DATA_DIR / "auction_tracker.log"),
        ],
    )


def cmd_collect(args):
    """Run data collection."""
    print(f"Starting auction data collection...")
    print(f"Max suburbs: {args.max_suburbs or 'all'}")

    collector = WeeklyCollector()
    summary = collector.run_collection(
        max_suburbs=args.max_suburbs,
        save_raw=not args.no_raw,
    )

    print("\n" + "=" * 50)
    print("COLLECTION COMPLETE")
    print("=" * 50)
    print(f"Week: {summary['week']}")
    print(f"Duration: {summary['duration_seconds']:.1f} seconds")
    print(f"Suburbs scraped: {summary['suburbs_scraped']}")
    print(f"Total results: {summary['total_results']}")
    print(f"Clearance rate: {summary['clearance_rate']:.1f}%")
    if summary['median_price']:
        print(f"Median price: ${summary['median_price']:,}")
    print(f"\nFiles saved:")
    for name, path in summary['files'].items():
        if path:
            print(f"  {name}: {path}")


def cmd_analyze(args):
    """Analyze collected data."""
    db = AuctionDatabase()
    db.initialize()

    week = args.week or date.today().strftime("%Y-W%W")
    print(f"Analyzing data for week: {week}")

    results = db.get_results_by_week(week)

    if not results:
        print(f"No data found for week {week}")
        available = db.get_available_weeks()
        if available:
            print(f"Available weeks: {', '.join(available[:10])}")
        return

    report = generate_weekly_report(results, week)

    print("\n" + "=" * 50)
    print(f"WEEKLY REPORT: {week}")
    print("=" * 50)

    summary = report["summary"]
    print(f"\nTotal auctions: {summary['total_auctions']}")
    print(f"Clearance rate: {summary['clearance_rate']:.1f}%")

    price_stats = summary["price_stats"]
    if price_stats["median"]:
        print(f"\nPrice Statistics:")
        print(f"  Median: ${price_stats['median']:,}")
        print(f"  Average: ${price_stats['average']:,}")
        print(f"  Range: ${price_stats['min']:,} - ${price_stats['max']:,}")
        print(f"  Total value: ${price_stats['total']:,}")

    print(f"\nOutcome Distribution:")
    for outcome, count in report["by_outcome"].items():
        print(f"  {outcome}: {count}")

    print(f"\nTop 5 Suburbs by Volume:")
    for suburb, count in report["top_suburbs_by_volume"][:5]:
        print(f"  {suburb}: {count} auctions")

    print(f"\nTop 5 Suburbs by Price:")
    for suburb, price in report["top_suburbs_by_price"][:5]:
        print(f"  {suburb}: ${price:,}")

    # Save report
    if args.save:
        report_file = PROCESSED_DATA_DIR / f"analysis_{week}.json"
        with open(report_file, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\nReport saved to: {report_file}")


def cmd_export(args):
    """Export data to file."""
    db = AuctionDatabase()
    db.initialize()

    week = args.week
    output_format = args.format

    if week:
        results = db.get_results_by_week(week)
        filename = f"auction_export_{week}"
    else:
        # Get all results
        weeks = db.get_available_weeks()
        results = []
        for w in weeks:
            results.extend(db.get_results_by_week(w))
        filename = "auction_export_all"

    if not results:
        print("No data to export")
        return

    output_path = Path(args.output) if args.output else PROCESSED_DATA_DIR

    if output_format == "csv":
        filepath = output_path / f"{filename}.csv"
        export_to_csv(results, filepath)
    elif output_format == "excel":
        filepath = output_path / f"{filename}.xlsx"
        export_to_excel(results, filepath)
    elif output_format == "json":
        filepath = output_path / f"{filename}.json"
        with open(filepath, "w") as f:
            json.dump([r.to_dict() for r in results], f, indent=2)

    print(f"Exported {len(results)} results to {filepath}")


def cmd_stats(args):
    """Show database statistics."""
    db = AuctionDatabase()
    db.initialize()

    stats = db.get_statistics()
    available_weeks = db.get_available_weeks()

    print("\n" + "=" * 50)
    print("DATABASE STATISTICS")
    print("=" * 50)
    print(f"Total results: {stats['total_results']:,}")
    print(f"Unique suburbs: {stats['unique_suburbs']}")
    print(f"Weeks collected: {stats['weeks_collected']}")

    if stats["date_range"]["min"]:
        print(f"Date range: {stats['date_range']['min']} to {stats['date_range']['max']}")

    if available_weeks:
        print(f"\nRecent weeks:")
        for week in available_weeks[:5]:
            week_results = db.get_results_by_week(week)
            analyzer = AuctionAnalyzer(week_results)
            print(
                f"  {week}: {len(week_results)} results, "
                f"{analyzer.get_clearance_rate():.1f}% clearance"
            )


def cmd_suburbs(args):
    """List available suburb URLs."""
    print("Fetching suburb URLs from realestate.com.au...")

    with RealEstateAuctionScraper() as scraper:
        urls = scraper.get_suburb_urls("nsw")

    print(f"\nFound {len(urls)} suburb URLs:")
    for url in urls[:args.limit] if args.limit else urls:
        print(f"  {url}")

    if args.limit and len(urls) > args.limit:
        print(f"\n... and {len(urls) - args.limit} more")


def cmd_test(args):
    """Test scraping a single suburb."""
    print(f"Testing scraper on: {args.url}")

    with RealEstateAuctionScraper() as scraper:
        results = scraper.scrape_suburb_page(args.url)

    print(f"\nFound {len(results)} results:")
    for result in results[:10]:
        print(f"\n  Address: {result.address}")
        print(f"  Suburb: {result.suburb} {result.postcode}")
        print(f"  Outcome: {result.outcome.value}")
        if result.sold_price:
            print(f"  Price: ${result.sold_price:,}")
        if result.bedrooms:
            print(f"  Beds: {result.bedrooms}")


def cmd_setup(args):
    """Set up scheduling."""
    print("Scheduling Options:")
    print("=" * 50)

    collector = WeeklyCollector()

    print("\n1. CRON JOB (Linux/Mac)")
    print("-" * 30)
    print("Add this line to your crontab (crontab -e):")
    print(collector.generate_cron_command())

    print("\n2. GITHUB ACTIONS")
    print("-" * 30)
    print("Create .github/workflows/collect.yml with content from:")
    print("  python -m nsw_auction_tracker setup --github-actions")

    if args.github_actions:
        from .scheduler.weekly_job import generate_github_actions_workflow
        print("\n" + generate_github_actions_workflow())

    print("\n3. SYSTEMD (Linux)")
    print("-" * 30)
    print("See documentation for systemd service setup")


def main():
    """Main entry point."""
    ensure_directories()

    parser = argparse.ArgumentParser(
        description="NSW Auction Tracker - Collect and analyze auction data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Collect command
    collect_parser = subparsers.add_parser(
        "collect",
        help="Run data collection",
    )
    collect_parser.add_argument(
        "--max-suburbs",
        type=int,
        help="Limit number of suburbs to scrape (for testing)",
    )
    collect_parser.add_argument(
        "--no-raw",
        action="store_true",
        help="Don't save raw JSON data",
    )

    # Analyze command
    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Analyze collected data",
    )
    analyze_parser.add_argument(
        "--week",
        help="Week to analyze (e.g., 2024-W01). Defaults to current week.",
    )
    analyze_parser.add_argument(
        "--save",
        action="store_true",
        help="Save analysis report to file",
    )

    # Export command
    export_parser = subparsers.add_parser(
        "export",
        help="Export data to file",
    )
    export_parser.add_argument(
        "--week",
        help="Week to export. If not specified, exports all data.",
    )
    export_parser.add_argument(
        "--format",
        choices=["csv", "excel", "json"],
        default="csv",
        help="Output format (default: csv)",
    )
    export_parser.add_argument(
        "--output",
        help="Output directory or file path",
    )

    # Stats command
    subparsers.add_parser(
        "stats",
        help="Show database statistics",
    )

    # Suburbs command
    suburbs_parser = subparsers.add_parser(
        "suburbs",
        help="List available suburb URLs",
    )
    suburbs_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Limit number of URLs to show",
    )

    # Test command
    test_parser = subparsers.add_parser(
        "test",
        help="Test scraping a single URL",
    )
    test_parser.add_argument(
        "url",
        help="Suburb URL to test",
    )

    # Setup command
    setup_parser = subparsers.add_parser(
        "setup",
        help="Show scheduling setup options",
    )
    setup_parser.add_argument(
        "--github-actions",
        action="store_true",
        help="Output GitHub Actions workflow",
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    if args.command == "collect":
        cmd_collect(args)
    elif args.command == "analyze":
        cmd_analyze(args)
    elif args.command == "export":
        cmd_export(args)
    elif args.command == "stats":
        cmd_stats(args)
    elif args.command == "suburbs":
        cmd_suburbs(args)
    elif args.command == "test":
        cmd_test(args)
    elif args.command == "setup":
        cmd_setup(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
