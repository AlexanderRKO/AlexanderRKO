"""
Weekly scheduler for automated auction data collection.

Provides multiple scheduling options:
1. Python schedule library (simple)
2. APScheduler (advanced)
3. Cron job generator (system-level)
4. GitHub Actions workflow generator
"""

import logging
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional, Callable, List
import json

from ..config import (
    COLLECTION_DAY,
    COLLECTION_TIME,
    DATA_DIR,
    RAW_DATA_DIR,
    PROCESSED_DATA_DIR,
    PREFERRED_POSTCODES,
)
from ..scrapers import RealEstateAuctionScraper
from ..storage import AuctionDatabase, export_to_csv
from ..aggregator import AuctionAnalyzer, generate_weekly_report

logger = logging.getLogger(__name__)


class WeeklyCollector:
    """
    Manages weekly auction data collection.

    Usage:
        collector = WeeklyCollector()
        collector.run_collection()  # Run immediately
        collector.schedule_weekly()  # Schedule for every Sunday
    """

    def __init__(
        self,
        db: Optional[AuctionDatabase] = None,
        on_complete: Optional[Callable] = None,
    ):
        self.db = db or AuctionDatabase()
        self.on_complete = on_complete

    def run_collection(
        self,
        postcodes: Optional[list] = None,
        max_suburbs: Optional[int] = None,
        save_raw: bool = True,
    ) -> dict:
        """
        Run the full collection process.

        Args:
            postcodes: List of postcodes to collect (RECOMMENDED, max 10).
                      If None, uses PREFERRED_POSTCODES from config.
                      If empty list, falls back to max_suburbs limit.
            max_suburbs: Limit number of suburbs (fallback if no postcodes)
            save_raw: Save raw JSON data to file

        Returns:
            Collection summary dictionary
        """
        week = date.today().strftime("%Y-W%W")
        started_at = datetime.now()

        logger.info(f"Starting collection for week {week}")

        # Initialize database
        self.db.initialize()
        run_id = self.db.start_collection_run(week)

        results = []
        errors = 0
        suburbs_scraped = 0

        # Use postcodes if provided, otherwise fall back to config or max_suburbs
        use_postcodes = postcodes if postcodes is not None else PREFERRED_POSTCODES

        try:
            with RealEstateAuctionScraper() as scraper:
                # RECOMMENDED: Use postcode filtering (API-friendly)
                if use_postcodes:
                    logger.info(f"Using postcode filter: {use_postcodes}")
                    suburb_urls = scraper.get_urls_for_postcodes(use_postcodes)
                else:
                    # Fallback: get all suburbs (not recommended)
                    logger.warning(
                        "No postcodes specified - consider using postcodes "
                        "to be API-friendly"
                    )
                    suburb_urls = scraper.get_suburb_urls("nsw")
                    if max_suburbs:
                        suburb_urls = suburb_urls[:max_suburbs]

                logger.info(f"Will scrape {len(suburb_urls)} suburbs")

                for i, url in enumerate(suburb_urls, 1):
                    try:
                        suburb_results = scraper.scrape_suburb_page(url)
                        results.extend(suburb_results)
                        suburbs_scraped += 1

                        if i % 5 == 0 or i == len(suburb_urls):
                            logger.info(
                                f"Progress: {i}/{len(suburb_urls)} suburbs, "
                                f"{len(results)} results"
                            )

                    except Exception as e:
                        logger.error(f"Error scraping {url}: {e}")
                        errors += 1

            # Save to database
            inserted, duplicates = self.db.insert_results(results)

            # Save raw data to file
            if save_raw and results:
                raw_file = RAW_DATA_DIR / f"auction_results_{week}.json"
                with open(raw_file, "w") as f:
                    json.dump([r.to_dict() for r in results], f, indent=2)
                logger.info(f"Saved raw data to {raw_file}")

            # Generate analysis
            analyzer = AuctionAnalyzer(results)
            report = generate_weekly_report(results, week)

            # Save report
            report_file = PROCESSED_DATA_DIR / f"weekly_report_{week}.json"
            with open(report_file, "w") as f:
                json.dump(report, f, indent=2)
            logger.info(f"Saved report to {report_file}")

            # Export CSV
            csv_file = PROCESSED_DATA_DIR / f"auction_results_{week}.csv"
            export_to_csv(results, csv_file)

            # Save suburb summaries to database
            for summary in analyzer.group_by_suburb().values():
                self.db.save_summary(summary)

            # Complete the run
            self.db.complete_collection_run(
                run_id, len(results), suburbs_scraped, errors
            )

            summary = {
                "week": week,
                "started_at": started_at.isoformat(),
                "completed_at": datetime.now().isoformat(),
                "duration_seconds": (datetime.now() - started_at).total_seconds(),
                "suburbs_scraped": suburbs_scraped,
                "total_results": len(results),
                "inserted": inserted,
                "duplicates": duplicates,
                "errors": errors,
                "clearance_rate": analyzer.get_clearance_rate(),
                "median_price": analyzer.get_price_stats().get("median"),
                "files": {
                    "raw": str(raw_file) if save_raw else None,
                    "report": str(report_file),
                    "csv": str(csv_file),
                },
            }

            logger.info(
                f"Collection complete: {len(results)} results from "
                f"{suburbs_scraped} suburbs in "
                f"{summary['duration_seconds']:.1f}s"
            )

            if self.on_complete:
                self.on_complete(summary)

            return summary

        except Exception as e:
            logger.error(f"Collection failed: {e}")
            raise

    def schedule_weekly(self, day: str = COLLECTION_DAY, time: str = COLLECTION_TIME):
        """
        Schedule weekly collection using the schedule library.

        Requires: schedule

        Args:
            day: Day of week (e.g., "sunday")
            time: Time to run (e.g., "06:00")
        """
        try:
            import schedule
        except ImportError:
            raise ImportError(
                "schedule library required. Run: pip install schedule"
            )

        # Map day name to schedule method
        day_methods = {
            "monday": schedule.every().monday,
            "tuesday": schedule.every().tuesday,
            "wednesday": schedule.every().wednesday,
            "thursday": schedule.every().thursday,
            "friday": schedule.every().friday,
            "saturday": schedule.every().saturday,
            "sunday": schedule.every().sunday,
        }

        day_method = day_methods.get(day.lower())
        if not day_method:
            raise ValueError(f"Invalid day: {day}")

        day_method.at(time).do(self.run_collection)

        logger.info(f"Scheduled weekly collection for {day} at {time}")

        # Run the scheduler loop
        while True:
            schedule.run_pending()
            time.sleep(60)

    def generate_cron_command(self) -> str:
        """
        Generate cron command for system scheduling.

        Returns:
            Cron command string
        """
        # Parse collection time
        hour, minute = COLLECTION_TIME.split(":")

        # Sunday = 0 in cron
        day_map = {
            "sunday": 0,
            "monday": 1,
            "tuesday": 2,
            "wednesday": 3,
            "thursday": 4,
            "friday": 5,
            "saturday": 6,
        }
        day_num = day_map.get(COLLECTION_DAY.lower(), 0)

        # Generate command
        script_path = Path(__file__).parent.parent / "main.py"
        python_path = "python3"  # Adjust as needed

        cron_line = (
            f"{minute} {hour} * * {day_num} "
            f"cd {DATA_DIR.parent} && {python_path} -m nsw_auction_tracker collect"
        )

        return cron_line


