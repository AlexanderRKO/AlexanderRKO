#!/usr/bin/env python3
"""
Portfolio Tracker - Main Entry Point

Command-line interface for managing and analyzing CommSec portfolio exports.

Usage:
    python -m portfolio_tracker import <csv_file>
    python -m portfolio_tracker view [--snapshot ID]
    python -m portfolio_tracker analyze [--snapshot ID]
    python -m portfolio_tracker query --min-return 10
    python -m portfolio_tracker history
    python -m portfolio_tracker compare --old ID --new ID
"""

import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path
from decimal import Decimal

from .parser import CommSecCSVParser
from .storage import PortfolioDatabase, export_portfolio_to_csv
from .analysis import PortfolioAnalyzer, generate_portfolio_report, compare_snapshots
from .visualizer import PortfolioVisualizer, plot_portfolio_history, plot_allocation_pie
from .price_fetcher import ASXPriceFetcher, update_portfolio_prices
from .sector_lookup import classify_portfolio, get_sector_summary
from .dividend_tracker import DividendFetcher, get_portfolio_dividends, calculate_income_projection
from .alerts import AlertManager, AlertType, format_alert_list, format_triggered_alerts

# Optional web dashboard (requires Flask)
try:
    from .web_dashboard import run_dashboard
except ImportError:
    run_dashboard = None

from .tax_reporting import generate_tax_report, format_tax_report, get_financial_year, analyze_unrealised_gains
from .change_tracker import compare_portfolios, get_fy_comparison, generate_change_report, get_import_history

# Configure data directory
DATA_DIR = Path(__file__).parent.parent / "data"
PORTFOLIO_DATA_DIR = DATA_DIR / "portfolio"


def ensure_directories():
    """Create necessary directories."""
    DATA_DIR.mkdir(exist_ok=True)
    PORTFOLIO_DATA_DIR.mkdir(exist_ok=True)


def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def cmd_import(args):
    """Import a CommSec CSV file."""
    csv_path = Path(args.csv_file)

    if not csv_path.exists():
        print(f"Error: File not found: {csv_path}")
        sys.exit(1)

    print(f"Importing portfolio from: {csv_path}")

    parser = CommSecCSVParser()
    portfolio = parser.parse_file(csv_path)

    # Show warnings/errors from parsing
    if parser.warnings:
        print("\nWarnings:")
        for w in parser.warnings[:5]:
            print(f"  - {w}")

    if parser.errors:
        print("\nErrors:")
        for e in parser.errors[:5]:
            print(f"  - {e}")

    # Save to database
    db = PortfolioDatabase()
    db.initialize()
    snapshot_id = db.save_portfolio(portfolio)

    print("\n" + "=" * 50)
    print("IMPORT COMPLETE")
    print("=" * 50)
    print(f"Snapshot ID:    {snapshot_id}")
    print(f"Snapshot Date:  {portfolio.snapshot_date}")
    print(f"Holdings:       {portfolio.holding_count}")
    print(f"Total Value:    ${float(portfolio.total_market_value):,.2f}")
    print(f"Total P/L:      ${float(portfolio.total_profit_loss):,.2f} ({float(portfolio.total_profit_loss_percent):+.2f}%)")

    # Quick top 5 view
    print("\nTop 5 Holdings:")
    for h in portfolio.top_holdings[:5]:
        print(f"  {h.code:<6} ${float(h.market_value):>12,.2f} ({float(h.portfolio_weight):.1f}%)")


def cmd_view(args):
    """View portfolio holdings."""
    db = PortfolioDatabase()
    db.initialize()

    if args.snapshot:
        portfolio = db.get_portfolio(args.snapshot)
        if not portfolio:
            print(f"Snapshot not found: {args.snapshot}")
            sys.exit(1)
    else:
        portfolio = db.get_latest_portfolio()
        if not portfolio:
            print("No portfolio data found. Import a CSV first with: portfolio import <file.csv>")
            sys.exit(1)

    viz = PortfolioVisualizer(portfolio)

    if args.dashboard:
        print(viz.dashboard())
    else:
        print(viz._summary_box())
        print()
        print(viz.holdings_table(limit=args.limit))


