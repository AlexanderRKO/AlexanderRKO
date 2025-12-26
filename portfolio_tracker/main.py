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
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
