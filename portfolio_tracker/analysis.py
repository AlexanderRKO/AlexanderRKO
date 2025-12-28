"""
Portfolio analysis tools.

Provides analytical functions for portfolio evaluation,
risk assessment, and decision support.
"""

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict

from .models import Portfolio, Holding, AssetClass, Sector, PortfolioSnapshot

logger = logging.getLogger(__name__)


@dataclass
class ConcentrationRisk:
    """Analysis of concentration risk in portfolio."""
    top_holding_weight: Decimal
    top_5_weight: Decimal
    top_10_weight: Decimal
    herfindahl_index: Decimal  # HHI for concentration
    effective_holdings: Decimal  # 1/HHI
    risk_level: str  # "low", "moderate", "high", "very_high"


@dataclass
class SectorAnalysis:
    """Sector breakdown and analysis."""
    allocations: Dict[Sector, Decimal]
    top_sector: Sector
    top_sector_weight: Decimal
    diversification_score: Decimal  # 0-100


@dataclass
class PerformanceMetrics:
    """Portfolio performance metrics."""
    total_return_pct: Decimal
    total_return_dollar: Decimal
    best_performer: Optional[Holding]
    worst_performer: Optional[Holding]
    winners_count: int
    losers_count: int
    win_rate: Decimal
    avg_winner_return: Decimal
    avg_loser_return: Decimal