def cmd_analyze(args):
    """Analyze portfolio."""
    db = PortfolioDatabase()
    db.initialize()

    if args.snapshot:
        portfolio = db.get_portfolio(args.snapshot)
        if not portfolio:
            print(f"Snapshot not found: {args.snapshot}")
            sys.exit(1)
    else:
        portfolio = db.get_latest_portfolio()
        if not portfolio:
            print("No portfolio data found. Import a CSV first.")
            sys.exit(1)

    if args.report:
        # Full text report
        print(generate_portfolio_report(portfolio))
    else:
        # Summary analysis
        analyzer = PortfolioAnalyzer(portfolio)
        summary = analyzer.get_summary()

        print("\n" + "=" * 50)
        print("PORTFOLIO ANALYSIS")
        print("=" * 50)

        print(f"\nDate: {summary['snapshot_date']}")
        print(f"Holdings: {summary['total_holdings']}")
        print(f"Market Value: ${summary['total_market_value']:,.2f}")
        print(f"Total P/L: ${summary['total_profit_loss']:,.2f} ({summary['total_profit_loss_percent']:+.2f}%)")

        perf = analyzer.get_performance_metrics()
        print(f"\nPerformance:")
        print(f"  Winners: {perf.winners_count} ({float(perf.win_rate):.1f}%)")
        print(f"  Losers: {perf.losers_count}")
        if perf.best_performer:
            print(f"  Best: {perf.best_performer.code} ({float(perf.best_performer.profit_loss_percent):+.2f}%)")
        if perf.worst_performer:
            print(f"  Worst: {perf.worst_performer.code} ({float(perf.worst_performer.profit_loss_percent):+.2f}%)")

        conc = summary['concentration']
        print(f"\nConcentration Risk: {conc['risk_level'].upper()}")
        print(f"  Top Holding: {conc['top_holding_weight']:.1f}%")
        print(f"  Top 5: {conc['top_5_weight']:.1f}%")
        print(f"  Effective Holdings: {conc['effective_holdings']:.1f}")

        print("\nAsset Class Allocation:")
        for ac, weight in summary['asset_class_breakdown'].items():
            if weight >= 1:  # Only show >1%
                print(f"  {ac.replace('_', ' ').title()}: {weight:.1f}%")

        # Rebalancing suggestions
        suggestions = analyzer.identify_rebalancing_opportunities()
        if suggestions:
            print("\nRebalancing Suggestions:")
            for s in suggestions[:5]:
                print(f"  - {s['suggestion']}")


def cmd_query(args):
    """Query holdings with filters."""
    db = PortfolioDatabase()
    db.initialize()

    portfolio = db.get_latest_portfolio()
    if not portfolio:
        print("No portfolio data found.")
        sys.exit(1)

    analyzer = PortfolioAnalyzer(portfolio)

    # Build filters from args
    filters = {}
    if args.min_value:
        filters["min_value"] = args.min_value
    if args.max_value:
        filters["max_value"] = args.max_value
    if args.min_return:
        filters["min_return"] = args.min_return
    if args.max_return:
        filters["max_return"] = args.max_return
    if args.profitable is not None:
        filters["profitable"] = args.profitable
    if args.asset_class:
        filters["asset_class"] = args.asset_class
    if args.min_weight:
        filters["min_weight"] = args.min_weight

    results = analyzer.query_holdings(**filters)

    if not results:
        print("No holdings match the specified criteria.")
        return

    print(f"\nFound {len(results)} matching holdings:\n")
    print(f"{'Code':<6} {'Name':<30} {'Value':>12} {'P/L %':>8} {'Weight':>7}")
    print("-" * 70)

    for h in sorted(results, key=lambda x: x.market_value, reverse=True):
        name = h.name[:29] + "…" if len(h.name) > 30 else h.name
        print(
            f"{h.code:<6} {name:<30} "
            f"${float(h.market_value):>11,.2f} "
            f"{float(h.profit_loss_percent):>+7.2f}% "
            f"{float(h.portfolio_weight):>6.1f}%"
        )

    print("-" * 70)
    total_value = sum(h.market_value for h in results)
    total_weight = sum(h.portfolio_weight for h in results)
    print(f"{'TOTAL':<6} {'':<30} ${float(total_value):>11,.2f} {'':<8} {float(total_weight):>6.1f}%")


def cmd_history(args):
    """Show portfolio history."""
    db = PortfolioDatabase()
    db.initialize()

    snapshots = db.get_all_snapshots()

    if not snapshots:
        print("No portfolio history found.")
        return

    print("\n" + "=" * 70)
    print("PORTFOLIO HISTORY")
    print("=" * 70)
    print(f"{'ID':<14} {'Date':<12} {'Holdings':>8} {'Value':>15} {'P/L':>15} {'P/L %':>8}")
    print("-" * 70)

    for s in snapshots[:20]:  # Show last 20
        print(
            f"{s.snapshot_id:<14} "
            f"{s.snapshot_date.isoformat():<12} "
            f"{s.total_holdings:>8} "
            f"${float(s.total_market_value):>14,.2f} "
            f"${float(s.total_profit_loss):>14,.2f} "
            f"{float(s.total_profit_loss_percent):>+7.2f}%"
        )

    if len(snapshots) > 20:
        print(f"\n... and {len(snapshots) - 20} more snapshots")

    # Value chart if matplotlib available
    if args.chart and len(snapshots) >= 2:
        chart_path = PORTFOLIO_DATA_DIR / "history_chart.png"
        result = plot_portfolio_history(snapshots, chart_path)
        if result:
            print(f"\nChart saved to: {result}")


