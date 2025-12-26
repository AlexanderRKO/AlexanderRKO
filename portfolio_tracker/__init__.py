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
]