class PortfolioAnalyzer:
    """
    Analyzes portfolio holdings for insights and decision support.
    """

    def __init__(self, portfolio: Portfolio):
        self.portfolio = portfolio

    def get_summary(self) -> Dict[str, Any]:
        """Get a complete portfolio summary."""
        return {
            "snapshot_date": self.portfolio.snapshot_date.isoformat(),
            "total_holdings": self.portfolio.holding_count,
            "total_cost_base": float(self.portfolio.total_cost_base),
            "total_market_value": float(self.portfolio.total_market_value),
            "total_profit_loss": float(self.portfolio.total_profit_loss),
            "total_profit_loss_percent": float(self.portfolio.total_profit_loss_percent),
            "performance": self.get_performance_metrics().__dict__,
            "concentration": self.analyze_concentration().__dict__,
            "sector_breakdown": self.get_sector_breakdown(),
            "asset_class_breakdown": self.get_asset_class_breakdown(),
        }

    def get_performance_metrics(self) -> PerformanceMetrics:
        """Calculate performance metrics."""
        holdings = self.portfolio.holdings
        if not holdings:
            return PerformanceMetrics(
                total_return_pct=Decimal("0"),
                total_return_dollar=Decimal("0"),
                best_performer=None,
                worst_performer=None,
                winners_count=0,
                losers_count=0,
                win_rate=Decimal("0"),
                avg_winner_return=Decimal("0"),
                avg_loser_return=Decimal("0"),
            )

        winners = [h for h in holdings if h.profit_loss > 0]
        losers = [h for h in holdings if h.profit_loss < 0]

        best = max(holdings, key=lambda h: h.profit_loss_percent) if holdings else None
        worst = min(holdings, key=lambda h: h.profit_loss_percent) if holdings else None

        win_rate = Decimal(len(winners)) / Decimal(len(holdings)) * 100 if holdings else Decimal("0")

        avg_winner = (
            sum(h.profit_loss_percent for h in winners) / len(winners)
            if winners else Decimal("0")
        )
        avg_loser = (
            sum(h.profit_loss_percent for h in losers) / len(losers)
            if losers else Decimal("0")
        )

        return PerformanceMetrics(
            total_return_pct=self.portfolio.total_profit_loss_percent,
            total_return_dollar=self.portfolio.total_profit_loss,
            best_performer=best,
            worst_performer=worst,
            winners_count=len(winners),
            losers_count=len(losers),
            win_rate=win_rate,
            avg_winner_return=avg_winner,
            avg_loser_return=avg_loser,
        )

    def analyze_concentration(self) -> ConcentrationRisk:
        """Analyze portfolio concentration risk."""
        holdings = self.portfolio.top_holdings
        if not holdings:
            return ConcentrationRisk(
                top_holding_weight=Decimal("0"),
                top_5_weight=Decimal("0"),
                top_10_weight=Decimal("0"),
                herfindahl_index=Decimal("0"),
                effective_holdings=Decimal("0"),
                risk_level="low",
            )

        weights = [h.portfolio_weight for h in holdings]

        top_1 = weights[0] if len(weights) >= 1 else Decimal("0")
        top_5 = sum(weights[:5])
        top_10 = sum(weights[:10])

        # Calculate Herfindahl-Hirschman Index (HHI)
        # HHI = sum of squared market shares (as percentages)
        hhi = sum((w / 100) ** 2 for w in weights) * 10000  # Scale to 0-10000

        # Effective number of holdings = 1/HHI
        effective = Decimal("1") / (hhi / 10000) if hhi > 0 else Decimal("0")

        # Determine risk level
        if top_1 > 25 or hhi > 2500:
            risk_level = "very_high"
        elif top_1 > 15 or top_5 > 50 or hhi > 1500:
            risk_level = "high"
        elif top_1 > 10 or top_5 > 40:
            risk_level = "moderate"
        else:
            risk_level = "low"

        return ConcentrationRisk(
            top_holding_weight=top_1,
            top_5_weight=top_5,
            top_10_weight=top_10,
            herfindahl_index=hhi,
            effective_holdings=effective,
            risk_level=risk_level,
        )

    def get_sector_breakdown(self) -> Dict[str, float]:
        """Get sector allocation breakdown."""
        allocations = self.portfolio.sector_allocation()
        return {
            sector.value: float(weight)
            for sector, weight in sorted(
                allocations.items(),
                key=lambda x: x[1],
                reverse=True
            )
        }

    def get_asset_class_breakdown(self) -> Dict[str, float]:
        """Get asset class allocation breakdown."""
        allocations = self.portfolio.asset_class_allocation()
        return {
            ac.value: float(weight)
            for ac, weight in sorted(
                allocations.items(),
                key=lambda x: x[1],
                reverse=True
            )
        }

    def identify_rebalancing_opportunities(
        self,
        target_allocations: Optional[Dict[str, float]] = None
    ) -> List[Dict[str, Any]]:
        """
        Identify holdings that may need rebalancing.

        Args:
            target_allocations: Optional target weights by code (e.g., {"VAS": 20, "VGS": 30})

        Returns:
            List of rebalancing suggestions
        """
        suggestions = []

        # Check for over-concentrated positions (>10% of portfolio)
        for holding in self.portfolio.holdings:
            if holding.portfolio_weight > 10:
                suggestions.append({
                    "code": holding.code,
                    "type": "over_concentrated",
                    "current_weight": float(holding.portfolio_weight),
                    "suggestion": f"Consider reducing {holding.code} position (currently {float(holding.portfolio_weight):.1f}% of portfolio)",
                })

        # Check against target allocations if provided
        if target_allocations:
            for code, target in target_allocations.items():
                holding = self.portfolio.get_holding(code)
                current = float(holding.portfolio_weight) if holding else 0

                diff = current - target
                if abs(diff) > 2:  # 2% threshold
                    action = "reduce" if diff > 0 else "increase"
                    suggestions.append({
                        "code": code,
                        "type": "off_target",
                        "current_weight": current,
                        "target_weight": target,
                        "difference": diff,
                        "suggestion": f"{action.capitalize()} {code} by {abs(diff):.1f}% (current: {current:.1f}%, target: {target:.1f}%)",
                    })

        return suggestions

    def get_dividend_analysis(self) -> Dict[str, Any]:
        """Analyze dividend income and yield."""
        total_dividends = sum(h.dividends_received for h in self.portfolio.holdings)
        total_franking = sum(h.franking_credits for h in self.portfolio.holdings)

        # Calculate gross-up (with franking credits)
        grossed_up = total_dividends + total_franking

        # Estimate yield (dividends / cost base)
        yield_on_cost = (
            (total_dividends / self.portfolio.total_cost_base) * 100
            if self.portfolio.total_cost_base > 0 else Decimal("0")
        )

        # Yield on current value
        yield_on_value = (
            (total_dividends / self.portfolio.total_market_value) * 100
            if self.portfolio.total_market_value > 0 else Decimal("0")
        )

        return {
            "total_dividends": float(total_dividends),
            "total_franking_credits": float(total_franking),
            "grossed_up_income": float(grossed_up),
            "yield_on_cost_percent": float(yield_on_cost),
            "yield_on_current_value_percent": float(yield_on_value),
            "franking_ratio": float(total_franking / total_dividends) if total_dividends > 0 else 0,
        }

    def query_holdings(self, **filters) -> List[Holding]:
        """
        Query holdings with various filters.

        Supported filters:
            - min_value: Minimum market value
            - max_value: Maximum market value
            - min_return: Minimum return percentage
            - max_return: Maximum return percentage
            - asset_class: Filter by asset class
            - sector: Filter by sector
            - profitable: True for winners, False for losers
            - min_weight: Minimum portfolio weight

        Returns:
            Filtered list of holdings
        """
        results = list(self.portfolio.holdings)

        if "min_value" in filters:
            results = [h for h in results if h.market_value >= Decimal(str(filters["min_value"]))]

        if "max_value" in filters:
            results = [h for h in results if h.market_value <= Decimal(str(filters["max_value"]))]

        if "min_return" in filters:
            results = [h for h in results if h.profit_loss_percent >= Decimal(str(filters["min_return"]))]

        if "max_return" in filters:
            results = [h for h in results if h.profit_loss_percent <= Decimal(str(filters["max_return"]))]

        if "asset_class" in filters:
            ac = filters["asset_class"]
            if isinstance(ac, str):
                ac = AssetClass(ac)
            results = [h for h in results if h.asset_class == ac]

        if "sector" in filters:
            sec = filters["sector"]
            if isinstance(sec, str):
                sec = Sector(sec)
            results = [h for h in results if h.sector == sec]

        if "profitable" in filters:
            if filters["profitable"]:
                results = [h for h in results if h.is_profitable]
            else:
                results = [h for h in results if not h.is_profitable]

        if "min_weight" in filters:
            results = [h for h in results if h.portfolio_weight >= Decimal(str(filters["min_weight"]))]

        return results