def cmd_compare(args):
    """Compare two portfolio snapshots."""
    db = PortfolioDatabase()
    db.initialize()

    old_portfolio = db.get_portfolio(args.old)
    new_portfolio = db.get_portfolio(args.new)

    if not old_portfolio:
        print(f"Snapshot not found: {args.old}")
        sys.exit(1)
    if not new_portfolio:
        print(f"Snapshot not found: {args.new}")
        sys.exit(1)

    comparison = compare_snapshots(old_portfolio, new_portfolio)

    print("\n" + "=" * 50)
    print("PORTFOLIO COMPARISON")
    print("=" * 50)
    print(f"Old: {comparison['old_date']} -> New: {comparison['new_date']}")

    print(f"\nValue Change:")
    print(f"  ${comparison['old_total_value']:,.2f} -> ${comparison['new_total_value']:,.2f}")
    print(f"  Change: ${comparison['value_change']:,.2f} ({comparison['value_change_percent']:+.2f}%)")

    if comparison['holdings_added']:
        print(f"\nNew Holdings Added: {', '.join(comparison['holdings_added'])}")

    if comparison['holdings_removed']:
        print(f"Holdings Removed: {', '.join(comparison['holdings_removed'])}")

    if comparison['holding_changes']:
        print("\nSignificant Changes:")
        for change in sorted(comparison['holding_changes'], key=lambda x: abs(x['price_change_pct']), reverse=True)[:10]:
            if change['quantity_change'] != 0:
                qty_str = f" (qty: {change['quantity_change']:+d})"
            else:
                qty_str = ""
            print(
                f"  {change['code']}: ${change['old_price']:.2f} -> ${change['new_price']:.2f} "
                f"({change['price_change_pct']:+.2f}%){qty_str}"
            )


def cmd_export(args):
    """Export portfolio to file."""
    db = PortfolioDatabase()
    db.initialize()

    if args.snapshot:
        portfolio = db.get_portfolio(args.snapshot)
        if not portfolio:
            print(f"Snapshot not found: {args.snapshot}")
            sys.exit(1)
    else:
        portfolio = db.get_latest_portfolio()
        if not portfolio:
            print("No portfolio data found.")
            sys.exit(1)

    output_path = Path(args.output) if args.output else PORTFOLIO_DATA_DIR

    if args.format == "csv":
        filepath = output_path / f"portfolio_export_{portfolio.snapshot_date}.csv"
        export_portfolio_to_csv(portfolio, filepath)
    elif args.format == "json":
        filepath = output_path / f"portfolio_export_{portfolio.snapshot_date}.json"
        with open(filepath, "w") as f:
            json.dump(portfolio.to_dict(), f, indent=2)
    elif args.format == "report":
        filepath = output_path / f"portfolio_report_{portfolio.snapshot_date}.txt"
        with open(filepath, "w") as f:
            f.write(generate_portfolio_report(portfolio))

    print(f"Exported to: {filepath}")


def cmd_stats(args):
    """Show database statistics."""
    db = PortfolioDatabase()
    db.initialize()

    stats = db.get_statistics()

    print("\n" + "=" * 40)
    print("DATABASE STATISTICS")
    print("=" * 40)
    print(f"Total Snapshots:     {stats['total_snapshots']}")
    print(f"Unique Holdings:     {stats['unique_holdings']}")
    print(f"Date Range:          {stats['date_range']['min']} to {stats['date_range']['max']}")
    print(f"Latest Value:        ${stats['latest_portfolio_value']:,.2f}")

    # Show unique holdings
    if args.holdings:
        print("\nAll Holdings Ever Tracked:")
        for code in db.get_unique_holdings():
            print(f"  {code}")


def cmd_holding(args):
    """Show details for a specific holding."""
    db = PortfolioDatabase()
    db.initialize()

    code = args.code.upper()

    # Get current portfolio
    portfolio = db.get_latest_portfolio()
    if not portfolio:
        print("No portfolio data found.")
        sys.exit(1)

    holding = portfolio.get_holding(code)
    if not holding:
        print(f"Holding not found: {code}")
        print(f"Available holdings: {', '.join(h.code for h in portfolio.holdings)}")
        sys.exit(1)

    print("\n" + "=" * 50)
    print(f"HOLDING: {holding.code} - {holding.name}")
    print("=" * 50)

    print(f"\nPosition Details:")
    print(f"  Quantity:       {holding.quantity:,}")
    print(f"  Avg Cost:       ${float(holding.avg_cost):.4f}")
    print(f"  Current Price:  ${float(holding.current_price):.4f}")
    print(f"  Cost Base:      ${float(holding.cost_base):,.2f}")
    print(f"  Market Value:   ${float(holding.market_value):,.2f}")

    print(f"\nPerformance:")
    pl_indicator = "▲" if holding.profit_loss >= 0 else "▼"
    print(f"  P/L:            {pl_indicator} ${float(holding.profit_loss):,.2f} ({float(holding.profit_loss_percent):+.2f}%)")
    print(f"  Portfolio Wt:   {float(holding.portfolio_weight):.2f}%")

    print(f"\nClassification:")
    print(f"  Asset Class:    {holding.asset_class.value.replace('_', ' ').title()}")
    print(f"  Sector:         {holding.sector.value.replace('_', ' ').title()}")

    # Historical data
    history = db.get_holding_history(code)
    if len(history) > 1:
        print(f"\nHistory ({len(history)} snapshots):")
        for h in history[-5:]:
            print(f"  {h['date']}: {h['quantity']:,} @ ${float(h['current_price']):.2f} = ${float(h['market_value']):,.2f}")


