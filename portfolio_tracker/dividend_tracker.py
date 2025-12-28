"""
Dividend Tracker - Track and analyze dividend payments for ASX stocks.

Fetches dividend data from Yahoo Finance and calculates yields.
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any

from .models import Holding, Portfolio

logger = logging.getLogger(__name__)


@dataclass
class Dividend:
    """Represents a single dividend payment."""
    code: str
    ex_date: date
    pay_date: Optional[date]
    amount: Decimal
    franking_percent: Decimal = Decimal("0")  # 0-100%
    type: str = "Interim"  # Interim, Final, Special

    @property
    def franking_credit(self) -> Decimal:
        """Calculate franking credit (Australian imputation)."""
        if self.franking_percent == 0:
            return Decimal("0")
        # Franking credit = Dividend * (Franking % / 100) * (Company Tax Rate / (1 - Company Tax Rate))
        # Company tax rate is 30% for large companies
        tax_rate = Decimal("0.30")
        return self.amount * (self.franking_percent / Decimal("100")) * (tax_rate / (Decimal("1") - tax_rate))

    @property
    def grossed_up_amount(self) -> Decimal:
        """Dividend amount plus franking credit."""
        return self.amount + self.franking_credit


@dataclass
class DividendInfo:
    """Dividend information for a stock."""
    code: str
    name: str
    annual_dividend: Decimal = Decimal("0")
    dividend_yield: Decimal = Decimal("0")  # As percentage
    ex_dividend_date: Optional[date] = None
    pay_date: Optional[date] = None
    frequency: str = "Unknown"  # Annual, Semi-Annual, Quarterly
    franking_percent: Decimal = Decimal("0")
    history: List[Dividend] = field(default_factory=list)
    last_updated: datetime = field(default_factory=datetime.now)

    @property
    def is_upcoming(self) -> bool:
        """Check if there's an upcoming ex-dividend date."""
        if not self.ex_dividend_date:
            return False
        return self.ex_dividend_date > date.today()

    @property
    def days_to_ex(self) -> Optional[int]:
        """Days until ex-dividend date."""
        if not self.ex_dividend_date:
            return None
        delta = self.ex_dividend_date - date.today()
        return delta.days


class DividendFetcher:
    """Fetches dividend data from Yahoo Finance."""

    def __init__(self):
        self._cache: Dict[str, DividendInfo] = {}

    def get_dividend_info(self, code: str) -> Optional[DividendInfo]:
        """
        Get dividend information for an ASX stock.

        Args:
            code: ASX ticker code

        Returns:
            DividendInfo or None if fetch failed
        """
        try:
            import requests
        except ImportError:
            raise ImportError("requests library required: pip install requests")

        code_upper = code.upper().strip()

        # Check cache (valid for 1 hour)
        if code_upper in self._cache:
            cached = self._cache[code_upper]
            if (datetime.now() - cached.last_updated).seconds < 3600:
                return cached

        try:
            # Yahoo Finance summary endpoint
            symbol = f"{code_upper}.AX"
            url = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{symbol}"
            params = {"modules": "summaryDetail,price,calendarEvents"}
            headers = {"User-Agent": "Mozilla/5.0"}

            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()

            data = response.json()
            result = data.get("quoteSummary", {}).get("result", [{}])[0]

            summary = result.get("summaryDetail", {})
            price_info = result.get("price", {})
            calendar = result.get("calendarEvents", {})

            # Extract dividend data
            dividend_rate = self._get_value(summary, "dividendRate")
            dividend_yield = self._get_value(summary, "dividendYield")
            ex_date = self._parse_date(summary.get("exDividendDate", {}))

            # Get name
            name = price_info.get("shortName", code_upper)

            # Try to get upcoming ex-div from calendar
            upcoming_ex = None
            if calendar and "exDividendDate" in calendar:
                upcoming_ex = self._parse_date(calendar["exDividendDate"])

            # Use upcoming if available, otherwise use last
            final_ex_date = upcoming_ex or ex_date

            # Determine frequency based on yield/rate
            frequency = "Unknown"
            if dividend_rate and dividend_rate > 0:
                # Most ASX stocks pay semi-annually
                frequency = "Semi-Annual"

            info = DividendInfo(
                code=code_upper,
                name=name,
                annual_dividend=Decimal(str(dividend_rate)) if dividend_rate else Decimal("0"),
                dividend_yield=Decimal(str(dividend_yield * 100)) if dividend_yield else Decimal("0"),
                ex_dividend_date=final_ex_date,
                frequency=frequency,
                last_updated=datetime.now(),
            )

            # Fetch dividend history
            info.history = self._get_dividend_history(code_upper)

            self._cache[code_upper] = info
            return info

        except Exception as e:
            logger.warning(f"Failed to fetch dividend info for {code}: {e}")
            return None

    def _get_value(self, data: dict, key: str) -> Optional[float]:
        """Extract a numeric value from Yahoo Finance response."""
        if key not in data:
            return None
        val = data[key]
        if isinstance(val, dict):
            return val.get("raw")
        return val

    def _parse_date(self, data: dict) -> Optional[date]:
        """Parse a date from Yahoo Finance timestamp."""
        if not data:
            return None
        timestamp = data.get("raw")
        if timestamp:
            return datetime.fromtimestamp(timestamp).date()
        return None

    def _get_dividend_history(self, code: str) -> List[Dividend]:
        """Fetch dividend payment history."""
        try:
            import requests
        except ImportError:
            return []

        try:
            symbol = f"{code}.AX"
            # Get last 2 years of dividends
            end_date = int(datetime.now().timestamp())
            start_date = int((datetime.now() - timedelta(days=730)).timestamp())

            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            params = {
                "period1": start_date,
                "period2": end_date,
                "events": "div",
                "interval": "1d",
            }
            headers = {"User-Agent": "Mozilla/5.0"}

            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()

            data = response.json()
            events = data.get("chart", {}).get("result", [{}])[0].get("events", {})
            dividends_data = events.get("dividends", {})

            dividends = []
            for timestamp, div_info in dividends_data.items():
                try:
                    ex_date = datetime.fromtimestamp(int(timestamp)).date()
                    amount = Decimal(str(div_info.get("amount", 0)))
                    dividends.append(Dividend(
                        code=code,
                        ex_date=ex_date,
                        pay_date=None,  # Not available from this endpoint
                        amount=amount,
                    ))
                except (ValueError, TypeError):
                    continue

            return sorted(dividends, key=lambda d: d.ex_date, reverse=True)

        except Exception as e:
            logger.debug(f"Failed to fetch dividend history for {code}: {e}")
            return []


