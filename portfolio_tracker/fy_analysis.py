"""
Financial Year Analysis - Comprehensive FY reporting for Australian investors.

Australian Financial Year: July 1 to June 30
Provides FY progress tracking, comparisons, and EOFY preparation.
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple
from calendar import monthrange

from .models import Portfolio, PortfolioSnapshot
from .storage import PortfolioDatabase
from .tax_reporting import get_financial_year, analyze_unrealised_gains

logger = logging.getLogger(__name__)


# Australian FY key dates
FY_MONTHS = [7, 8, 9, 10, 11, 12, 1, 2, 3, 4, 5, 6]  # Jul to Jun
FY_QUARTERS = {
    "Q1": [7, 8, 9],    # Jul-Sep
    "Q2": [10, 11, 12], # Oct-Dec
    "Q3": [1, 2, 3],    # Jan-Mar
    "Q4": [4, 5, 6],    # Apr-Jun
}


@dataclass
class FYDates:
    """Key dates for a financial year."""
    fy_string: str  # e.g., "2024-25"
    start_date: date  # July 1
    end_date: date  # June 30
    q1_end: date  # Sep 30
    q2_end: date  # Dec 31
    q3_end: date  # Mar 31
    q4_end: date  # Jun 30 (same as end_date)

    @classmethod
    def from_fy_string(cls, fy_string: str) -> "FYDates":
        """Create FYDates from a FY string like '2024-25'."""
        start_year = int(fy_string.split("-")[0])
        end_year = start_year + 1

        return cls(
            fy_string=fy_string,
            start_date=date(start_year, 7, 1),
            end_date=date(end_year, 6, 30),
            q1_end=date(start_year, 9, 30),
            q2_end=date(start_year, 12, 31),
            q3_end=date(end_year, 3, 31),
            q4_end=date(end_year, 6, 30),
        )

    @property
    def is_current(self) -> bool:
        """Check if this is the current FY."""
        today = date.today()
        return self.start_date <= today <= self.end_date

    @property
    def days_total(self) -> int:
        """Total days in the FY."""
        return (self.end_date - self.start_date).days + 1

    @property
    def days_elapsed(self) -> int:
        """Days elapsed in the FY (for current FY)."""
        today = min(date.today(), self.end_date)
        if today < self.start_date:
            return 0
        return (today - self.start_date).days + 1

    @property
    def days_remaining(self) -> int:
        """Days remaining in the FY."""
        today = date.today()
        if today > self.end_date:
            return 0
        if today < self.start_date:
            return self.days_total
        return (self.end_date - today).days

    @property
    def progress_percent(self) -> float:
        """Percentage of FY completed."""
        return (self.days_elapsed / self.days_total) * 100

    @property
    def current_quarter(self) -> str:
        """Get current quarter."""
        today = date.today()
        if today <= self.q1_end:
            return "Q1"
        elif today <= self.q2_end:
            return "Q2"
        elif today <= self.q3_end:
            return "Q3"
        else:
            return "Q4"


@dataclass
class FYSnapshot:
    """Portfolio state at a point in the FY."""
    snapshot_date: date
    total_value: Decimal
    total_cost: Decimal
    total_profit: Decimal
    profit_percent: Decimal
    holding_count: int
    snapshot_id: str


@dataclass
class FYAnalysis:
    """Comprehensive FY analysis."""
    fy_dates: FYDates

    # Starting position (July 1 or first available)
    start_snapshot: Optional[FYSnapshot] = None

    # Current/ending position
    end_snapshot: Optional[FYSnapshot] = None

    # Performance metrics
    value_change: Decimal = Decimal("0")
    value_change_percent: Decimal = Decimal("0")
    profit_change: Decimal = Decimal("0")

    # Quarterly snapshots (if available)
    q1_snapshot: Optional[FYSnapshot] = None
    q2_snapshot: Optional[FYSnapshot] = None
    q3_snapshot: Optional[FYSnapshot] = None
    q4_snapshot: Optional[FYSnapshot] = None

    # Monthly data points
    monthly_values: Dict[str, Decimal] = field(default_factory=dict)

    # CGT analysis
    unrealised_gains: Decimal = Decimal("0")
    unrealised_losses: Decimal = Decimal("0")
    potential_cgt_discount: Decimal = Decimal("0")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "financial_year": self.fy_dates.fy_string,
            "period": {
                "start": self.fy_dates.start_date.isoformat(),
                "end": self.fy_dates.end_date.isoformat(),
                "days_elapsed": self.fy_dates.days_elapsed,
                "days_remaining": self.fy_dates.days_remaining,
                "progress_percent": self.fy_dates.progress_percent,
            },
            "performance": {
                "start_value": float(self.start_snapshot.total_value) if self.start_snapshot else None,
                "end_value": float(self.end_snapshot.total_value) if self.end_snapshot else None,
                "value_change": float(self.value_change),
                "value_change_percent": float(self.value_change_percent),
                "profit_change": float(self.profit_change),
            },
            "cgt": {
                "unrealised_gains": float(self.unrealised_gains),
                "unrealised_losses": float(self.unrealised_losses),
                "potential_discount": float(self.potential_cgt_discount),
            },
        }


def get_fy_dates(fy_string: Optional[str] = None) -> FYDates:
    """Get FY dates for a given FY string or current FY."""
    if fy_string is None:
        fy_string = get_financial_year()
    return FYDates.from_fy_string(fy_string)


def find_closest_snapshot(
    snapshots: List[PortfolioSnapshot],
    target_date: date,
    direction: str = "before",
) -> Optional[PortfolioSnapshot]:
    """
    Find snapshot closest to target date.

    Args:
        snapshots: List of snapshots
        target_date: Date to find closest to
        direction: 'before', 'after', or 'nearest'

    Returns:
        Closest snapshot or None
    """
    if not snapshots:
        return None

    candidates = []
    for snap in snapshots:
        if direction == "before" and snap.snapshot_date <= target_date:
            candidates.append(snap)
        elif direction == "after" and snap.snapshot_date >= target_date:
            candidates.append(snap)
        elif direction == "nearest":
            candidates.append(snap)

    if not candidates:
        return None

    if direction == "before":
        return max(candidates, key=lambda s: s.snapshot_date)
    elif direction == "after":
        return min(candidates, key=lambda s: s.snapshot_date)
    else:  # nearest
        return min(candidates, key=lambda s: abs((s.snapshot_date - target_date).days))


def snapshot_to_fy_snapshot(snap: PortfolioSnapshot) -> FYSnapshot:
    """Convert PortfolioSnapshot to FYSnapshot."""
    return FYSnapshot(
        snapshot_date=snap.snapshot_date,
        total_value=snap.total_market_value,
        total_cost=snap.total_cost_base,
        total_profit=snap.total_profit_loss,
        profit_percent=snap.total_profit_loss_percent,
        holding_count=snap.total_holdings,
        snapshot_id=snap.snapshot_id,
    )


def analyze_financial_year(
    db: PortfolioDatabase,
    fy_string: Optional[str] = None,
) -> FYAnalysis:
    """
    Perform comprehensive FY analysis.

    Args:
        db: Database instance
        fy_string: FY string (e.g., "2024-25") or None for current

    Returns:
        FYAnalysis with all metrics
    """
    fy_dates = get_fy_dates(fy_string)
    analysis = FYAnalysis(fy_dates=fy_dates)

    # Get all snapshots
    all_snapshots = db.get_all_snapshots()
    if not all_snapshots:
        return analysis

    # Filter to FY period
    fy_snapshots = [
        s for s in all_snapshots
        if fy_dates.start_date <= s.snapshot_date <= fy_dates.end_date
    ]

    # Find start snapshot (closest to July 1)
    start_snap = find_closest_snapshot(fy_snapshots, fy_dates.start_date, "after")
    if start_snap:
        analysis.start_snapshot = snapshot_to_fy_snapshot(start_snap)

    # Find end snapshot (latest in FY or today)
    target_end = min(date.today(), fy_dates.end_date)
    end_snap = find_closest_snapshot(fy_snapshots, target_end, "before")
    if end_snap:
        analysis.end_snapshot = snapshot_to_fy_snapshot(end_snap)

    # Calculate performance
    if analysis.start_snapshot and analysis.end_snapshot:
        analysis.value_change = (
            analysis.end_snapshot.total_value - analysis.start_snapshot.total_value
        )
        if analysis.start_snapshot.total_value > 0:
            analysis.value_change_percent = (
                analysis.value_change / analysis.start_snapshot.total_value * Decimal("100")
            )
        analysis.profit_change = (
            analysis.end_snapshot.total_profit - analysis.start_snapshot.total_profit
        )

    # Find quarterly snapshots
    analysis.q1_snapshot = _find_quarter_snapshot(fy_snapshots, fy_dates.q1_end)
    analysis.q2_snapshot = _find_quarter_snapshot(fy_snapshots, fy_dates.q2_end)
    analysis.q3_snapshot = _find_quarter_snapshot(fy_snapshots, fy_dates.q3_end)
    analysis.q4_snapshot = _find_quarter_snapshot(fy_snapshots, fy_dates.q4_end)

    # Build monthly values
    for snap in fy_snapshots:
        month_key = snap.snapshot_date.strftime("%Y-%m")
        # Keep latest value for each month
        analysis.monthly_values[month_key] = snap.total_market_value

    # CGT analysis (from latest portfolio)
    latest_portfolio = db.get_latest_portfolio()
    if latest_portfolio:
        unrealised = analyze_unrealised_gains(latest_portfolio)
        analysis.unrealised_gains = unrealised["total_unrealised_gain"]
        analysis.unrealised_losses = unrealised["total_unrealised_loss"]
        analysis.potential_cgt_discount = unrealised["potential_discount"]

    return analysis


def _find_quarter_snapshot(
    snapshots: List[PortfolioSnapshot],
    quarter_end: date,
) -> Optional[FYSnapshot]:
    """Find snapshot closest to quarter end."""
    # Look for snapshot within 7 days of quarter end
    candidates = [
        s for s in snapshots
        if abs((s.snapshot_date - quarter_end).days) <= 7
    ]
    if candidates:
        closest = min(candidates, key=lambda s: abs((s.snapshot_date - quarter_end).days))
        return snapshot_to_fy_snapshot(closest)
    return None


def format_fy_report(analysis: FYAnalysis, portfolio: Optional[Portfolio] = None) -> str:
    """Format FY analysis as a report."""
    lines = []
    fy = analysis.fy_dates

    lines.append("=" * 70)
    lines.append(f"FINANCIAL YEAR ANALYSIS - FY {fy.fy_string}")
    lines.append("=" * 70)

    # FY Progress
    lines.append("\n" + "-" * 70)
    lines.append("FY PROGRESS")
    lines.append("-" * 70)
    lines.append(f"  Period:           {fy.start_date.strftime('%d %b %Y')} to {fy.end_date.strftime('%d %b %Y')}")
    lines.append(f"  Days Elapsed:     {fy.days_elapsed} of {fy.days_total}")
    lines.append(f"  Days Remaining:   {fy.days_remaining}")
    lines.append(f"  Progress:         {fy.progress_percent:.1f}%")
    lines.append(f"  Current Quarter:  {fy.current_quarter}")

    # Progress bar
    bar_width = 40
    filled = int(bar_width * fy.progress_percent / 100)
    bar = "█" * filled + "░" * (bar_width - filled)
    lines.append(f"\n  [{bar}] {fy.progress_percent:.0f}%")

    # Key dates
    today = date.today()
    lines.append(f"\n  Key Dates:")
    lines.append(f"    FY Start (Jul 1):  {fy.start_date} {'✓' if today >= fy.start_date else ''}")
    lines.append(f"    Q1 End (Sep 30):   {fy.q1_end} {'✓' if today >= fy.q1_end else ''}")
    lines.append(f"    Q2 End (Dec 31):   {fy.q2_end} {'✓' if today >= fy.q2_end else ''}")
    lines.append(f"    Q3 End (Mar 31):   {fy.q3_end} {'✓' if today >= fy.q3_end else ''}")
    lines.append(f"    EOFY (Jun 30):     {fy.end_date} {'✓' if today >= fy.end_date else ''}")

    # Performance Summary
    if analysis.start_snapshot and analysis.end_snapshot:
        lines.append("\n" + "-" * 70)
        lines.append("FY PERFORMANCE")
        lines.append("-" * 70)
        lines.append(f"\n  {'Metric':<25} {'Start':>15} {'Current':>15} {'Change':>12}")
        lines.append("  " + "-" * 67)

        lines.append(
            f"  {'Portfolio Value':<25} "
            f"${float(analysis.start_snapshot.total_value):>14,.0f} "
            f"${float(analysis.end_snapshot.total_value):>14,.0f} "
            f"{float(analysis.value_change_percent):>+11.1f}%"
        )
        lines.append(
            f"  {'Unrealised P/L':<25} "
            f"${float(analysis.start_snapshot.total_profit):>+14,.0f} "
            f"${float(analysis.end_snapshot.total_profit):>+14,.0f} "
            f"${float(analysis.profit_change):>+11,.0f}"
        )
        lines.append(
            f"  {'Holdings':<25} "
            f"{analysis.start_snapshot.holding_count:>15} "
            f"{analysis.end_snapshot.holding_count:>15} "
            f"{analysis.end_snapshot.holding_count - analysis.start_snapshot.holding_count:>+12}"
        )

        # Value change
        lines.append(f"\n  FY Value Change:    ${float(analysis.value_change):>+15,.2f}")
        lines.append(f"  FY Return:          {float(analysis.value_change_percent):>+15.2f}%")

    # Quarterly Performance
    quarters = [
        ("Q1 (Jul-Sep)", analysis.q1_snapshot),
        ("Q2 (Oct-Dec)", analysis.q2_snapshot),
        ("Q3 (Jan-Mar)", analysis.q3_snapshot),
        ("Q4 (Apr-Jun)", analysis.q4_snapshot),
    ]
    has_quarters = any(q[1] for q in quarters)

    if has_quarters:
        lines.append("\n" + "-" * 70)
        lines.append("QUARTERLY VALUES")
        lines.append("-" * 70)
        lines.append(f"\n  {'Quarter':<15} {'Date':>12} {'Value':>15} {'P/L':>12}")
        lines.append("  " + "-" * 56)

        for qname, qsnap in quarters:
            if qsnap:
                lines.append(
                    f"  {qname:<15} "
                    f"{qsnap.snapshot_date.strftime('%Y-%m-%d'):>12} "
                    f"${float(qsnap.total_value):>14,.0f} "
                    f"${float(qsnap.total_profit):>+11,.0f}"
                )
            else:
                lines.append(f"  {qname:<15} {'--':>12} {'--':>15} {'--':>12}")

    # CGT Summary
    if analysis.unrealised_gains > 0 or analysis.unrealised_losses > 0:
        lines.append("\n" + "-" * 70)
        lines.append("CGT POSITION (if all sold today)")
        lines.append("-" * 70)
        lines.append(f"  Unrealised Gains:   ${float(analysis.unrealised_gains):>15,.2f}")
        lines.append(f"  Unrealised Losses:  ${float(analysis.unrealised_losses):>15,.2f}")
        lines.append(f"  Net Position:       ${float(analysis.unrealised_gains - analysis.unrealised_losses):>+15,.2f}")
        lines.append(f"  CGT Discount (50%): ${float(analysis.potential_cgt_discount):>15,.2f}")

        taxable = analysis.unrealised_gains - analysis.potential_cgt_discount - analysis.unrealised_losses
        if taxable < 0:
            taxable = Decimal("0")
        lines.append(f"  Est. Taxable Gain:  ${float(taxable):>15,.2f}")

    # EOFY Checklist (if in Q3 or Q4)
    if fy.is_current and fy.current_quarter in ("Q3", "Q4"):
        lines.append("\n" + "-" * 70)
        lines.append("EOFY CHECKLIST")
        lines.append("-" * 70)
        lines.append("\n  □ Review tax-loss harvesting opportunities")
        lines.append("  □ Consider selling loss-making positions before June 30")
        lines.append("  □ Check dividend payment dates (franking credits)")
        lines.append("  □ Review CGT discount eligibility (12-month rule)")
        lines.append("  □ Document cost base for any sales")
        lines.append("  □ Prepare records for tax return")
        if fy.days_remaining <= 30:
            lines.append(f"\n  ⚠️  Only {fy.days_remaining} days until EOFY!")

    lines.append("\n" + "=" * 70)

    return "\n".join(lines)


def compare_financial_years(
    db: PortfolioDatabase,
    fy1: str,
    fy2: str,
) -> Dict[str, Any]:
    """
    Compare two financial years.

    Args:
        db: Database instance
        fy1: First FY (e.g., "2023-24")
        fy2: Second FY (e.g., "2024-25")

    Returns:
        Comparison data
    """
    analysis1 = analyze_financial_year(db, fy1)
    analysis2 = analyze_financial_year(db, fy2)

    return {
        "fy1": fy1,
        "fy2": fy2,
        "fy1_data": analysis1.to_dict(),
        "fy2_data": analysis2.to_dict(),
        "comparison": {
            "value_change_diff": float(analysis2.value_change - analysis1.value_change),
            "return_diff": float(analysis2.value_change_percent - analysis1.value_change_percent),
        }
    }
