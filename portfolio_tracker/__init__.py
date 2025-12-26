"""
Portfolio Tracker - CommSec CSV Import and Analysis

A portfolio tracking tool for Australian investors using CommSec.
"""

from .models import Holding, Portfolio, PortfolioSnapshot, Sector
from .parser import CommSecCSVParser
from .storage import PortfolioDatabase
from .analysis import PortfolioAnalyzer
from .visualizer import PortfolioVisualizer
from .price_fetcher import ASXPriceFetcher, PriceQuote, update_portfolio_prices
from .sector_lookup import (
    get_sector,
    classify_holding,
    classify_portfolio,
    get_sector_summary,
)
from .dividend_tracker import (
    Dividend,
    DividendInfo,
    DividendFetcher,
    get_portfolio_dividends,
    calculate_income_projection,
)
from .alerts import (
    Alert,
    AlertType,
    AlertStatus,
    AlertManager,
    TriggeredAlert,
)

# Optional web dashboard (requires Flask)
try:
    from .web_dashboard import create_app, run_dashboard
except ImportError:
    create_app = None
    run_dashboard = None

from .tax_reporting import (
    TaxSummary,
    CapitalGain,
    DividendIncome,
    generate_tax_report,
    analyze_unrealised_gains,
    format_tax_report,
    get_financial_year,
)
from .change_tracker import (
    HoldingChange,
    PortfolioComparison,
    compare_portfolios,
    get_fy_comparison,
    generate_change_report,
    get_import_history,
)
from .fy_analysis import (
    FYDates,
    FYAnalysis,
    get_fy_dates,
    analyze_financial_year,
    format_fy_report,
    compare_financial_years,
)
from .formatting import (
    green, red, yellow, blue, cyan, bold, dim,
    format_money, format_percent, format_change, progress_bar,
)
from .status_dashboard import (
    generate_status_dashboard,
    generate_welcome_message,
    COMMAND_ALIASES,
)
from .charts import (
    ascii_bar_chart,
    ascii_pie_chart,
    ascii_sparkline,
    ascii_table,
    sector_tree,
    check_matplotlib,
    create_pie_chart,
    create_bar_chart,
    create_line_chart,
    get_sector_chart_data,
    get_performance_chart_data,
    get_holdings_chart_data,
)
from .news_feed import (
    NewsItem,
    fetch_stock_news,
    fetch_portfolio_news,
    format_news_feed,
    format_stock_news,
    get_news_summary,
)

__all__ = [
    "Holding",
    "Portfolio",
    "PortfolioSnapshot",
    "Sector",
    "CommSecCSVParser",
    "PortfolioDatabase",
    "PortfolioAnalyzer",
    "PortfolioVisualizer",
    "ASXPriceFetcher",
    "PriceQuote",
    "update_portfolio_prices",
    "get_sector",
    "classify_holding",
    "classify_portfolio",
    "get_sector_summary",
    "Dividend",
    "DividendInfo",
    "DividendFetcher",
    "get_portfolio_dividends",
    "calculate_income_projection",
    "Alert",
    "AlertType",
    "AlertStatus",
    "AlertManager",
    "TriggeredAlert",
    "create_app",
    "run_dashboard",
    "TaxSummary",
    "CapitalGain",
    "DividendIncome",
    "generate_tax_report",
    "analyze_unrealised_gains",
    "format_tax_report",
    "get_financial_year",
    "HoldingChange",
    "PortfolioComparison",
    "compare_portfolios",
    "get_fy_comparison",
    "generate_change_report",
    "get_import_history",
    "FYDates",
    "FYAnalysis",
    "get_fy_dates",
    "analyze_financial_year",
    "format_fy_report",
    "compare_financial_years",
    "green",
    "red",
    "yellow",
    "blue",
    "cyan",
    "bold",
    "dim",
    "format_money",
    "format_percent",
    "format_change",
    "progress_bar",
    "generate_status_dashboard",
    "generate_welcome_message",
    "COMMAND_ALIASES",
    "ascii_bar_chart",
    "ascii_pie_chart",
    "ascii_sparkline",
    "ascii_table",
    "sector_tree",
    "check_matplotlib",
    "create_pie_chart",
    "create_bar_chart",
    "create_line_chart",
    "get_sector_chart_data",
    "get_performance_chart_data",
    "get_holdings_chart_data",
    "NewsItem",
    "fetch_stock_news",
    "fetch_portfolio_news",
    "format_news_feed",
    "format_stock_news",
    "get_news_summary",
]