def cmd_update(args):
    """Update portfolio with live ASX prices."""
    db = PortfolioDatabase()
    db.initialize()

    portfolio = db.get_latest_portfolio()
    if not portfolio:
        print("No portfolio data found. Import a CSV first.")
        sys.exit(1)

    print(f"Updating prices for {portfolio.holding_count} holdings...")
    print(f"Current value: ${float(portfolio.total_market_value):,.2f}")

    try:
        fetcher = ASXPriceFetcher()
        result = update_portfolio_prices(portfolio, fetcher)
    except ImportError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error fetching prices: {e}")
        sys.exit(1)

    print("\n" + "=" * 50)
    print("PRICE UPDATE COMPLETE")
    print("=" * 50)
    print(f"Updated:     {result['updated']}/{result['total']} holdings")
    if result['failed'] > 0:
        print(f"Failed:      {result['failed']} (check logs)")

    print(f"\nPortfolio Value:")
    print(f"  Before:    ${result['old_value']:>15,.2f}")
    print(f"  After:     ${result['new_value']:>15,.2f}")

    change = result['value_change']
    change_pct = (change / result['old_value'] * 100) if result['old_value'] > 0 else 0
    arrow = "▲" if change >= 0 else "▼"
    print(f"  Change:    {arrow} ${abs(change):>14,.2f} ({change_pct:+.2f}%)")

    # Save updated portfolio if requested
    if args.save:
        snapshot_id = db.save_portfolio(portfolio)
        print(f"\nSaved as new snapshot: {snapshot_id}")
    else:
        print("\nUse --save to store updated prices as a new snapshot")

    # Show top movers
    if result['updated'] > 0:
        print("\nTop Daily Movers:")
        movers = sorted(portfolio.holdings, key=lambda h: abs(float(h.daily_change_percent)), reverse=True)
        for h in movers[:5]:
            arrow = "▲" if h.daily_change >= 0 else "▼"
            print(f"  {h.code:<6} {arrow} {float(h.daily_change_percent):>+6.2f}%  (${float(h.daily_change):>+8.2f})")


def cmd_quote(args):
    """Get a live quote for a single stock."""
    try:
        fetcher = ASXPriceFetcher()
        quote = fetcher.get_quote(args.code)
    except ImportError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error fetching quote: {e}")
        sys.exit(1)

    if not quote:
        print(f"Could not fetch quote for {args.code.upper()}")
        sys.exit(1)

    print("\n" + "=" * 50)
    print(f"{quote.code} - {quote.name}")
    print("=" * 50)

    arrow = "▲" if quote.change >= 0 else "▼"
    print(f"\nPrice:       ${float(quote.price):,.4f}")
    print(f"Change:      {arrow} ${float(quote.change):+.4f} ({float(quote.change_percent):+.2f}%)")
    print(f"Volume:      {quote.volume:,}")

    if quote.day_high and quote.day_low:
        print(f"Day Range:   ${float(quote.day_low):.2f} - ${float(quote.day_high):.2f}")
    if quote.year_high and quote.year_low:
        print(f"52wk Range:  ${float(quote.year_low):.2f} - ${float(quote.year_high):.2f}")
    if quote.market_cap:
        print(f"Market Cap:  ${float(quote.market_cap):,.0f}")

    print(f"\nLast Updated: {quote.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")


def cmd_sectors(args):
    """Show sector breakdown of portfolio."""
    db = PortfolioDatabase()
    db.initialize()

    portfolio = db.get_latest_portfolio()
    if not portfolio:
        print("No portfolio data found. Import a CSV first.")
        sys.exit(1)

    # Reclassify if requested
    if args.reclassify:
        result = classify_portfolio(portfolio)
        print(f"Reclassified {result['classified']}/{result['total']} holdings")
        if result['unknown_codes']:
            print(f"Unknown: {', '.join(result['unknown_codes'][:10])}")
        print()

    # Get sector summary
    sector_data = get_sector_summary(portfolio)

    print("\n" + "=" * 70)
    print("SECTOR BREAKDOWN")
    print("=" * 70)

    print(f"\n{'Sector':<25} {'Holdings':>8} {'Value':>15} {'Weight':>8} {'Return':>8}")
    print("-" * 70)

    for sector_name, data in sector_data.items():
        print(
            f"{sector_name:<25} "
            f"{data['count']:>8} "
            f"${data['market_value']:>14,.2f} "
            f"{data['weight']:>7.1f}% "
            f"{data['return_percent']:>+7.1f}%"
        )

    print("-" * 70)
    print(
        f"{'TOTAL':<25} "
        f"{portfolio.holding_count:>8} "
        f"${float(portfolio.total_market_value):>14,.2f} "
        f"{'100.0%':>8} "
        f"{float(portfolio.total_profit_loss_percent):>+7.1f}%"
    )

    # Show holdings by sector if verbose
    if args.holdings:
        print("\n" + "=" * 70)
        print("HOLDINGS BY SECTOR")
        print("=" * 70)
        for sector_name, data in sector_data.items():
            if data['holdings']:
                print(f"\n{sector_name}:")
                holdings = [portfolio.get_holding(code) for code in data['holdings']]
                holdings = sorted([h for h in holdings if h], key=lambda x: x.market_value, reverse=True)
                for h in holdings:
                    print(f"  {h.code:<6} ${float(h.market_value):>12,.2f} ({float(h.portfolio_weight):>5.1f}%)")

    # Save if requested
    if args.save:
        snapshot_id = db.save_portfolio(portfolio)
        print(f"\nSaved updated sectors to snapshot: {snapshot_id}")


