"""
Tax Reporting - Australian CGT calculations and tax summaries.

Provides Capital Gains Tax calculations for Australian investors including:
- CGT discount (50% for assets held > 12 months)
- Franking credits tracking
- EOFY tax report generation
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple

from .models import Portfolio, Holding

logger = logging.getLogger(__name__)

# Australian tax constants
CGT_DISCOUNT_PERCENT = Decimal("50")  # 50% discount for assets held > 12 months
CGT_DISCOUNT_HOLDING_DAYS = 365  # Must hold for at least 12 months
COMPANY_TAX_RATE = Decimal("30")  # Company tax rate for franking credits


class CGTMethod(Enum):
    """CGT calculation methods."""
    FIFO = "fifo"  # First In, First Out
    LIFO = "lifo"  # Last In, First Out
    AVERAGE = "average"  # Average cost method
    SPECIFIC = "specific"  # Specific identification


@dataclass
class CapitalGain:
    """Represents a capital gain/loss on a holding."""
    code: str
    name: str
    quantity: int
    cost_base: Decimal
    proceeds: Decimal
    gross_gain: Decimal
    holding_period_days: int
    eligible_for_discount: bool
    discount_amount: Decimal
    net_gain: Decimal
    acquisition_date: Optional[date] = None
    disposal_date: Optional[date] = None

    @property
    def is_loss(self) -> bool:
        return self.gross_gain < 0


@dataclass
class DividendIncome:
    """Dividend income with franking credits."""
    code: str
    name: str
    gross_dividend: Decimal
    franking_credit: Decimal
    franking_percent: Decimal
    net_dividend: Decimal  # What you actually received

    @property
    def assessable_income(self) -> Decimal:
        """Total assessable income (dividend + franking credit)."""
        return self.net_dividend + self.franking_credit


@dataclass
class TaxSummary:
    """Annual tax summary for EOFY."""
    financial_year: str  # e.g., "2024-25"

    # Capital Gains
    total_capital_gains: Decimal = Decimal("0")
    total_capital_losses: Decimal = Decimal("0")
    discount_eligible_gains: Decimal = Decimal("0")
    cgt_discount_applied: Decimal = Decimal("0")
    net_capital_gain: Decimal = Decimal("0")

    # Dividends
    total_dividends: Decimal = Decimal("0")
    total_franking_credits: Decimal = Decimal("0")

    # Details
    capital_gains_detail: List[CapitalGain] = field(default_factory=list)
    dividend_detail: List[DividendIncome] = field(default_factory=list)

    # Unrealised (for planning)
    unrealised_gains: Decimal = Decimal("0")
    unrealised_losses: Decimal = Decimal("0")
    potential_cgt_discount: Decimal = Decimal("0")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "financial_year": self.financial_year,
            "capital_gains": {
                "total_gains": float(self.total_capital_gains),
                "total_losses": float(self.total_capital_losses),
                "discount_eligible": float(self.discount_eligible_gains),
                "discount_applied": float(self.cgt_discount_applied),
                "net_capital_gain": float(self.net_capital_gain),
            },
            "dividends": {
                "total_dividends": float(self.total_dividends),
                "franking_credits": float(self.total_franking_credits),
            },
            "unrealised": {
                "gains": float(self.unrealised_gains),
                "losses": float(self.unrealised_losses),
                "potential_discount": float(self.potential_cgt_discount),
            },
        }


def get_financial_year(for_date: Optional[date] = None) -> str:
    """
    Get Australian financial year string.
    FY runs July 1 to June 30.
    """
    if for_date is None:
        for_date = date.today()

    if for_date.month >= 7:  # July onwards = next FY
        return f"{for_date.year}-{str(for_date.year + 1)[2:]}"
    else:
        return f"{for_date.year - 1}-{str(for_date.year)[2:]}"


def calculate_cgt_discount(
    gross_gain: Decimal,
    holding_period_days: int,
) -> Tuple[bool, Decimal]:
    """
    Calculate CGT discount eligibility and amount.

    Args:
        gross_gain: The gross capital gain
        holding_period_days: Days the asset was held

    Returns:
        Tuple of (eligible, discount_amount)
    """
    if gross_gain <= 0:
        return False, Decimal("0")

    if holding_period_days >= CGT_DISCOUNT_HOLDING_DAYS:
        discount = (gross_gain * CGT_DISCOUNT_PERCENT / Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        return True, discount

    return False, Decimal("0")


def calculate_franking_credit(
    dividend: Decimal,
    franking_percent: Decimal = Decimal("100"),
) -> Decimal:
    """
    Calculate franking credit for a dividend.

    Formula: Dividend × (Franking % / 100) × (Tax Rate / (1 - Tax Rate))
    For 100% franked at 30% rate: Dividend × 0.4286
    """
    if franking_percent <= 0:
        return Decimal("0")

    franking_ratio = franking_percent / Decimal("100")
    tax_multiplier = COMPANY_TAX_RATE / (Decimal("100") - COMPANY_TAX_RATE)

    credit = (dividend * franking_ratio * tax_multiplier).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return credit


def analyze_unrealised_gains(
    portfolio: Portfolio,
    assumed_holding_days: int = 365,
) -> Dict[str, Any]:
    """
    Analyze unrealised capital gains in portfolio.

    Args:
        portfolio: Current portfolio
        assumed_holding_days: Assumed holding period for discount eligibility

    Returns:
        Dictionary with unrealised gain analysis
    """
    gains = []
    losses = []
    total_unrealised_gain = Decimal("0")
    total_unrealised_loss = Decimal("0")
    discount_eligible_total = Decimal("0")

    for holding in portfolio.holdings:
        if holding.profit_loss > 0:
            gains.append(holding)
            total_unrealised_gain += holding.profit_loss

            # Check discount eligibility (assume > 12 months if not tracked)
            if assumed_holding_days >= CGT_DISCOUNT_HOLDING_DAYS:
                discount_eligible_total += holding.profit_loss
        else:
            losses.append(holding)
            total_unrealised_loss += abs(holding.profit_loss)

    # Potential CGT discount
    potential_discount = (discount_eligible_total * CGT_DISCOUNT_PERCENT / Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    # Net position
    net_unrealised = total_unrealised_gain - total_unrealised_loss

    # After discount
    taxable_if_sold = total_unrealised_gain - potential_discount - total_unrealised_loss
    if taxable_if_sold < 0:
        taxable_if_sold = Decimal("0")

    return {
        "total_unrealised_gain": total_unrealised_gain,
        "total_unrealised_loss": total_unrealised_loss,
        "net_unrealised": net_unrealised,
        "discount_eligible": discount_eligible_total,
        "potential_discount": potential_discount,
        "taxable_if_sold_now": taxable_if_sold,
        "holdings_in_profit": len(gains),
        "holdings_in_loss": len(losses),
        "gains_detail": [
            {
                "code": h.code,
                "profit": float(h.profit_loss),
                "profit_percent": float(h.profit_loss_percent),
            }
            for h in sorted(gains, key=lambda x: x.profit_loss, reverse=True)[:10]
        ],
        "losses_detail": [
            {
                "code": h.code,
                "loss": float(abs(h.profit_loss)),
                "loss_percent": float(abs(h.profit_loss_percent)),
            }
            for h in sorted(losses, key=lambda x: x.profit_loss)[:10]
        ],
    }


def generate_tax_report(
    portfolio: Portfolio,
    financial_year: Optional[str] = None,
) -> TaxSummary:
    """
    Generate a tax report for the portfolio.

    Note: This provides estimates based on current holdings.
    Actual CGT depends on sale dates and purchase dates.

    Args:
        portfolio: Current portfolio
        financial_year: FY string (auto-detected if None)

    Returns:
        TaxSummary with tax estimates
    """
    if financial_year is None:
        financial_year = get_financial_year()

    summary = TaxSummary(financial_year=financial_year)

    # Analyze unrealised positions
    unrealised = analyze_unrealised_gains(portfolio)
    summary.unrealised_gains = unrealised["total_unrealised_gain"]
    summary.unrealised_losses = unrealised["total_unrealised_loss"]
    summary.potential_cgt_discount = unrealised["potential_discount"]

    # Dividend income (from portfolio totals)
    summary.total_dividends = portfolio.total_dividends
    summary.total_franking_credits = portfolio.total_franking_credits

    # Build dividend detail
    for holding in portfolio.holdings:
        if holding.dividends_received > 0:
            # Estimate franking credit if not tracked
            franking = holding.franking_credits
            if franking == 0 and holding.dividends_received > 0:
                # Assume 100% franked as estimate
                franking = calculate_franking_credit(holding.dividends_received)

            summary.dividend_detail.append(DividendIncome(
                code=holding.code,
                name=holding.name,
                gross_dividend=holding.dividends_received + franking,
                franking_credit=franking,
                franking_percent=Decimal("100"),  # Assumed
                net_dividend=holding.dividends_received,
            ))

    return summary


def format_tax_report(summary: TaxSummary, portfolio: Portfolio) -> str:
    """Format tax report for display."""
    lines = []

    lines.append("=" * 70)
    lines.append(f"TAX REPORT - FY {summary.financial_year}")
    lines.append("=" * 70)

    # Disclaimer
    lines.append("\n⚠️  DISCLAIMER: This is an estimate only. Consult a tax professional.")
    lines.append("    Actual CGT depends on purchase dates and sale dates.\n")

    # Portfolio Summary
    lines.append("-" * 70)
    lines.append("PORTFOLIO SUMMARY")
    lines.append("-" * 70)
    lines.append(f"  Total Market Value:     ${float(portfolio.total_market_value):>15,.2f}")
    lines.append(f"  Total Cost Base:        ${float(portfolio.total_cost_base):>15,.2f}")
    lines.append(f"  Total Profit/Loss:      ${float(portfolio.total_profit_loss):>+15,.2f}")

    # Unrealised Gains Analysis
    lines.append("\n" + "-" * 70)
    lines.append("UNREALISED CAPITAL GAINS (if sold today)")
    lines.append("-" * 70)
    lines.append(f"  Gross Capital Gains:    ${float(summary.unrealised_gains):>15,.2f}")
    lines.append(f"  Capital Losses:         ${float(summary.unrealised_losses):>15,.2f}")
    lines.append(f"  Net Unrealised:         ${float(summary.unrealised_gains - summary.unrealised_losses):>+15,.2f}")
    lines.append("")
    lines.append(f"  CGT Discount (50%)*:    ${float(summary.potential_cgt_discount):>15,.2f}")
    lines.append(f"  Estimated Taxable:      ${float(summary.unrealised_gains - summary.potential_cgt_discount - summary.unrealised_losses):>15,.2f}")
    lines.append("")
    lines.append("  * Assumes all gains held > 12 months")

    # Dividend Income
    if summary.total_dividends > 0 or summary.total_franking_credits > 0:
        lines.append("\n" + "-" * 70)
        lines.append("DIVIDEND INCOME")
        lines.append("-" * 70)
        lines.append(f"  Cash Dividends:         ${float(summary.total_dividends):>15,.2f}")
        lines.append(f"  Franking Credits:       ${float(summary.total_franking_credits):>15,.2f}")
        lines.append(f"  Assessable Income:      ${float(summary.total_dividends + summary.total_franking_credits):>15,.2f}")

    # Tax Loss Harvesting Opportunities
    losses = [h for h in portfolio.holdings if h.profit_loss < 0]
    if losses:
        losses_sorted = sorted(losses, key=lambda x: x.profit_loss)[:5]
        lines.append("\n" + "-" * 70)
        lines.append("TAX LOSS HARVESTING OPPORTUNITIES")
        lines.append("-" * 70)
        lines.append(f"\n  {'Code':<6} {'Loss':>12} {'Value':>12} {'Weight':>8}")
        lines.append("  " + "-" * 42)
        for h in losses_sorted:
            lines.append(
                f"  {h.code:<6} "
                f"${float(h.profit_loss):>+11,.0f} "
                f"${float(h.market_value):>11,.0f} "
                f"{float(h.portfolio_weight):>7.1f}%"
            )
        total_harvestable = sum(abs(h.profit_loss) for h in losses)
        lines.append("  " + "-" * 42)
        lines.append(f"  {'TOTAL':<6} ${float(-total_harvestable):>+11,.0f}")

    # CGT Discount Eligible Holdings (gains held > 12 months assumed)
    gains = [h for h in portfolio.holdings if h.profit_loss > 0]
    if gains:
        gains_sorted = sorted(gains, key=lambda x: x.profit_loss, reverse=True)[:5]
        lines.append("\n" + "-" * 70)
        lines.append("TOP CAPITAL GAINS (50% CGT discount assumed)")
        lines.append("-" * 70)
        lines.append(f"\n  {'Code':<6} {'Gain':>12} {'Taxable*':>12} {'Value':>12}")
        lines.append("  " + "-" * 46)
        for h in gains_sorted:
            taxable = h.profit_loss * Decimal("0.5")  # After 50% discount
            lines.append(
                f"  {h.code:<6} "
                f"${float(h.profit_loss):>+11,.0f} "
                f"${float(taxable):>11,.0f} "
                f"${float(h.market_value):>11,.0f}"
            )
        lines.append("\n  * After 50% CGT discount for holdings > 12 months")

    lines.append("\n" + "=" * 70)

    return "\n".join(lines)
