"""
Change Tracker - Track portfolio changes between CSV imports.

Provides comparison between snapshots to identify:
- New and sold holdings
- Quantity changes
- Value and P/L movements
- FY progress reports (July 1 - June 30)
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any, Set, Tuple

from .models import Portfolio, Holding, PortfolioSnapshot
from .storage import PortfolioDatabase
from .tax_reporting import get_financial_year

logger = logging.getLogger(__name__)


@dataclass
class HoldingChange:
    """Represents a change in a single holding."""
    code: str
    name: str
    change_type: str  # 'new', 'sold', 'increased', 'decreased', 'unchanged'

    # Previous state (None if new)
    prev_quantity: Optional[int] = None
    prev_value: Optional[Decimal] = None
    prev_cost: Optional[Decimal] = None
    prev_profit: Optional[Decimal] = None

    # Current state (None if sold)
    curr_quantity: Optional[int] = None
    curr_value: Optional[Decimal] = None
    curr_cost: Optional[Decimal] = None
    curr_profit: Optional[Decimal] = None

    # Changes
    quantity_change: int = 0
    value_change: Decimal = Decimal("0")
    profit_change: Decimal = Decimal("0")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "change_type": self.change_type,
            "quantity_change": self.quantity_change,
            "value_change": float(self.value_change),
            "profit_change": float(self.profit_change),
            "prev": {
                "quantity": self.prev_quantity,
                "value": float(self.prev_value) if self.prev_value else None,
            },
            "curr": {
                "quantity": self.curr_quantity,
                "value": float(self.curr_value) if self.curr_value else None,
            },
        }


@dataclass
class PortfolioComparison:
    """Comparison between two portfolio snapshots."""
    from_date: date
    to_date: date
    from_snapshot_id: str
    to_snapshot_id: str

    # Summary metrics
    holdings_added: int = 0
    holdings_removed: int = 0
    holdings_changed: int = 0
    holdings_unchanged: int = 0

    # Value changes
    prev_total_value: Decimal = Decimal("0")
    curr_total_value: Decimal = Decimal("0")
    value_change: Decimal = Decimal("0")
    value_change_percent: Decimal = Decimal("0")

    # P/L changes
    prev_total_profit: Decimal = Decimal("0")
    curr_total_profit: Decimal = Decimal("0")
    profit_change: Decimal = Decimal("0")

    # Detail
    changes: List[HoldingChange] = field(default_factory=list)

    @property
    def new_holdings(self) -> List[HoldingChange]:
        return [c for c in self.changes if c.change_type == "new"]

    @property
    def sold_holdings(self) -> List[HoldingChange]:
        return [c for c in self.changes if c.change_type == "sold"]

    @property
    def increased_holdings(self) -> List[HoldingChange]:
        return [c for c in self.changes if c.change_type == "increased"]

    @property
    def decreased_holdings(self) -> List[HoldingChange]:
        return [c for c in self.changes if c.change_type == "decreased"]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "period": {
                "from": self.from_date.isoformat(),
                "to": self.to_date.isoformat(),
            },
            "summary": {
                "added": self.holdings_added,
                "removed": self.holdings_removed,
                "changed": self.holdings_changed,
                "unchanged": self.holdings_unchanged,
            },
            "value": {
                "previous": float(self.prev_total_value),
                "current": float(self.curr_total_value),
                "change": float(self.value_change),
                "change_percent": float(self.value_change_percent),
            },
            "profit": {
                "previous": float(self.prev_total_profit),
                "current": float(self.curr_total_profit),
                "change": float(self.profit_change),
            },
            "changes": [c.to_dict() for c in self.changes],
        }


def compare_portfolios(
    prev_portfolio: Portfolio,
    curr_portfolio: Portfolio,
) -> PortfolioComparison:
    """
    Compare two portfolio snapshots and identify changes.

    Args:
        prev_portfolio: Earlier portfolio snapshot
        curr_portfolio: Later portfolio snapshot

    Returns:
        PortfolioComparison with all changes identified
    """
    comparison = PortfolioComparison(
        from_date=prev_portfolio.snapshot_date,
        to_date=curr_portfolio.snapshot_date,
        from_snapshot_id=prev_portfolio.snapshot_id or "",
        to_snapshot_id=curr_portfolio.snapshot_id or "",
        prev_total_value=prev_portfolio.total_market_value,
        curr_total_value=curr_portfolio.total_market_value,
        prev_total_profit=prev_portfolio.total_profit_loss,
        curr_total_profit=curr_portfolio.total_profit_loss,
    )

    # Calculate value changes
    comparison.value_change = comparison.curr_total_value - comparison.prev_total_value
    if comparison.prev_total_value > 0:
        comparison.value_change_percent = (
            comparison.value_change / comparison.prev_total_value * Decimal("100")
        )
    comparison.profit_change = comparison.curr_total_profit - comparison.prev_total_profit

    # Build lookup maps
    prev_holdings = {h.code: h for h in prev_portfolio.holdings}
    curr_holdings = {h.code: h for h in curr_portfolio.holdings}

    all_codes = set(prev_holdings.keys()) | set(curr_holdings.keys())

    for code in all_codes:
        prev_h = prev_holdings.get(code)
        curr_h = curr_holdings.get(code)

        if prev_h and curr_h:
            # Holding exists in both
            qty_change = curr_h.quantity - prev_h.quantity
            if qty_change > 0:
                change_type = "increased"
                comparison.holdings_changed += 1
            elif qty_change < 0:
                change_type = "decreased"
                comparison.holdings_changed += 1
            else:
                change_type = "unchanged"
                comparison.holdings_unchanged += 1

            change = HoldingChange(
                code=code,
                name=curr_h.name,
                change_type=change_type,
                prev_quantity=prev_h.quantity,
                prev_value=prev_h.market_value,
                prev_cost=prev_h.cost_base,
                prev_profit=prev_h.profit_loss,
                curr_quantity=curr_h.quantity,
                curr_value=curr_h.market_value,
                curr_cost=curr_h.cost_base,
                curr_profit=curr_h.profit_loss,
                quantity_change=qty_change,
                value_change=curr_h.market_value - prev_h.market_value,
                profit_change=curr_h.profit_loss - prev_h.profit_loss,
            )
            comparison.changes.append(change)

        elif curr_h and not prev_h:
            # New holding
            comparison.holdings_added += 1
            change = HoldingChange(
                code=code,
                name=curr_h.name,
                change_type="new",
                curr_quantity=curr_h.quantity,
                curr_value=curr_h.market_value,
                curr_cost=curr_h.cost_base,
                curr_profit=curr_h.profit_loss,
                quantity_change=curr_h.quantity,
                value_change=curr_h.market_value,
                profit_change=curr_h.profit_loss,
            )
            comparison.changes.append(change)

        elif prev_h and not curr_h:
            # Sold holding
            comparison.holdings_removed += 1
            change = HoldingChange(
                code=code,
                name=prev_h.name,
                change_type="sold",
                prev_quantity=prev_h.quantity,
                prev_value=prev_h.market_value,
                prev_cost=prev_h.cost_base,
                prev_profit=prev_h.profit_loss,
                quantity_change=-prev_h.quantity,
                value_change=-prev_h.market_value,
                profit_change=-prev_h.profit_loss,
            )
            comparison.changes.append(change)

    # Sort changes by absolute value change
    comparison.changes.sort(key=lambda c: abs(c.value_change), reverse=True)

    return comparison


def get_fy_comparison(
    db: PortfolioDatabase,
    financial_year: Optional[str] = None,
) -> Optional[PortfolioComparison]:
    """
    Get comparison for a financial year (July 1 to June 30).

    Args:
        db: Database instance
        financial_year: FY string (e.g., "2024-25") or None for current

    Returns:
        PortfolioComparison for the FY or None if insufficient data
    """
    if financial_year is None:
        financial_year = get_financial_year()

    # Parse FY string to get dates
    try:
        start_year = int(financial_year.split("-")[0])
        fy_start = date(start_year, 7, 1)
        fy_end = date(start_year + 1, 6, 30)
    except (ValueError, IndexError):
        logger.error(f"Invalid financial year format: {financial_year}")
        return None

    # Find snapshots closest to FY start and end
    snapshots = db.get_all_snapshots()
    if len(snapshots) < 2:
        return None

    # Find snapshot closest to (but after) FY start
    start_snapshot = None
    for snap in snapshots:
        if snap.snapshot_date >= fy_start:
            if start_snapshot is None or snap.snapshot_date < start_snapshot.snapshot_date:
                start_snapshot = snap

    # Find snapshot closest to (but before or on) FY end, or latest
    end_snapshot = None
    today = date.today()
    target_end = min(fy_end, today)
    for snap in snapshots:
        if snap.snapshot_date <= target_end:
            if end_snapshot is None or snap.snapshot_date > end_snapshot.snapshot_date:
                end_snapshot = snap

    if not start_snapshot or not end_snapshot:
        return None

    if start_snapshot.snapshot_id == end_snapshot.snapshot_id:
        # Only one snapshot in the period
        return None

    # Load full portfolios
    start_portfolio = db.get_portfolio(start_snapshot.snapshot_id)
    end_portfolio = db.get_portfolio(end_snapshot.snapshot_id)

    if not start_portfolio or not end_portfolio:
        return None

    return compare_portfolios(start_portfolio, end_portfolio)


def generate_change_report(comparison: PortfolioComparison) -> str:
    """Generate a formatted change report."""
    lines = []

    lines.append("=" * 70)
    lines.append("PORTFOLIO CHANGE REPORT")
    lines.append("=" * 70)
    lines.append(f"\nPeriod: {comparison.from_date} to {comparison.to_date}")
    days = (comparison.to_date - comparison.from_date).days
    lines.append(f"Duration: {days} days")

    # Value Summary
    lines.append("\n" + "-" * 70)
    lines.append("VALUE SUMMARY")
    lines.append("-" * 70)
    lines.append(f"  Starting Value:    ${float(comparison.prev_total_value):>15,.2f}")
    lines.append(f"  Ending Value:      ${float(comparison.curr_total_value):>15,.2f}")
    lines.append(f"  Change:            ${float(comparison.value_change):>+15,.2f} ({float(comparison.value_change_percent):+.1f}%)")

    # P/L Summary
    lines.append(f"\n  Starting P/L:      ${float(comparison.prev_total_profit):>+15,.2f}")
    lines.append(f"  Ending P/L:        ${float(comparison.curr_total_profit):>+15,.2f}")
    lines.append(f"  P/L Change:        ${float(comparison.profit_change):>+15,.2f}")

    # Holdings Summary
    lines.append("\n" + "-" * 70)
    lines.append("HOLDINGS SUMMARY")
    lines.append("-" * 70)
    lines.append(f"  New positions:     {comparison.holdings_added:>5}")
    lines.append(f"  Sold positions:    {comparison.holdings_removed:>5}")
    lines.append(f"  Quantity changed:  {comparison.holdings_changed:>5}")
    lines.append(f"  Unchanged:         {comparison.holdings_unchanged:>5}")

    # New Holdings
    if comparison.new_holdings:
        lines.append("\n" + "-" * 70)
        lines.append("NEW POSITIONS")
        lines.append("-" * 70)
        lines.append(f"\n  {'Code':<6} {'Quantity':>10} {'Value':>15} {'P/L':>12}")
        lines.append("  " + "-" * 47)
        for h in comparison.new_holdings:
            lines.append(
                f"  {h.code:<6} "
                f"{h.curr_quantity:>10,} "
                f"${float(h.curr_value):>14,.0f} "
                f"${float(h.curr_profit):>+11,.0f}"
            )

    # Sold Holdings
    if comparison.sold_holdings:
        lines.append("\n" + "-" * 70)
        lines.append("SOLD POSITIONS")
        lines.append("-" * 70)
        lines.append(f"\n  {'Code':<6} {'Quantity':>10} {'Value':>15} {'P/L':>12}")
        lines.append("  " + "-" * 47)
        for h in comparison.sold_holdings:
            lines.append(
                f"  {h.code:<6} "
                f"{h.prev_quantity:>10,} "
                f"${float(h.prev_value):>14,.0f} "
                f"${float(h.prev_profit):>+11,.0f}"
            )

    # Top Value Changes
    value_changes = [c for c in comparison.changes if c.change_type not in ("new", "sold")]
    if value_changes:
        top_gainers = sorted(value_changes, key=lambda c: c.value_change, reverse=True)[:5]
        top_losers = sorted(value_changes, key=lambda c: c.value_change)[:5]

        lines.append("\n" + "-" * 70)
        lines.append("TOP VALUE GAINERS")
        lines.append("-" * 70)
        lines.append(f"\n  {'Code':<6} {'Value Change':>15} {'Prev':>12} {'Curr':>12}")
        lines.append("  " + "-" * 49)
        for h in top_gainers:
            if h.value_change > 0:
                lines.append(
                    f"  {h.code:<6} "
                    f"${float(h.value_change):>+14,.0f} "
                    f"${float(h.prev_value):>11,.0f} "
                    f"${float(h.curr_value):>11,.0f}"
                )

        lines.append("\n" + "-" * 70)
        lines.append("TOP VALUE LOSERS")
        lines.append("-" * 70)
        lines.append(f"\n  {'Code':<6} {'Value Change':>15} {'Prev':>12} {'Curr':>12}")
        lines.append("  " + "-" * 49)
        for h in top_losers:
            if h.value_change < 0:
                lines.append(
                    f"  {h.code:<6} "
                    f"${float(h.value_change):>+14,.0f} "
                    f"${float(h.prev_value):>11,.0f} "
                    f"${float(h.curr_value):>11,.0f}"
                )

    # Talking Points
    lines.append("\n" + "=" * 70)
    lines.append("KEY TALKING POINTS")
    lines.append("=" * 70)

    points = generate_talking_points(comparison)
    for i, point in enumerate(points, 1):
        lines.append(f"\n  {i}. {point}")

    lines.append("\n" + "=" * 70)

    return "\n".join(lines)


def generate_talking_points(comparison: PortfolioComparison) -> List[str]:
    """Generate key talking points from the comparison."""
    points = []

    # Overall performance
    if comparison.value_change > 0:
        points.append(
            f"Portfolio grew by ${float(comparison.value_change):,.0f} "
            f"({float(comparison.value_change_percent):+.1f}%) over the period."
        )
    else:
        points.append(
            f"Portfolio declined by ${float(abs(comparison.value_change)):,.0f} "
            f"({float(comparison.value_change_percent):+.1f}%) over the period."
        )

    # New investments
    if comparison.new_holdings:
        new_value = sum(h.curr_value for h in comparison.new_holdings)
        points.append(
            f"Added {comparison.holdings_added} new position(s) "
            f"worth ${float(new_value):,.0f}."
        )

    # Exits
    if comparison.sold_holdings:
        points.append(
            f"Exited {comparison.holdings_removed} position(s)."
        )

    # Best performer
    all_changes = [c for c in comparison.changes if c.prev_value and c.curr_value]
    if all_changes:
        best = max(all_changes, key=lambda c: c.value_change)
        if best.value_change > 0:
            points.append(
                f"Best performer: {best.code} gained ${float(best.value_change):,.0f}."
            )

        worst = min(all_changes, key=lambda c: c.value_change)
        if worst.value_change < 0:
            points.append(
                f"Largest decline: {worst.code} lost ${float(abs(worst.value_change)):,.0f}."
            )

    # Concentration
    if comparison.curr_total_value > 0:
        top_changes = sorted(
            [c for c in comparison.changes if c.curr_value],
            key=lambda c: c.curr_value,
            reverse=True
        )[:3]
        top_weight = sum(c.curr_value for c in top_changes) / comparison.curr_total_value * 100
        top_codes = ", ".join(c.code for c in top_changes)
        points.append(
            f"Top 3 holdings ({top_codes}) represent {float(top_weight):.1f}% of portfolio."
        )

    return points


def get_import_history(db: PortfolioDatabase, limit: int = 10) -> List[Dict[str, Any]]:
    """Get recent import history."""
    snapshots = db.get_all_snapshots()

    history = []
    for snap in snapshots[:limit]:
        history.append({
            "snapshot_id": snap.snapshot_id,
            "date": snap.snapshot_date.isoformat(),
            "holdings": snap.total_holdings,
            "value": float(snap.total_market_value),
            "profit": float(snap.total_profit_loss),
            "profit_percent": float(snap.total_profit_loss_percent),
        })

    return history