def compare_snapshots(
    old: Portfolio,
    new: Portfolio
) -> Dict[str, Any]:
    """
    Compare two portfolio snapshots to see changes.

    Args:
        old: Earlier portfolio snapshot
        new: Later portfolio snapshot

    Returns:
        Dictionary with comparison details
    """
    old_codes = {h.code for h in old.holdings}
    new_codes = {h.code for h in new.holdings}

    added = new_codes - old_codes
    removed = old_codes - new_codes
    common = old_codes & new_codes

    # Value changes
    value_change = new.total_market_value - old.total_market_value
    value_change_pct = (
        (value_change / old.total_market_value) * 100
        if old.total_market_value > 0 else Decimal("0")
    )

    # Track changes in common holdings
    holding_changes = []
    for code in common:
        old_h = old.get_holding(code)
        new_h = new.get_holding(code)
        if old_h and new_h:
            qty_change = new_h.quantity - old_h.quantity
            price_change = new_h.current_price - old_h.current_price
            if qty_change != 0 or price_change != 0:
                holding_changes.append({
                    "code": code,
                    "quantity_change": qty_change,
                    "old_price": float(old_h.current_price),
                    "new_price": float(new_h.current_price),
                    "price_change": float(price_change),
                    "price_change_pct": float(
                        (price_change / old_h.current_price) * 100
                        if old_h.current_price > 0 else 0
                    ),
                })

    return {
        "old_date": old.snapshot_date.isoformat(),
        "new_date": new.snapshot_date.isoformat(),
        "holdings_added": list(added),
        "holdings_removed": list(removed),
        "old_total_value": float(old.total_market_value),
        "new_total_value": float(new.total_market_value),
        "value_change": float(value_change),
        "value_change_percent": float(value_change_pct),
        "holding_changes": holding_changes,
    }


def generate_portfolio_report(portfolio: Portfolio) -> str:
    """
    Generate a text report for the portfolio.

    Args:
        portfolio: Portfolio to report on

    Returns:
        Formatted text report
    """
    analyzer = PortfolioAnalyzer(portfolio)
    perf = analyzer.get_performance_metrics()
    conc = analyzer.analyze_concentration()

    lines = [
        "=" * 60,
        f"PORTFOLIO REPORT - {portfolio.snapshot_date.isoformat()}",
        "=" * 60,
        "",
        "SUMMARY",
        "-" * 40,
        f"Total Holdings:     {portfolio.holding_count}",
        f"Total Cost Base:    ${float(portfolio.total_cost_base):>15,.2f}",
        f"Total Market Value: ${float(portfolio.total_market_value):>15,.2f}",
        f"Total P/L:          ${float(portfolio.total_profit_loss):>15,.2f} ({float(portfolio.total_profit_loss_percent):+.2f}%)",
        "",
        "PERFORMANCE",
        "-" * 40,
        f"Winners:  {perf.winners_count} ({float(perf.win_rate):.1f}%)",
        f"Losers:   {perf.losers_count}",
        f"Avg Winner Return: {float(perf.avg_winner_return):+.2f}%",
        f"Avg Loser Return:  {float(perf.avg_loser_return):+.2f}%",
        "",
    ]

    if perf.best_performer:
        lines.append(f"Best Performer:  {perf.best_performer.code} ({float(perf.best_performer.profit_loss_percent):+.2f}%)")
    if perf.worst_performer:
        lines.append(f"Worst Performer: {perf.worst_performer.code} ({float(perf.worst_performer.profit_loss_percent):+.2f}%)")

    lines.extend([
        "",
        "CONCENTRATION RISK",
        "-" * 40,
        f"Risk Level: {conc.risk_level.upper()}",
        f"Top Holding Weight: {float(conc.top_holding_weight):.1f}%",
        f"Top 5 Holdings:     {float(conc.top_5_weight):.1f}%",
        f"Top 10 Holdings:    {float(conc.top_10_weight):.1f}%",
        f"Effective Holdings: {float(conc.effective_holdings):.1f}",
        "",
        "TOP 10 HOLDINGS",
        "-" * 40,
    ])

    for i, h in enumerate(portfolio.top_holdings[:10], 1):
        lines.append(
            f"{i:2}. {h.code:<6} {h.name[:25]:<25} "
            f"${float(h.market_value):>12,.2f} ({float(h.portfolio_weight):>5.1f}%) "
            f"{float(h.profit_loss_percent):>+7.2f}%"
        )

    lines.extend([
        "",
        "ASSET CLASS ALLOCATION",
        "-" * 40,
    ])
    for ac, weight in analyzer.get_asset_class_breakdown().items():
        lines.append(f"  {ac:<25} {weight:>6.1f}%")

    lines.append("")
    lines.append("=" * 60)

    return "\n".join(lines)
