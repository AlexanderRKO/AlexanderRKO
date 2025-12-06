"""
Aggregation and analysis module for NSW Auction Results

Provides functions for calculating statistics, trends, and generating reports.
"""
import statistics
import logging
from datetime import date, timedelta
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import get_region_for_postcode, NSW_REGIONS
from src.models import (
    AuctionResult, SuburbSummary, RegionalSummary, WeeklySummary, AuctionOutcome
)
from src.storage import Database

logger = logging.getLogger(__name__)


class AuctionAggregator:
    """
    Aggregates and analyzes auction results data.

    Provides methods for calculating clearance rates, median prices,
    trends over time, and regional comparisons.
    """

    def __init__(self, db: Database):
        """
        Initialize aggregator with database connection.

        Args:
            db: Database instance for data access
        """
        self.db = db

    def calculate_suburb_summary(
        self,
        suburb: str,
        postcode: str,
        results: List[AuctionResult]
    ) -> SuburbSummary:
        """
        Calculate summary statistics for a suburb's auction results.

        Args:
            suburb: Suburb name
            postcode: Postcode
            results: List of auction results for the suburb

        Returns:
            SuburbSummary with calculated statistics
        """
        if not results:
            return SuburbSummary(
                suburb=suburb,
                postcode=postcode,
                region=get_region_for_postcode(postcode),
                week_ending=date.today()
            )

        # Count outcomes
        sold = sum(1 for r in results if r.outcome == AuctionOutcome.SOLD)
        sold_prior = sum(1 for r in results if r.outcome == AuctionOutcome.SOLD_PRIOR)
        sold_after = sum(1 for r in results if r.outcome == AuctionOutcome.SOLD_AFTER)
        passed_in = sum(1 for r in results if r.outcome == AuctionOutcome.PASSED_IN)
        withdrawn = sum(1 for r in results if r.outcome == AuctionOutcome.WITHDRAWN)

        total_sold = sold + sold_prior + sold_after
        total_auctions = len(results)

        # Calculate clearance rate (sold / (sold + passed_in))
        clearance_denominator = total_sold + passed_in
        clearance_rate = (total_sold / clearance_denominator * 100) if clearance_denominator > 0 else None

        # Calculate median price (only from disclosed prices)
        prices = [r.price for r in results if r.price and not r.price_undisclosed]
        median_price = int(statistics.median(prices)) if prices else None

        # Total sales value
        total_value = sum(prices) if prices else None

        # Get week ending date from results
        week_ending = results[0].auction_date if results[0].auction_date else date.today()

        return SuburbSummary(
            suburb=suburb,
            postcode=postcode,
            region=get_region_for_postcode(postcode),
            week_ending=week_ending,
            total_auctions=total_auctions,
            total_sold=total_sold,
            sold_at_auction=sold,
            sold_prior=sold_prior,
            sold_after=sold_after,
            passed_in=passed_in,
            withdrawn=withdrawn,
            clearance_rate=round(clearance_rate, 1) if clearance_rate else None,
            median_price=median_price,
            total_sales_value=total_value
        )

    def calculate_regional_summary(
        self,
        region: str,
        summaries: List[SuburbSummary]
    ) -> RegionalSummary:
        """
        Calculate summary statistics for a region.

        Args:
            region: Region name
            summaries: List of suburb summaries in the region

        Returns:
            RegionalSummary with calculated statistics
        """
        if not summaries:
            return RegionalSummary(region=region, week_ending=date.today())

        total_auctions = sum(s.total_auctions for s in summaries)
        total_sold = sum(s.total_sold for s in summaries)

        # Regional clearance rate
        total_passed_in = sum(s.passed_in for s in summaries)
        clearance_denominator = total_sold + total_passed_in
        clearance_rate = (total_sold / clearance_denominator * 100) if clearance_denominator > 0 else None

        # Regional median price (weighted approach would be more accurate)
        # For simplicity, we use median of suburb medians
        median_prices = [s.median_price for s in summaries if s.median_price]
        median_price = int(statistics.median(median_prices)) if median_prices else None

        # Total sales value
        total_value = sum(s.total_sales_value for s in summaries if s.total_sales_value)

        return RegionalSummary(
            region=region,
            week_ending=summaries[0].week_ending,
            suburbs_count=len(summaries),
            total_auctions=total_auctions,
            total_sold=total_sold,
            clearance_rate=round(clearance_rate, 1) if clearance_rate else None,
            median_price=median_price,
            total_sales_value=total_value if total_value > 0 else None
        )

    def calculate_weekly_summary(
        self,
        week_ending: date,
        summaries: List[SuburbSummary]
    ) -> WeeklySummary:
        """
        Calculate state-wide weekly summary.

        Args:
            week_ending: The Saturday date for the week
            summaries: List of all suburb summaries for the week

        Returns:
            WeeklySummary with state-wide statistics
        """
        if not summaries:
            return WeeklySummary(week_ending=week_ending)

        total_auctions = sum(s.total_auctions for s in summaries)
        total_sold = sum(s.total_sold for s in summaries)

        # State-wide clearance rate
        total_passed_in = sum(s.passed_in for s in summaries)
        clearance_denominator = total_sold + total_passed_in
        clearance_rate = (total_sold / clearance_denominator * 100) if clearance_denominator > 0 else None

        # Median price
        median_prices = [s.median_price for s in summaries if s.median_price]
        median_price = int(statistics.median(median_prices)) if median_prices else None

        # Total sales value
        total_value = sum(s.total_sales_value for s in summaries if s.total_sales_value)

        # Sydney vs Regional breakdown
        sydney_regions = [r for r in NSW_REGIONS.keys() if r.startswith('sydney')]
        sydney_summaries = [s for s in summaries if s.region in sydney_regions]
        regional_summaries = [s for s in summaries if s.region not in sydney_regions]

        sydney_sold = sum(s.total_sold for s in sydney_summaries)
        sydney_passed = sum(s.passed_in for s in sydney_summaries)
        sydney_denom = sydney_sold + sydney_passed
        sydney_clearance = (sydney_sold / sydney_denom * 100) if sydney_denom > 0 else None

        regional_sold = sum(s.total_sold for s in regional_summaries)
        regional_passed = sum(s.passed_in for s in regional_summaries)
        regional_denom = regional_sold + regional_passed
        regional_clearance = (regional_sold / regional_denom * 100) if regional_denom > 0 else None

        return WeeklySummary(
            week_ending=week_ending,
            total_auctions=total_auctions,
            total_sold=total_sold,
            clearance_rate=round(clearance_rate, 1) if clearance_rate else None,
            median_price=median_price,
            total_sales_value=total_value if total_value > 0 else None,
            sydney_clearance_rate=round(sydney_clearance, 1) if sydney_clearance else None,
            regional_clearance_rate=round(regional_clearance, 1) if regional_clearance else None,
            suburbs_with_auctions=len(summaries)
        )

    def aggregate_week(self, week_ending: date) -> Dict:
        """
        Generate complete aggregation for a week.

        Args:
            week_ending: The Saturday date for the week

        Returns:
            Dictionary with all aggregated summaries
        """
        # Get suburb summaries from database
        summaries = self.db.get_suburb_summaries_by_week(week_ending)

        if not summaries:
            logger.warning(f"No data found for week ending {week_ending}")
            return {}

        # Group by region
        by_region = defaultdict(list)
        for summary in summaries:
            by_region[summary.region].append(summary)

        # Calculate regional summaries
        regional_summaries = []
        for region, region_summaries in by_region.items():
            regional = self.calculate_regional_summary(region, region_summaries)
            regional_summaries.append(regional)

        # Calculate weekly summary
        weekly = self.calculate_weekly_summary(week_ending, summaries)

        return {
            'week_ending': week_ending,
            'weekly_summary': weekly,
            'regional_summaries': regional_summaries,
            'suburb_summaries': summaries
        }

    def get_clearance_rate_trend(
        self,
        weeks: int = 12,
        region: Optional[str] = None
    ) -> List[Tuple[date, float]]:
        """
        Get clearance rate trend over time.

        Args:
            weeks: Number of weeks to include
            region: Optional region to filter by

        Returns:
            List of (week_ending, clearance_rate) tuples
        """
        available_weeks = self.db.get_available_weeks()[:weeks]
        trend = []

        for week in available_weeks:
            summaries = self.db.get_suburb_summaries_by_week(week)

            if region:
                summaries = [s for s in summaries if s.region == region]

            if summaries:
                total_sold = sum(s.total_sold for s in summaries)
                total_passed = sum(s.passed_in for s in summaries)
                denom = total_sold + total_passed
                if denom > 0:
                    rate = total_sold / denom * 100
                    trend.append((week, round(rate, 1)))

        return sorted(trend, key=lambda x: x[0])

    def get_median_price_trend(
        self,
        weeks: int = 12,
        region: Optional[str] = None
    ) -> List[Tuple[date, int]]:
        """
        Get median price trend over time.

        Args:
            weeks: Number of weeks to include
            region: Optional region to filter by

        Returns:
            List of (week_ending, median_price) tuples
        """
        available_weeks = self.db.get_available_weeks()[:weeks]
        trend = []

        for week in available_weeks:
            summaries = self.db.get_suburb_summaries_by_week(week)

            if region:
                summaries = [s for s in summaries if s.region == region]

            prices = [s.median_price for s in summaries if s.median_price]
            if prices:
                median = int(statistics.median(prices))
                trend.append((week, median))

        return sorted(trend, key=lambda x: x[0])

    def compare_regions(self, week_ending: date) -> List[RegionalSummary]:
        """
        Compare all regions for a specific week.

        Args:
            week_ending: The week to compare

        Returns:
            List of RegionalSummary objects sorted by clearance rate
        """
        summaries = self.db.get_suburb_summaries_by_week(week_ending)

        by_region = defaultdict(list)
        for summary in summaries:
            by_region[summary.region].append(summary)

        regional_summaries = []
        for region, region_summaries in by_region.items():
            regional = self.calculate_regional_summary(region, region_summaries)
            regional_summaries.append(regional)

        # Sort by clearance rate (descending)
        return sorted(
            regional_summaries,
            key=lambda x: x.clearance_rate if x.clearance_rate else 0,
            reverse=True
        )

    def get_top_suburbs(
        self,
        week_ending: date,
        metric: str = 'clearance_rate',
        limit: int = 10,
        min_auctions: int = 5
    ) -> List[SuburbSummary]:
        """
        Get top performing suburbs by a given metric.

        Args:
            week_ending: The week to analyze
            metric: Metric to rank by ('clearance_rate', 'median_price', 'total_auctions')
            limit: Number of suburbs to return
            min_auctions: Minimum auctions to be included

        Returns:
            List of top SuburbSummary objects
        """
        summaries = self.db.get_suburb_summaries_by_week(week_ending)

        # Filter by minimum auctions
        summaries = [s for s in summaries if s.total_auctions >= min_auctions]

        # Sort by metric
        if metric == 'clearance_rate':
            summaries = sorted(
                summaries,
                key=lambda x: x.clearance_rate if x.clearance_rate else 0,
                reverse=True
            )
        elif metric == 'median_price':
            summaries = sorted(
                summaries,
                key=lambda x: x.median_price if x.median_price else 0,
                reverse=True
            )
        elif metric == 'total_auctions':
            summaries = sorted(
                summaries,
                key=lambda x: x.total_auctions,
                reverse=True
            )

        return summaries[:limit]