def run_scheduled_collection():
    """Entry point for scheduled collection."""
    collector = WeeklyCollector()
    return collector.run_collection()


def generate_github_actions_workflow() -> str:
    """
    Generate GitHub Actions workflow for automated collection.

    Returns:
        YAML workflow content
    """
    workflow = """# GitHub Actions workflow for weekly auction data collection
name: Weekly Auction Collection

on:
  schedule:
    # Run every Sunday at 6:00 AM AEST (Saturday 20:00 UTC)
    - cron: '0 20 * * 6'
  workflow_dispatch:  # Allow manual trigger

jobs:
  collect:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run collection
        run: |
          python -m nsw_auction_tracker collect --max-suburbs 50
        env:
          PYTHONUNBUFFERED: 1

      - name: Upload results
        uses: actions/upload-artifact@v4
        with:
          name: auction-results-${{ github.run_number }}
          path: |
            data/processed/*.csv
            data/processed/*.json
          retention-days: 90

      - name: Commit data to repository
        run: |
          git config --local user.email "action@github.com"
          git config --local user.name "GitHub Action"
          git add data/
          git diff --quiet && git diff --staged --quiet || git commit -m "Add auction data for week $(date +%Y-W%W)"
          git push
"""
    return workflow


def generate_systemd_service() -> tuple:
    """
    Generate systemd service and timer files for Linux systems.

    Returns:
        Tuple of (service_content, timer_content)
    """
    service = """[Unit]
Description=NSW Auction Data Collector
After=network.target

[Service]
Type=oneshot
WorkingDirectory=/path/to/nsw_auction_tracker
ExecStart=/usr/bin/python3 -m nsw_auction_tracker collect
User=your_username
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""

    timer = """[Unit]
Description=Weekly NSW Auction Data Collection

[Timer]
OnCalendar=Sun *-*-* 06:00:00
Persistent=true

[Install]
WantedBy=timers.target
"""

    return service, timer
