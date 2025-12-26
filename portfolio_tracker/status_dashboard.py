"""
Status Dashboard - Quick portfolio overview.

Provides a single-command summary of portfolio status.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any

from .models import Portfolio
from .storage import PortfolioDatabase
from .alerts import AlertManager
from .fy_analysis import get_fy_dates, analyze_financial_year
from .formatting import (
    green, red, yellow, blue, cyan, magenta, bold, dim,
    format_money, format_percent, format_change, progress_bar,
    header, subheader, status_badge, sparkline, Box,
    COLORS_ENABLED
)


def get_top_movers(portfolio: Portfolio, count: int = 3) -> Dict[str, List]:
    """Get top gainers and losers by daily change."""
    holdings = [h for h in portfolio.holdings if h.daily_change_percent != 0]

    gainers = sorted(holdings, key=lambda h: h.daily_change_percent, reverse=True)[:count]
    losers = sorted(holdings, key=lambda h: h.daily_change_percent)[:count]

    return {
        "gainers": gainers,
        "losers": [h for h in losers if h.daily_change_percent < 0],
    }


def generate_status_dashboard(
    db: PortfolioDatabase,
    portfolio: Portfolio,
    compact: bool = False,
) -> str:
    """
    Generate a quick status dashboard.

    Args:
        db: Database instance
        portfolio: Current portfolio
        compact: If True, show minimal output

    Returns:
        Formatted dashboard string
    """
    lines = []
    today = date.today()

    # Header
    title = f"PORTFOLIO STATUS - {today.strftime('%d %b %Y')}"
    if COLORS_ENABLED:
        lines.append(bold(cyan("━" * 50)))
        lines.append(bold(f"📊 {title}"))
        lines.append(bold(cyan("━" * 50)))
    else:
        lines.append("=" * 50)
        lines.append(title)
        lines.append("=" * 50)

    # Main value
    value = float(portfolio.total_market_value)
    profit = float(portfolio.total_profit_loss)
    profit_pct = float(portfolio.total_profit_loss_percent)

    lines.append("")
    lines.append(f"  {bold('Value:')}  {format_money(value)}")
    lines.append(f"  {bold('P/L:')}    {format_money(profit, show_sign=True)} ({format_percent(profit_pct)})")

    # Daily change (sum of all holdings)
    daily_change = sum(float(h.value_change) for h in portfolio.holdings)
    daily_pct = (daily_change / value * 100) if value > 0 else 0
    lines.append(f"  {bold('Today:')} {format_change(daily_change)} ({format_percent(daily_pct)})")

    if compact:
        return "\n".join(lines)

    # Top movers
    movers = get_top_movers(portfolio)
    if movers["gainers"] or movers["losers"]:
        lines.append("")
        lines.append(dim("─" * 50))
        lines.append(bold("  Top Movers"))

        if movers["gainers"]:
            gainer_strs = [
                f"{h.code} {format_percent(float(h.daily_change_percent))}"
                for h in movers["gainers"][:3]
            ]
            lines.append(f"  {green('▲')} {', '.join(gainer_strs)}")

        if movers["losers"]:
            loser_strs = [
                f"{h.code} {format_percent(float(h.daily_change_percent))}"
                for h in movers["losers"][:3]
            ]
            lines.append(f"  {red('▼')} {', '.join(loser_strs)}")

    # Alerts
    alert_manager = AlertManager()
    active_alerts = alert_manager.get_active_alerts()
    triggered = alert_manager.get_triggered_alerts()

    if active_alerts or triggered:
        lines.append("")
        lines.append(dim("─" * 50))
        lines.append(bold("  Alerts"))

        if triggered:
            lines.append(f"  {yellow('⚠')} {len(triggered)} triggered")
        if active_alerts:
            lines.append(f"  {blue('●')} {len(active_alerts)} active")

    # FY Progress
    fy_dates = get_fy_dates()
    lines.append("")
    lines.append(dim("─" * 50))
    lines.append(bold(f"  FY {fy_dates.fy_string}"))
    lines.append(f"  {progress_bar(fy_dates.days_elapsed, fy_dates.days_total, width=25)}")
    lines.append(f"  {dim(f'{fy_dates.days_remaining} days to EOFY')}")

    # CGT quick summary
    analysis = analyze_financial_year(db)
    if analysis.unrealised_gains > 0:
        net_taxable = analysis.unrealised_gains - analysis.potential_cgt_discount - analysis.unrealised_losses
        if net_taxable < 0:
            net_taxable = Decimal("0")
        lines.append(f"  Est. taxable: {format_money(float(net_taxable))}")

    # Holdings summary
    lines.append("")
    lines.append(dim("─" * 50))
    profitable = len(portfolio.profitable_holdings)
    losing = len(portfolio.losing_holdings)
    lines.append(f"  {bold('Holdings:')} {portfolio.holding_count} ({green(str(profitable))} up, {red(str(losing))} down)")

    # Quick actions hint
    lines.append("")
    lines.append(dim("  Tip: Run 'view' for details, 'help' for commands"))

    if COLORS_ENABLED:
        lines.append(bold(cyan("━" * 50)))
    else:
        lines.append("=" * 50)

    return "\n".join(lines)


def generate_welcome_message(has_data: bool = False) -> str:
    """Generate welcome/onboarding message."""
    lines = []

    if COLORS_ENABLED:
        lines.append(bold(cyan("━" * 55)))
        lines.append(bold("  📈 Welcome to Portfolio Tracker"))
        lines.append(bold(cyan("━" * 55)))
    else:
        lines.append("=" * 55)
        lines.append("  Welcome to Portfolio Tracker")
        lines.append("=" * 55)

    if not has_data:
        lines.append("")
        lines.append("  No portfolio data found. Let's get started!")
        lines.append("")
        lines.append(bold("  Quick Start:"))
        lines.append("  1. Export your portfolio from CommSec as CSV")
        lines.append("  2. Run: " + cyan("portfolio import <your_file.csv>"))
        lines.append("")
        lines.append(dim("  Example:"))
        lines.append(dim("  $ portfolio import ~/Downloads/portfolio.csv"))
    else:
        lines.append("")
        lines.append("  Your portfolio is ready!")
        lines.append("")
        lines.append(bold("  Quick Commands:"))
        lines.append(f"  {cyan('status')}    - Quick overview")
        lines.append(f"  {cyan('view')}      - Full portfolio")
        lines.append(f"  {cyan('sectors')}   - Sector breakdown")
        lines.append(f"  {cyan('dividends')} - Dividend analysis")
        lines.append(f"  {cyan('tax')}       - Tax report")
        lines.append(f"  {cyan('fy')}        - Financial year")
        lines.append(f"  {cyan('web')}       - Web dashboard")

    lines.append("")
    lines.append(dim("  Run 'portfolio --help' for all commands"))

    if COLORS_ENABLED:
        lines.append(bold(cyan("━" * 55)))
    else:
        lines.append("=" * 55)

    return "\n".join(lines)


# Command aliases
COMMAND_ALIASES = {
    "s": "status",
    "st": "status",
    "v": "view",
    "q": "quote",
    "u": "update",
    "a": "analyze",
    "h": "holding",
    "sec": "sectors",
    "div": "dividends",
    "t": "tax",
    "c": "changes",
    "w": "web",
    "al": "alerts",
    "i": "import",
    "e": "export",
}


def resolve_alias(command: str) -> str:
    """Resolve a command alias to the full command."""
    return COMMAND_ALIASES.get(command, command)