def cmd_dividends(args):
    """Show dividend information for portfolio."""
    db = PortfolioDatabase()
    db.initialize()

    portfolio = db.get_latest_portfolio()
    if not portfolio:
        print("No portfolio data found. Import a CSV first.")
        sys.exit(1)

    print(f"\nFetching dividend data for {portfolio.holding_count} holdings...")

    try:
        fetcher = DividendFetcher()
        dividend_data = get_portfolio_dividends(portfolio, fetcher)
    except ImportError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error fetching dividends: {e}")
        sys.exit(1)

    print("\n" + "=" * 80)
    print("DIVIDEND ANALYSIS")
    print("=" * 80)

    print(f"\nData fetched for {dividend_data['fetched']}/{dividend_data['fetched'] + dividend_data['failed']} holdings")

    # Summary
    print(f"\n{'PORTFOLIO INCOME SUMMARY':^80}")
    print("-" * 80)
    print(f"  Portfolio Value:        ${float(portfolio.total_market_value):>15,.2f}")
    print(f"  Expected Annual Income: ${dividend_data['total_annual_income']:>15,.2f}")
    print(f"  Portfolio Yield:        {dividend_data['portfolio_yield']:>15.2f}%")
    print(f"  Monthly Average:        ${dividend_data['total_annual_income']/12:>15,.2f}")

    # Holdings table
    if args.holdings:
        print("\n" + "=" * 80)
        print("DIVIDEND YIELD BY HOLDING")
        print("=" * 80)
        print(f"\n{'Code':<6} {'Name':<25} {'Value':>12} {'Yield':>7} {'Annual':>12} {'Freq':<10}")
        print("-" * 80)

        # Sort by yield
        holdings = sorted(dividend_data['holdings'], key=lambda x: x['dividend_yield'], reverse=True)

        for h in holdings:
            name = h['name'][:24] if len(h['name']) > 24 else h['name']
            yield_str = f"{h['dividend_yield']:.2f}%" if h['dividend_yield'] > 0 else "-"
            annual_str = f"${h['expected_annual_income']:,.0f}" if h['expected_annual_income'] > 0 else "-"
            print(
                f"{h['code']:<6} "
                f"{name:<25} "
                f"${h['market_value']:>10,.0f} "
                f"{yield_str:>7} "
                f"{annual_str:>12} "
                f"{h['frequency']:<10}"
            )

    # Upcoming dividends
    upcoming = dividend_data.get('upcoming_dividends', [])
    if upcoming:
        print("\n" + "=" * 80)
        print("UPCOMING EX-DIVIDEND DATES")
        print("=" * 80)
        print(f"\n{'Code':<6} {'Ex-Date':<12} {'Days':>6} {'Est. Payment':>15}")
        print("-" * 45)

        for div in upcoming[:10]:  # Top 10 upcoming
            print(
                f"{div['code']:<6} "
                f"{div['ex_date']:<12} "
                f"{div['days_to_ex']:>6} "
                f"${div['estimated_payment']:>14,.2f}"
            )
    else:
        print("\n  No upcoming ex-dividend dates found.")

    # Income projection
    if args.projection:
        projection = calculate_income_projection(portfolio, dividend_data)
        print("\n" + "=" * 80)
        print("12-MONTH INCOME PROJECTION")
        print("=" * 80)
        print(f"\n{'Month':<20} {'Expected Income':>15}")
        print("-" * 40)

        for month in projection['projection']:
            income = float(month['expected_income'])
            bar = "█" * int(income / 500) if income > 0 else ""
            print(f"{month['label']:<20} ${income:>14,.2f}  {bar}")

        print("-" * 40)
        print(f"{'Annual Total':<20} ${projection['total_annual']:>14,.2f}")
        print(f"{'Monthly Average':<20} ${projection['average_monthly']:>14,.2f}")


