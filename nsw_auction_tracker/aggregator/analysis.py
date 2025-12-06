"""
Analysis and aggregation utilities for auction data.

Provides:
- Clearance rate calculations
- Price statistics (median, average, trends)
- Suburb and region comparisons
- Weekly/monthly trend analysis
"""

import statistics
import logging
from datetime import date, datetime
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict

from ..models import (
    AuctionResult,
    AuctionOutcome,
    PropertyType,
    SuburbSummary,
    WeeklySnapshot,
)
from ..storage import AuctionDatabase

logger = logging.getLogger(__name__)


def calculate_clearance_rate(results: List[AuctionResult]) -> float:
    """
    Calculate clearance rate from auction results.

    Clearance rate = (Sold / Total Reported) * 100

    Note: Only includes properties with definitive outcomes.
    Withdrawn/postponed are typically excluded from official rates.

    Args:
        results: List of AuctionResult objects

    Returns:
        Clearance rate as percentage (0-100)
    """
    if not results:
        return 0.0

    # Count sold vs total reported
    sold = sum(1 for r in results if r.is_sold)
    total = sum(1 for r in results if r.outcome not in [
        AuctionOutcome.WITHDRAWN,
        AuctionOutcome.POSTPONED,
        AuctionOutcome.UNKNOWN,
    ])

    if total == 0:
        return 0.0

    return round((sold / total) * 100, 1)


def calculate_median_price(results: List[AuctionResult]) -> Optional[int]:
    """
    Calculate median sold price from auction results.

    Args:
        results: List of AuctionResult objects

    Returns:
        Median price or None if no sold prices available
    """
    prices = [r.sold_price for r in results if r.sold_price and r.is_sold]

    if not prices:
        return None

    return int(statistics.median(prices))


def calculate_price_stats(results: List[AuctionResult]) -> Dict[str, Any]:
    """
    Calculate comprehensive price statistics.

    Args:
        results: List of AuctionResult objects

    Returns:
        Dictionary with price statistics
    """
    prices = [r.sold_price for r in results if r.sold_price and r.is_sold]

    if not prices:
        return {
            "count": 0,
            "median": None,
            "average": None,
            "min": None,
            "max": None,
            "total": None,
            "std_dev": None,
        }

    return {
        "count": len(prices),
        "median": int(statistics.median(prices)),
        "average": int(statistics.mean(prices)),
        "min": min(prices),
        "max": max(prices),
        "total": sum(prices),
        "std_dev": int(statistics.stdev(prices)) if len(prices) > 1 else None,
    }