def get_portfolio_dividends(portfolio: Portfolio, fetcher: Optional[DividendFetcher] = None) -> Dict[str, Any]:
    """
    Get dividend information for all holdings in a portfolio.

    Args:
        portfolio: Portfolio to analyze
        fetcher: Optional DividendFetcher instance

    Returns:
        Dictionary with dividend analysis
    """
    if fetcher is None:
        fetcher = DividendFetcher()

    results = {
        "holdings": [],
        "total_annual_income": Decimal("0"),
        "portfolio_yield": Decimal("0"),
        "upcoming_dividends": [],
        "fetched": 0,
        "failed": 0,
    }

    for holding in portfolio.holdings:
        info = fetcher.get_dividend_info(holding.code)

        if info:
            results["fetched"] += 1

            # Calculate expected annual income from this holding
            expected_income = info.annual_dividend * holding.quantity

            holding_data = {
                "code": holding.code,
                "name": holding.name,
                "quantity": holding.quantity,
                "market_value": float(holding.market_value),
                "annual_dividend": float(info.annual_dividend),
                "dividend_yield": float(info.dividend_yield),
                "expected_annual_income": float(expected_income),
                "ex_dividend_date": info.ex_dividend_date.isoformat() if info.ex_dividend_date else None,
                "frequency": info.frequency,
            }
            results["holdings"].append(holding_data)
            results["total_annual_income"] += expected_income

            # Track upcoming dividends
            if info.is_upcoming and info.ex_dividend_date:
                results["upcoming_dividends"].append({
                    "code": holding.code,
                    "ex_date": info.ex_dividend_date.isoformat(),
                    "days_to_ex": info.days_to_ex,
                    "estimated_payment": float(info.annual_dividend / 2 * holding.quantity),  # Assume semi-annual
                })
        else:
            results["failed"] += 1
            results["holdings"].append({
                "code": holding.code,
                "name": holding.name,
                "quantity": holding.quantity,
                "market_value": float(holding.market_value),
                "annual_dividend": 0,
                "dividend_yield": 0,
                "expected_annual_income": 0,
                "ex_dividend_date": None,
                "frequency": "Unknown",
            })

    # Calculate portfolio yield
    if portfolio.total_market_value > 0:
        results["portfolio_yield"] = (
            results["total_annual_income"] / portfolio.total_market_value * Decimal("100")
        )

    # Sort upcoming by date
    results["upcoming_dividends"] = sorted(
        results["upcoming_dividends"],
        key=lambda x: x["ex_date"]
    )

    results["total_annual_income"] = float(results["total_annual_income"])
    results["portfolio_yield"] = float(results["portfolio_yield"])

    return results


def calculate_income_projection(portfolio: Portfolio, dividend_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Project dividend income for the next 12 months.

    Args:
        portfolio: Portfolio to analyze
        dividend_data: Output from get_portfolio_dividends

    Returns:
        Monthly income projection
    """
    from calendar import month_name

    today = date.today()
    projection = {}

    # Initialize months
    for i in range(12):
        month_date = today + timedelta(days=30 * i)
        month_key = f"{month_date.year}-{month_date.month:02d}"
        month_label = f"{month_name[month_date.month]} {month_date.year}"
        projection[month_key] = {
            "label": month_label,
            "expected_income": Decimal("0"),
            "dividends": [],
        }

    # Distribute expected income across months
    # Most ASX stocks pay semi-annually (Feb/Aug or Mar/Sep or Apr/Oct)
    total_annual = Decimal(str(dividend_data["total_annual_income"]))
    semi_annual = total_annual / 2

    # Typical ASX dividend months
    div_months = [2, 8]  # Feb and Aug for many big stocks

    for month_num in div_months:
        for i in range(12):
            month_date = today + timedelta(days=30 * i)
            if month_date.month == month_num:
                month_key = f"{month_date.year}-{month_date.month:02d}"
                if month_key in projection:
                    projection[month_key]["expected_income"] = semi_annual
                break

    return {
        "projection": list(projection.values()),
        "total_annual": float(total_annual),
        "average_monthly": float(total_annual / 12),
    }


# Known high-yield ASX stocks (for quick reference)
HIGH_YIELD_STOCKS = {
    # Big 4 Banks (typically 4-6% yield)
    "CBA", "WBC", "NAB", "ANZ",
    # Telcos
    "TLS",
    # REITs (typically higher yields)
    "DXS", "GPT", "SCG", "VCX", "BWP",
    # High yield ETFs
    "VHY", "HVST", "SYI",
    # LICs
    "AFI", "ARG", "MLT", "WHF",
    # Miners (variable)
    "BHP", "RIO", "FMG",
}