def cmd_alerts(args):
    """Manage portfolio alerts."""
    manager = AlertManager(DATA_DIR)
    db = PortfolioDatabase()
    db.initialize()

    # Add new alert
    if args.add:
        alert_type_map = {
            "price-above": AlertType.PRICE_ABOVE,
            "price-below": AlertType.PRICE_BELOW,
            "profit-above": AlertType.PROFIT_ABOVE,
            "loss-below": AlertType.LOSS_BELOW,
            "value-above": AlertType.PORTFOLIO_VALUE_ABOVE,
            "value-below": AlertType.PORTFOLIO_VALUE_BELOW,
            "weight-above": AlertType.WEIGHT_ABOVE,
            "daily-up": AlertType.DAILY_CHANGE_ABOVE,
            "daily-down": AlertType.DAILY_CHANGE_BELOW,
        }

        if args.add not in alert_type_map:
            print(f"Unknown alert type: {args.add}")
            print(f"Valid types: {', '.join(alert_type_map.keys())}")
            sys.exit(1)

        if not args.threshold:
            print("Error: --threshold required when adding alerts")
            sys.exit(1)

        alert_type = alert_type_map[args.add]

        # Validate code requirement
        needs_code = alert_type not in (AlertType.PORTFOLIO_VALUE_ABOVE, AlertType.PORTFOLIO_VALUE_BELOW)
        if needs_code and not args.code:
            print(f"Error: --code required for {args.add} alerts")
            sys.exit(1)

        alert = manager.add_alert(
            alert_type=alert_type,
            threshold=Decimal(str(args.threshold)),
            code=args.code,
            description=args.note or "",
        )
        print(f"Created alert {alert.id}: {alert_type.value}")
        if alert.code:
            print(f"  Stock: {alert.code}")
        print(f"  Threshold: {args.threshold}")
        return

    # Remove alert
    if args.remove:
        if manager.remove_alert(args.remove):
            print(f"Removed alert {args.remove}")
        else:
            print(f"Alert {args.remove} not found")
        return

    # Reset alert
    if args.reset:
        if manager.reset_alert(args.reset):
            print(f"Reset alert {args.reset} to active")
        else:
            print(f"Alert {args.reset} not found")
        return

    # Dismiss alert
    if args.dismiss:
        if manager.dismiss_alert(args.dismiss):
            print(f"Dismissed alert {args.dismiss}")
        else:
            print(f"Alert {args.dismiss} not found")
        return

    # Check alerts against current portfolio
    if args.check:
        portfolio = db.get_latest_portfolio()
        if not portfolio:
            print("No portfolio data found. Import a CSV first.")
            sys.exit(1)

        triggered = manager.check_alerts(portfolio)
        if triggered:
            print(format_triggered_alerts(triggered))
        else:
            print("No alerts triggered.")
        return

    # List all alerts (default)
    print("\n" + "=" * 65)
    print("PORTFOLIO ALERTS")
    print("=" * 65)

    active = manager.get_active_alerts()
    triggered = manager.get_triggered_alerts()

    if active:
        print(f"\nActive Alerts ({len(active)}):")
        print(format_alert_list(active))

    if triggered:
        print(f"\nTriggered Alerts ({len(triggered)}):")
        print(format_alert_list(triggered))

    if not active and not triggered:
        print("\nNo alerts configured.")
        print("\nExample commands:")
        print("  alerts --add price-above --code CBA --threshold 150")
        print("  alerts --add value-below --threshold 2000000")
        print("  alerts --add loss-below --code VAS --threshold 10")
        print("  alerts --check")


def cmd_web(args):
    """Launch web dashboard."""
    if run_dashboard is None:
        print("Error: Flask is required for the web dashboard")
        print("Install with: pip install flask")
        sys.exit(1)

    try:
        run_dashboard(
            host=args.host,
            port=args.port,
            debug=args.debug,
        )
    except Exception as e:
        print(f"Error starting web server: {e}")
        sys.exit(1)


def cmd_tax(args):
    """Generate tax report."""
    db = PortfolioDatabase()
    db.initialize()

    portfolio = db.get_latest_portfolio()
    if not portfolio:
        print("No portfolio data found. Import a CSV first.")
        sys.exit(1)

    # Determine financial year
    fy = args.fy if args.fy else get_financial_year()

    print(f"\nGenerating tax report for FY {fy}...")

    # Generate report
    summary = generate_tax_report(portfolio, fy)

    if args.json:
        import json
        print(json.dumps(summary.to_dict(), indent=2))
    else:
        print(format_tax_report(summary, portfolio))

    # Show tax-loss harvesting suggestions if requested
    if args.harvest:
        print("\n" + "=" * 70)
        print("TAX-LOSS HARVESTING ANALYSIS")
        print("=" * 70)

        losses = [h for h in portfolio.holdings if h.profit_loss < 0]
        gains = [h for h in portfolio.holdings if h.profit_loss > 0]

        total_losses = sum(abs(h.profit_loss) for h in losses)
        total_gains = sum(h.profit_loss for h in gains)

        print(f"\n  Total Unrealised Gains:  ${float(total_gains):>12,.2f}")
        print(f"  Total Unrealised Losses: ${float(total_losses):>12,.2f}")

        if losses:
            print(f"\n  Selling all loss-making positions would:")
            print(f"  - Crystallise ${float(total_losses):,.2f} in capital losses")
            print(f"  - Offset gains, reducing taxable amount")

            # Estimate tax saving (assume 47% marginal rate)
            potential_saving = total_losses * Decimal("0.47")
            if total_gains > 0:
                discount = min(total_gains, total_losses) * Decimal("0.5") * Decimal("0.47")
                print(f"  - Potential tax saving: up to ${float(potential_saving):,.0f}")


