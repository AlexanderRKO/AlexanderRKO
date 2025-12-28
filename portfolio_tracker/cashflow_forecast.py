"""
Cashflow Forecast - Dividend calendar and income projections.

Features:
- Monthly dividend payment calendar
- Ex-dividend date tracking
- 12-month cashflow projection
- Dividend growth analysis
- Yield on cost tracking
- DRP (Dividend Reinvestment Plan) simulation
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
from calendar import monthrange
import json

from .models import Portfolio, Holding
from .dividend_tracker import DividendFetcher, DividendInfo, get_portfolio_dividends

logger = logging.getLogger(__name__)


@dataclass
class DividendPayment:
    """Represents an expected dividend payment."""
    code: str
    name: str
    ex_date: Optional[date]
    payment_date: Optional[date]
    amount_per_share: Decimal
    shares_held: int
    expected_payment: Decimal
    franking_percent: Decimal = Decimal("0")
    frequency: str = "unknown"
    is_confirmed: bool = False  # True if from official announcement


@dataclass
class MonthlyForecast:
    """Monthly cashflow forecast."""
    month: date  # First day of month
    month_label: str  # "Jan 2025"
    expected_income: Decimal
    payments: List[DividendPayment]
    cumulative_income: Decimal = Decimal("0")


@dataclass
class CashflowForecast:
    """Complete cashflow forecast for portfolio."""
    portfolio_value: Decimal
    total_cost_base: Decimal
    annual_income: Decimal
    portfolio_yield: Decimal
    yield_on_cost: Decimal
    monthly_forecasts: List[MonthlyForecast]
    upcoming_ex_dates: List[DividendPayment]
    dividend_growth: Dict[str, Any]
    drp_projection: Optional[Dict[str, Any]] = None


def estimate_payment_dates(
    code: str,
    dividend_info: DividendInfo,
    shares: int,
    forecast_months: int = 12,
) -> List[DividendPayment]:
    """
    Estimate future dividend payments based on historical patterns.

    Uses frequency and last known dates to project forward.
    """
    payments = []
    today = date.today()
    end_date = today + timedelta(days=forecast_months * 31)

    if not dividend_info or dividend_info.annual_dividend <= 0:
        return payments

    # Determine payment interval based on frequency
    frequency = dividend_info.frequency.lower() if dividend_info.frequency else "unknown"

    if frequency in ("annual", "yearly"):
        interval_months = 12
        payments_per_year = 1
    elif frequency in ("semi-annual", "biannual", "half-yearly"):
        interval_months = 6
        payments_per_year = 2
    elif frequency in ("quarterly"):
        interval_months = 3
        payments_per_year = 4
    elif frequency in ("monthly"):
        interval_months = 1
        payments_per_year = 12
    else:
        # Default to semi-annual for Australian stocks
        interval_months = 6
        payments_per_year = 2

    # Calculate payment per dividend
    payment_per_div = dividend_info.annual_dividend / Decimal(str(payments_per_year))

    # Start from next expected payment
    # If we have ex-date info, use it; otherwise estimate
    if dividend_info.ex_dividend_date and dividend_info.ex_dividend_date > today:
        next_ex = dividend_info.ex_dividend_date
        # Payment typically 4-6 weeks after ex-date
        next_payment = next_ex + timedelta(days=35)
    else:
        # Estimate based on typical ASX patterns
        # Many pay in Feb/Aug or Mar/Sep
        current_month = today.month
        if interval_months == 6:
            # Find next semi-annual month
            if current_month <= 2:
                next_month = 2
            elif current_month <= 8:
                next_month = 8
            else:
                next_month = 2
                next_ex = date(today.year + 1, next_month, 15)
            if current_month <= 8:
                next_ex = date(today.year, next_month, 15)
        elif interval_months == 3:
            # Quarterly - next quarter end
            quarter_months = [3, 6, 9, 12]
            next_month = min([m for m in quarter_months if m > current_month] or [3])
            if next_month == 3 and current_month >= 10:
                next_ex = date(today.year + 1, next_month, 15)
            else:
                next_ex = date(today.year, next_month, 15)
        else:
            next_ex = today + timedelta(days=30)

        next_payment = next_ex + timedelta(days=35)

    # Generate payments for forecast period
    current_ex = next_ex if 'next_ex' in dir() else today + timedelta(days=30)

    while current_ex <= end_date:
        payment_date = current_ex + timedelta(days=35)

        if payment_date > today:  # Only future payments
            payments.append(DividendPayment(
                code=code,
                name=dividend_info.name if hasattr(dividend_info, 'name') else code,
                ex_date=current_ex,
                payment_date=payment_date,
                amount_per_share=payment_per_div,
                shares_held=shares,
                expected_payment=payment_per_div * Decimal(str(shares)),
                franking_percent=dividend_info.franking_percent,
                frequency=frequency,
                is_confirmed=False,
            ))

        # Move to next payment
        if interval_months == 1:
            current_ex = current_ex + timedelta(days=30)
        elif interval_months == 3:
            current_ex = current_ex + timedelta(days=91)
        elif interval_months == 6:
            current_ex = current_ex + timedelta(days=182)
        else:
            current_ex = current_ex + timedelta(days=365)

    return payments


def generate_cashflow_forecast(
    portfolio: Portfolio,
    dividend_data: Dict[str, Any],
    forecast_months: int = 12,
) -> CashflowForecast:
    """
    Generate a complete cashflow forecast for the portfolio.
    """
    today = date.today()

    # Collect all expected payments
    all_payments: List[DividendPayment] = []

    for holding_data in dividend_data.get("holdings", []):
        code = holding_data["code"]
        holding = portfolio.get_holding(code)
        if not holding:
            continue

        # Create a simple dividend info object
        annual_div = Decimal(str(holding_data.get("annual_dividend", 0)))
        if annual_div <= 0:
            continue

        @dataclass
        class SimpleDivInfo:
            annual_dividend: Decimal
            frequency: str
            franking_percent: Decimal
            ex_dividend_date: Optional[date]
            name: str

        div_info = SimpleDivInfo(
            annual_dividend=annual_div,
            frequency=holding_data.get("frequency", "semi-annual"),
            franking_percent=Decimal(str(holding_data.get("franking_percent", 0))),
            ex_dividend_date=None,
            name=holding_data.get("name", code),
        )

        payments = estimate_payment_dates(
            code=code,
            dividend_info=div_info,
            shares=holding.quantity,
            forecast_months=forecast_months,
        )
        all_payments.extend(payments)

    # Organize by month
    monthly_data: Dict[str, List[DividendPayment]] = {}

    for payment in all_payments:
        if payment.payment_date:
            month_key = payment.payment_date.strftime("%Y-%m")
            if month_key not in monthly_data:
                monthly_data[month_key] = []
            monthly_data[month_key].append(payment)

    # Create monthly forecasts
    monthly_forecasts: List[MonthlyForecast] = []
    cumulative = Decimal("0")

    current = date(today.year, today.month, 1)
    for i in range(forecast_months):
        month_key = current.strftime("%Y-%m")
        month_payments = monthly_data.get(month_key, [])
        month_income = sum(p.expected_payment for p in month_payments)
        cumulative += month_income

        monthly_forecasts.append(MonthlyForecast(
            month=current,
            month_label=current.strftime("%b %Y"),
            expected_income=month_income,
            payments=month_payments,
            cumulative_income=cumulative,
        ))

        # Move to next month
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)

    # Get upcoming ex-dates (next 60 days)
    upcoming_ex = [
        p for p in all_payments
        if p.ex_date and today <= p.ex_date <= today + timedelta(days=60)
    ]
    upcoming_ex.sort(key=lambda x: x.ex_date or today)

    # Calculate yields
    annual_income = sum(mf.expected_income for mf in monthly_forecasts)
    portfolio_yield = (annual_income / portfolio.total_market_value * 100) if portfolio.total_market_value > 0 else Decimal("0")
    yield_on_cost = (annual_income / portfolio.total_cost_base * 100) if portfolio.total_cost_base > 0 else Decimal("0")

    # Dividend growth placeholder (would need historical data)
    dividend_growth = {
        "note": "Dividend growth analysis requires historical dividend data",
        "average_growth": None,
    }

    return CashflowForecast(
        portfolio_value=portfolio.total_market_value,
        total_cost_base=portfolio.total_cost_base,
        annual_income=annual_income,
        portfolio_yield=portfolio_yield,
        yield_on_cost=yield_on_cost,
        monthly_forecasts=monthly_forecasts,
        upcoming_ex_dates=upcoming_ex,
        dividend_growth=dividend_growth,
    )


def simulate_drp(
    portfolio: Portfolio,
    cashflow: CashflowForecast,
    years: int = 10,
    annual_price_growth: Decimal = Decimal("0.05"),
) -> Dict[str, Any]:
    """
    Simulate Dividend Reinvestment Plan over multiple years.

    Shows projected portfolio growth if all dividends are reinvested.
    """
    results = []

    current_value = float(portfolio.total_market_value)
    current_income = float(cashflow.annual_income)
    current_yield = float(cashflow.portfolio_yield) / 100

    for year in range(1, years + 1):
        # Dividends received
        dividends = current_value * current_yield

        # Reinvest dividends (buy more shares at current prices)
        current_value += dividends

        # Price appreciation
        current_value *= (1 + float(annual_price_growth))

        # New income (more shares = more dividends)
        new_income = current_value * current_yield

        results.append({
            "year": year,
            "portfolio_value": current_value,
            "annual_income": new_income,
            "dividends_reinvested": dividends,
            "cumulative_dividends": sum(r["dividends_reinvested"] for r in results) + dividends,
        })

        current_income = new_income

    return {
        "starting_value": float(portfolio.total_market_value),
        "starting_income": float(cashflow.annual_income),
        "ending_value": results[-1]["portfolio_value"] if results else current_value,
        "ending_income": results[-1]["annual_income"] if results else current_income,
        "total_dividends_reinvested": results[-1]["cumulative_dividends"] if results else 0,
        "assumptions": {
            "annual_price_growth": f"{float(annual_price_growth)*100:.1f}%",
            "yield_constant": True,
        },
        "yearly_projections": results,
    }


def format_cashflow_calendar(
    forecast: CashflowForecast,
    show_payments: bool = True,
) -> str:
    """Format cashflow forecast as a calendar view."""
    lines = []

    lines.append("=" * 70)
    lines.append("DIVIDEND CALENDAR & CASHFLOW FORECAST")
    lines.append("=" * 70)

    # Summary
    lines.append("")
    lines.append(f"  Portfolio Value:     ${float(forecast.portfolio_value):>14,.0f}")
    lines.append(f"  Annual Income:       ${float(forecast.annual_income):>14,.0f}")
    lines.append(f"  Portfolio Yield:     {float(forecast.portfolio_yield):>14.2f}%")
    lines.append(f"  Yield on Cost:       {float(forecast.yield_on_cost):>14.2f}%")
    lines.append("")

    # Upcoming Ex-Dates
    if forecast.upcoming_ex_dates:
        lines.append("-" * 70)
        lines.append("UPCOMING EX-DIVIDEND DATES (Next 60 Days)")
        lines.append("-" * 70)
        lines.append(f"  {'Code':<6} {'Ex-Date':<12} {'Payment':<12} {'Amount':>12} {'Days':>6}")
        lines.append("  " + "-" * 54)

        today = date.today()
        for payment in forecast.upcoming_ex_dates[:10]:
            days_to_ex = (payment.ex_date - today).days if payment.ex_date else 0
            ex_str = payment.ex_date.strftime("%Y-%m-%d") if payment.ex_date else "-"
            pay_str = payment.payment_date.strftime("%Y-%m-%d") if payment.payment_date else "-"

            # Highlight if ex-date is soon
            if days_to_ex <= 7:
                code_str = f"⚠️ {payment.code}"
            else:
                code_str = f"  {payment.code}"

            lines.append(
                f"{code_str:<8} {ex_str:<12} {pay_str:<12} "
                f"${float(payment.expected_payment):>10,.0f} {days_to_ex:>6}"
            )
        lines.append("")

    # Monthly Forecast
    lines.append("-" * 70)
    lines.append("12-MONTH CASHFLOW FORECAST")
    lines.append("-" * 70)

    max_income = max(float(mf.expected_income) for mf in forecast.monthly_forecasts) or 1

    for mf in forecast.monthly_forecasts:
        income = float(mf.expected_income)
        bar_len = int(income / max_income * 25) if max_income > 0 else 0
        bar = "█" * bar_len

        lines.append(
            f"  {mf.month_label:<8} ${income:>8,.0f}  {bar}"
        )

        if show_payments and mf.payments:
            for p in mf.payments[:3]:  # Show up to 3 per month
                lines.append(f"             └─ {p.code}: ${float(p.expected_payment):,.0f}")

    lines.append("")
    lines.append("-" * 70)
    total_income = sum(float(mf.expected_income) for mf in forecast.monthly_forecasts)
    monthly_avg = total_income / 12
    lines.append(f"  Total Annual Income:    ${total_income:>12,.0f}")
    lines.append(f"  Monthly Average:        ${monthly_avg:>12,.0f}")
    lines.append("")

    return "\n".join(lines)


def format_drp_projection(drp: Dict[str, Any]) -> str:
    """Format DRP projection results."""
    lines = []

    lines.append("-" * 70)
    lines.append("DRP SIMULATION (10-Year Projection)")
    lines.append("-" * 70)
    lines.append(f"  Assumptions: {drp['assumptions']['annual_price_growth']} annual price growth, constant yield")
    lines.append("")

    lines.append(f"  {'Year':<6} {'Value':>14} {'Income':>12} {'Reinvested':>12}")
    lines.append("  " + "-" * 48)

    lines.append(f"  {'Start':<6} ${drp['starting_value']:>12,.0f} ${drp['starting_income']:>10,.0f}")

    for proj in drp["yearly_projections"]:
        lines.append(
            f"  {proj['year']:<6} ${proj['portfolio_value']:>12,.0f} "
            f"${proj['annual_income']:>10,.0f} ${proj['dividends_reinvested']:>10,.0f}"
        )

    lines.append("")
    lines.append(f"  Total Growth: ${drp['ending_value'] - drp['starting_value']:,.0f} "
                f"({(drp['ending_value'] / drp['starting_value'] - 1) * 100:.0f}%)")
    lines.append(f"  Total Dividends Reinvested: ${drp['total_dividends_reinvested']:,.0f}")
    lines.append("")

    return "\n".join(lines)


def get_dividend_calendar_data(
    portfolio: Portfolio,
    dividend_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Get dividend calendar data in a format suitable for visualization."""
    forecast = generate_cashflow_forecast(portfolio, dividend_data)

    return {
        "summary": {
            "portfolio_value": float(forecast.portfolio_value),
            "annual_income": float(forecast.annual_income),
            "portfolio_yield": float(forecast.portfolio_yield),
            "yield_on_cost": float(forecast.yield_on_cost),
        },
        "monthly": [
            {
                "month": mf.month_label,
                "income": float(mf.expected_income),
                "cumulative": float(mf.cumulative_income),
                "payment_count": len(mf.payments),
            }
            for mf in forecast.monthly_forecasts
        ],
        "upcoming_ex_dates": [
            {
                "code": p.code,
                "ex_date": p.ex_date.isoformat() if p.ex_date else None,
                "payment_date": p.payment_date.isoformat() if p.payment_date else None,
                "amount": float(p.expected_payment),
            }
            for p in forecast.upcoming_ex_dates
        ],
    }