class AuctionAnalyzer:
    """
    Comprehensive analyzer for auction results data.

    Usage:
        analyzer = AuctionAnalyzer(results)
        clearance = analyzer.get_clearance_rate()
        by_suburb = analyzer.group_by_suburb()
        trends = analyzer.calculate_trends()
    """

    def __init__(self, results: List[AuctionResult]):
        self.results = results

    def get_clearance_rate(self) -> float:
        """Get overall clearance rate."""
        return calculate_clearance_rate(self.results)

    def get_price_stats(self) -> Dict[str, Any]:
        """Get overall price statistics."""
        return calculate_price_stats(self.results)

    def group_by_suburb(self) -> Dict[str, SuburbSummary]:
        """
        Group results by suburb and calculate summaries.

        Returns:
            Dictionary mapping suburb-postcode to SuburbSummary
        """
        grouped: Dict[str, List[AuctionResult]] = defaultdict(list)

        for result in self.results:
            key = f"{result.suburb}_{result.postcode}"
            grouped[key].append(result)

        summaries = {}
        for key, suburb_results in grouped.items():
            summary = self._create_suburb_summary(suburb_results)
            summaries[key] = summary

        return summaries

    def _create_suburb_summary(self, results: List[AuctionResult]) -> SuburbSummary:
        """Create a SuburbSummary from a list of results."""
        if not results:
            return SuburbSummary(suburb="", postcode="", region="", week="")

        first = results[0]
        week = first.collection_week or date.today().strftime("%Y-W%W")

        summary = SuburbSummary(
            suburb=first.suburb,
            postcode=first.postcode,
            region=first.region,
            week=week,
        )

        # Count by outcome
        summary.total_auctions = len(results)
        summary.sold_count = sum(1 for r in results if r.is_sold)
        summary.passed_in_count = sum(
            1 for r in results
            if r.outcome in [AuctionOutcome.PASSED_IN, AuctionOutcome.PASSED_IN_VENDOR_BID]
        )
        summary.withdrawn_count = sum(
            1 for r in results if r.outcome == AuctionOutcome.WITHDRAWN
        )

        # Price stats
        price_stats = calculate_price_stats(results)
        summary.median_price = price_stats["median"]
        summary.average_price = price_stats["average"]
        summary.min_price = price_stats["min"]
        summary.max_price = price_stats["max"]
        summary.total_value = price_stats["total"]

        # By property type
        summary.houses_sold = sum(
            1 for r in results
            if r.is_sold and r.property_type == PropertyType.HOUSE
        )
        summary.units_sold = sum(
            1 for r in results
            if r.is_sold and r.property_type in [
                PropertyType.UNIT, PropertyType.APARTMENT, PropertyType.TOWNHOUSE
            ]
        )

        # Calculate clearance rate
        summary.calculate_clearance_rate()

        return summary

    def group_by_region(self) -> Dict[str, Dict[str, Any]]:
        """
        Group results by region with statistics.

        Returns:
            Dictionary mapping region to statistics
        """
        grouped: Dict[str, List[AuctionResult]] = defaultdict(list)

        for result in self.results:
            region = result.region or "Unknown"
            grouped[region].append(result)

        stats = {}
        for region, region_results in grouped.items():
            stats[region] = {
                "total": len(region_results),
                "clearance_rate": calculate_clearance_rate(region_results),
                "price_stats": calculate_price_stats(region_results),
                "suburbs": len(set(r.suburb for r in region_results)),
            }

        return stats

    def group_by_property_type(self) -> Dict[str, Dict[str, Any]]:
        """
        Group results by property type.

        Returns:
            Dictionary mapping property type to statistics
        """
        grouped: Dict[str, List[AuctionResult]] = defaultdict(list)

        for result in self.results:
            ptype = result.property_type.value
            grouped[ptype].append(result)

        stats = {}
        for ptype, type_results in grouped.items():
            stats[ptype] = {
                "total": len(type_results),
                "clearance_rate": calculate_clearance_rate(type_results),
                "price_stats": calculate_price_stats(type_results),
            }

        return stats

    def get_top_suburbs_by_price(self, n: int = 10) -> List[Tuple[str, int]]:
        """
        Get top N suburbs by median price.

        Args:
            n: Number of suburbs to return

        Returns:
            List of (suburb_name, median_price) tuples
        """
        by_suburb = self.group_by_suburb()

        sorted_suburbs = sorted(
            [(k, v.median_price) for k, v in by_suburb.items() if v.median_price],
            key=lambda x: x[1],
            reverse=True,
        )

        return sorted_suburbs[:n]

    def get_top_suburbs_by_volume(self, n: int = 10) -> List[Tuple[str, int]]:
        """
        Get top N suburbs by auction volume.

        Args:
            n: Number of suburbs to return

        Returns:
            List of (suburb_name, count) tuples
        """
        by_suburb = self.group_by_suburb()

        sorted_suburbs = sorted(
            [(k, v.total_auctions) for k, v in by_suburb.items()],
            key=lambda x: x[1],
            reverse=True,
        )

        return sorted_suburbs[:n]

    def get_outcome_distribution(self) -> Dict[str, int]:
        """
        Get distribution of auction outcomes.

        Returns:
            Dictionary mapping outcome to count
        """
        distribution: Dict[str, int] = defaultdict(int)

        for result in self.results:
            distribution[result.outcome.value] += 1

        return dict(distribution)

    def get_price_brackets(
        self, brackets: Optional[List[int]] = None
    ) -> Dict[str, int]:
        """
        Get count of properties in each price bracket.

        Args:
            brackets: List of price thresholds (default: standard brackets)

        Returns:
            Dictionary mapping bracket label to count
        """
        if brackets is None:
            brackets = [500_000, 750_000, 1_000_000, 1_500_000, 2_000_000, 3_000_000]

        distribution: Dict[str, int] = defaultdict(int)
        sold_results = [r for r in self.results if r.sold_price and r.is_sold]

        for result in sold_results:
            price = result.sold_price
            placed = False

            for i, threshold in enumerate(brackets):
                if price < threshold:
                    if i == 0:
                        label = f"Under ${threshold//1000}K"
                    else:
                        prev = brackets[i - 1]
                        label = f"${prev//1000}K - ${threshold//1000}K"
                    distribution[label] += 1
                    placed = True
                    break

            if not placed:
                label = f"Over ${brackets[-1]//1_000_000}M"
                distribution[label] += 1

        return dict(distribution)


def generate_weekly_report(
    results: List[AuctionResult],
    week: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate a comprehensive weekly report.

    Args:
        results: List of AuctionResult objects
        week: Week identifier (default: current week)

    Returns:
        Dictionary containing full weekly report
    """
    if week is None:
        week = date.today().strftime("%Y-W%W")

    analyzer = AuctionAnalyzer(results)

    report = {
        "week": week,
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "total_auctions": len(results),
            "clearance_rate": analyzer.get_clearance_rate(),
            "price_stats": analyzer.get_price_stats(),
        },
        "by_outcome": analyzer.get_outcome_distribution(),
        "by_property_type": analyzer.group_by_property_type(),
        "top_suburbs_by_price": analyzer.get_top_suburbs_by_price(10),
        "top_suburbs_by_volume": analyzer.get_top_suburbs_by_volume(10),
        "price_brackets": analyzer.get_price_brackets(),
        "suburbs": {
            k: v.to_dict() for k, v in analyzer.group_by_suburb().items()
        },
    }

    return report


def compare_weeks(
    db: AuctionDatabase,
    week1: str,
    week2: str,
) -> Dict[str, Any]:
    """
    Compare auction statistics between two weeks.

    Args:
        db: AuctionDatabase instance
        week1: First week identifier
        week2: Second week identifier

    Returns:
        Dictionary with comparison data
    """
    results1 = db.get_results_by_week(week1)
    results2 = db.get_results_by_week(week2)

    analyzer1 = AuctionAnalyzer(results1)
    analyzer2 = AuctionAnalyzer(results2)

    stats1 = analyzer1.get_price_stats()
    stats2 = analyzer2.get_price_stats()

    comparison = {
        "weeks": [week1, week2],
        "total_auctions": {
            week1: len(results1),
            week2: len(results2),
            "change": len(results2) - len(results1),
        },
        "clearance_rate": {
            week1: analyzer1.get_clearance_rate(),
            week2: analyzer2.get_clearance_rate(),
            "change": analyzer2.get_clearance_rate() - analyzer1.get_clearance_rate(),
        },
        "median_price": {
            week1: stats1["median"],
            week2: stats2["median"],
            "change": (stats2["median"] or 0) - (stats1["median"] or 0),
            "change_pct": (
                ((stats2["median"] or 0) - (stats1["median"] or 0)) / (stats1["median"] or 1) * 100
                if stats1["median"] else None
            ),
        },
    }

    return comparison