def cmd_changes(args):
    """Show portfolio changes between snapshots."""
    db = PortfolioDatabase()
    db.initialize()

    # Show import history if requested
    if args.history:
        history = get_import_history(db, limit=args.limit or 10)
        if not history:
            print("No import history found.")
            return

        print("\n" + "=" * 70)
        print("IMPORT HISTORY")
        print("=" * 70)
        print(f"\n  {'ID':<12} {'Date':<12} {'Holdings':>8} {'Value':>15} {'P/L':>12}")
        print("  " + "-" * 63)
        for h in history:
            print(
                f"  {h['snapshot_id']:<12} "
                f"{h['date']:<12} "
                f"{h['holdings']:>8} "
                f"${h['value']:>14,.0f} "
                f"${h['profit']:>+11,.0f}"
            )
        return

    # FY comparison
    if args.fy:
        comparison = get_fy_comparison(db, args.fy)
        if not comparison:
            print(f"Insufficient data for FY {args.fy} comparison.")
            print("Need at least 2 snapshots within the financial year.")
            return

        if args.json:
            import json
            print(json.dumps(comparison.to_dict(), indent=2))
        else:
            print(generate_change_report(comparison))
        return

    # Compare two specific snapshots
    if args.old and args.new:
        old_portfolio = db.get_portfolio(args.old)
        new_portfolio = db.get_portfolio(args.new)

        if not old_portfolio:
            print(f"Snapshot '{args.old}' not found.")
            return
        if not new_portfolio:
            print(f"Snapshot '{args.new}' not found.")
            return

        comparison = compare_portfolios(old_portfolio, new_portfolio)

        if args.json:
            import json
            print(json.dumps(comparison.to_dict(), indent=2))
        else:
            print(generate_change_report(comparison))
        return

    # Default: compare latest two snapshots
    snapshots = db.get_all_snapshots()
    if len(snapshots) < 2:
        print("Need at least 2 snapshots to compare changes.")
        print("Import another CSV file to track changes over time.")
        return

    latest = snapshots[0]
    previous = snapshots[1]

    old_portfolio = db.get_portfolio(previous.snapshot_id)
    new_portfolio = db.get_portfolio(latest.snapshot_id)

    if old_portfolio and new_portfolio:
        comparison = compare_portfolios(old_portfolio, new_portfolio)
        if args.json:
            import json
            print(json.dumps(comparison.to_dict(), indent=2))
        else:
            print(generate_change_report(comparison))
    else:
        print("Error loading snapshots for comparison.")