def generate_weekly_report(db: Database, week_ending: date) -> str:
    """
    Generate a text-based weekly report.

    Args:
        db: Database instance
        week_ending: The week to report on

    Returns:
        Formatted report string
    """
    aggregator = AuctionAggregator(db)
    data = aggregator.aggregate_week(week_ending)

    if not data:
        return f"No data available for week ending {week_ending}"

    weekly = data['weekly_summary']
    regional = data['regional_summaries']

    lines = [
        f"NSW AUCTION RESULTS - Week Ending {week_ending.strftime('%d %B %Y')}",
        "=" * 60,
        "",
        "STATE-WIDE SUMMARY",
        "-" * 40,
        f"Total Auctions:      {weekly.total_auctions:,}",
        f"Properties Sold:     {weekly.total_sold:,}",
        f"Clearance Rate:      {weekly.clearance_rate:.1f}%" if weekly.clearance_rate else "Clearance Rate:      N/A",
        f"Median Price:        ${weekly.median_price:,}" if weekly.median_price else "Median Price:        N/A",
        f"Total Sales Value:   ${weekly.total_sales_value:,}" if weekly.total_sales_value else "Total Sales Value:   N/A",
        "",
        f"Sydney Clearance:    {weekly.sydney_clearance_rate:.1f}%" if weekly.sydney_clearance_rate else "Sydney Clearance:    N/A",
        f"Regional Clearance:  {weekly.regional_clearance_rate:.1f}%" if weekly.regional_clearance_rate else "Regional Clearance:  N/A",
        "",
        "REGIONAL BREAKDOWN",
        "-" * 40,
    ]

    # Sort regions by clearance rate
    regional_sorted = sorted(
        regional,
        key=lambda x: x.clearance_rate if x.clearance_rate else 0,
        reverse=True
    )

    for r in regional_sorted:
        clearance = f"{r.clearance_rate:.1f}%" if r.clearance_rate else "N/A"
        median = f"${r.median_price:,}" if r.median_price else "N/A"
        lines.append(
            f"{r.region.replace('_', ' ').title():25} | "
            f"Auctions: {r.total_auctions:4} | "
            f"Sold: {r.total_sold:4} | "
            f"Rate: {clearance:6} | "
            f"Median: {median}"
        )

    lines.extend([
        "",
        "TOP 10 SUBURBS BY CLEARANCE RATE (min 5 auctions)",
        "-" * 40,
    ])

    top_suburbs = aggregator.get_top_suburbs(week_ending, 'clearance_rate', 10, 5)
    for i, s in enumerate(top_suburbs, 1):
        clearance = f"{s.clearance_rate:.1f}%" if s.clearance_rate else "N/A"
        lines.append(
            f"{i:2}. {s.suburb} ({s.postcode}) - "
            f"{s.total_sold}/{s.total_auctions} sold ({clearance})"
        )

    return "\n".join(lines)