def main():
    """Main entry point."""
    ensure_directories()

    parser = argparse.ArgumentParser(
        description="Portfolio Tracker - Manage and analyze CommSec portfolio exports",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  portfolio_tracker import portfolio.csv     Import a CommSec CSV export
  portfolio_tracker view                     View current portfolio
  portfolio_tracker view --dashboard         Full dashboard view
  portfolio_tracker analyze --report         Detailed analysis report
  portfolio_tracker query --min-return 10    Find holdings with >10% return
  portfolio_tracker holding CBA              Details for specific holding
  portfolio_tracker update                   Fetch live ASX prices
  portfolio_tracker quote BHP                Get live quote for a stock
  portfolio_tracker history                  Show portfolio history
        """
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Import command
    import_parser = subparsers.add_parser("import", help="Import CommSec CSV file")
    import_parser.add_argument("csv_file", help="Path to CommSec CSV export")

    # View command
    view_parser = subparsers.add_parser("view", help="View portfolio")
    view_parser.add_argument("--snapshot", "-s", help="Specific snapshot ID")
    view_parser.add_argument("--dashboard", "-d", action="store_true", help="Show full dashboard")
    view_parser.add_argument("--limit", "-l", type=int, default=20, help="Max holdings to show")

    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze portfolio")
    analyze_parser.add_argument("--snapshot", "-s", help="Specific snapshot ID")
    analyze_parser.add_argument("--report", "-r", action="store_true", help="Full text report")

    # Query command
    query_parser = subparsers.add_parser("query", help="Query holdings with filters")
    query_parser.add_argument("--min-value", type=float, help="Minimum market value")
    query_parser.add_argument("--max-value", type=float, help="Maximum market value")
    query_parser.add_argument("--min-return", type=float, help="Minimum return %")
    query_parser.add_argument("--max-return", type=float, help="Maximum return %")
    query_parser.add_argument("--profitable", action="store_true", dest="profitable", default=None, help="Only profitable")
    query_parser.add_argument("--losing", action="store_false", dest="profitable", help="Only losing")
    query_parser.add_argument("--asset-class", help="Filter by asset class")
    query_parser.add_argument("--min-weight", type=float, help="Minimum portfolio weight %")

    # History command
    history_parser = subparsers.add_parser("history", help="Show portfolio history")
    history_parser.add_argument("--chart", "-c", action="store_true", help="Generate chart (requires matplotlib)")

    # Compare command
    compare_parser = subparsers.add_parser("compare", help="Compare two snapshots")
    compare_parser.add_argument("--old", required=True, help="Older snapshot ID")
    compare_parser.add_argument("--new", required=True, help="Newer snapshot ID")

    # Export command
    export_parser = subparsers.add_parser("export", help="Export portfolio")
    export_parser.add_argument("--snapshot", "-s", help="Specific snapshot ID")
    export_parser.add_argument("--format", choices=["csv", "json", "report"], default="csv")
    export_parser.add_argument("--output", "-o", help="Output directory")

    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Database statistics")
    stats_parser.add_argument("--holdings", action="store_true", help="List all holdings")

    # Holding command (single holding details)
    holding_parser = subparsers.add_parser("holding", help="View specific holding")
    holding_parser.add_argument("code", help="Stock/ETF ticker code (e.g., CBA, VAS)")

    # Update command (live prices)
    update_parser = subparsers.add_parser("update", help="Update portfolio with live ASX prices")
    update_parser.add_argument("--save", "-s", action="store_true", help="Save as new snapshot")

    # Quote command (single stock quote)
    quote_parser = subparsers.add_parser("quote", help="Get live quote for a stock")
    quote_parser.add_argument("code", help="ASX ticker code (e.g., CBA, BHP)")

    # Sectors command
    sectors_parser = subparsers.add_parser("sectors", help="Show sector breakdown")
    sectors_parser.add_argument("--list", "-l", dest="holdings", action="store_true", help="List holdings per sector")
    sectors_parser.add_argument("--reclassify", "-r", action="store_true", help="Reclassify all holdings")
    sectors_parser.add_argument("--save", "-s", action="store_true", help="Save updated sectors")

    # Dividends command
    dividends_parser = subparsers.add_parser("dividends", help="Show dividend analysis")
    dividends_parser.add_argument("--list", "-l", dest="holdings", action="store_true", help="List holdings with yields")
    dividends_parser.add_argument("--projection", "-p", action="store_true", help="Show 12-month income projection")

    # Alerts command
    alerts_parser = subparsers.add_parser("alerts", help="Manage portfolio alerts")
    alerts_parser.add_argument("--add", "-a", metavar="TYPE", help="Add alert (price-above, price-below, profit-above, loss-below, value-above, value-below, weight-above, daily-up, daily-down)")
    alerts_parser.add_argument("--code", "-c", help="Stock code for the alert")
    alerts_parser.add_argument("--threshold", "-t", type=float, help="Threshold value")
    alerts_parser.add_argument("--note", "-n", help="Optional note/description")
    alerts_parser.add_argument("--remove", metavar="ID", help="Remove alert by ID")
    alerts_parser.add_argument("--reset", metavar="ID", help="Reset triggered alert to active")
    alerts_parser.add_argument("--dismiss", metavar="ID", help="Dismiss a triggered alert")
    alerts_parser.add_argument("--check", action="store_true", help="Check alerts against current portfolio")

    # Web dashboard command
    web_parser = subparsers.add_parser("web", help="Launch web dashboard")
    web_parser.add_argument("--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)")
    web_parser.add_argument("--port", "-p", type=int, default=5000, help="Port to run on (default: 5000)")
    web_parser.add_argument("--debug", "-d", action="store_true", help="Enable debug mode")

    # Tax reporting command
    tax_parser = subparsers.add_parser("tax", help="Tax report and CGT analysis")
    tax_parser.add_argument("--fy", help="Financial year (e.g., 2024-25). Defaults to current FY")
    tax_parser.add_argument("--harvest", action="store_true", help="Show tax-loss harvesting opportunities")
    tax_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Changes command
    changes_parser = subparsers.add_parser("changes", help="Track portfolio changes between imports")
    changes_parser.add_argument("--history", action="store_true", help="Show import history")
    changes_parser.add_argument("--limit", type=int, help="Limit history entries (default: 10)")
    changes_parser.add_argument("--fy", help="Compare for financial year (e.g., 2024-25)")
    changes_parser.add_argument("--old", help="Old snapshot ID for comparison")
    changes_parser.add_argument("--new", help="New snapshot ID for comparison")
    changes_parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()
    setup_logging(args.verbose)

    if args.command == "import":
        cmd_import(args)
    elif args.command == "view":
        cmd_view(args)
    elif args.command == "analyze":
        cmd_analyze(args)
    elif args.command == "query":
        cmd_query(args)
    elif args.command == "history":
        cmd_history(args)
    elif args.command == "compare":
        cmd_compare(args)
    elif args.command == "export":
        cmd_export(args)
    elif args.command == "stats":
        cmd_stats(args)
    elif args.command == "holding":
        cmd_holding(args)
    elif args.command == "update":
        cmd_update(args)
    elif args.command == "quote":
        cmd_quote(args)
    elif args.command == "sectors":
        cmd_sectors(args)
    elif args.command == "dividends":
        cmd_dividends(args)
    elif args.command == "alerts":
        cmd_alerts(args)
    elif args.command == "web":
        cmd_web(args)
    elif args.command == "tax":
        cmd_tax(args)
    elif args.command == "changes":
        cmd_changes(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
