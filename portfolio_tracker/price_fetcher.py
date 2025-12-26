"""
ASX Price Fetcher - Fetch live prices for ASX-listed securities.

Uses Yahoo Finance API for real-time ASX price data.
ASX tickers use the format "CODE.AX" (e.g., "CBA.AX", "VAS.AX").
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime, date
from decimal import Decimal
from typing import Dict, List, Optional, Any
import json

try:
    import requests
except ImportError:
    requests = None  # type: ignore

logger = logging.getLogger(__name__)

# Yahoo Finance API endpoint
YAHOO_QUOTE_URL = "https://query1.finance.yahoo.com/v7/finance/quote"

# Rate limiting
REQUEST_DELAY = 0.5  # seconds between requests
MAX_SYMBOLS_PER_REQUEST = 20  # Yahoo allows batching


@dataclass
class PriceQuote:
    """Real-time price quote for a security."""
    code: str  # ASX code (without .AX suffix)
    price: Decimal
    change: Decimal
    change_percent: Decimal
    volume: int
    market_cap: Optional[Decimal]
    day_high: Optional[Decimal]
    day_low: Optional[Decimal]
    year_high: Optional[Decimal]
    year_low: Optional[Decimal]
    name: str
    timestamp: datetime

    @property
    def is_valid(self) -> bool:
        """Check if quote has valid price data."""
        return self.price > 0


class ASXPriceFetcher:
    """
    Fetches live prices from Yahoo Finance for ASX securities.

    Usage:
        fetcher = ASXPriceFetcher()
        quotes = fetcher.get_quotes(["CBA", "BHP", "VAS"])
        for code, quote in quotes.items():
            print(f"{code}: ${quote.price}")
    """

    def __init__(self):
        if requests is None:
            raise ImportError("requests library required. Install with: pip install requests")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        self._last_request_time = 0.0

    def _rate_limit(self):
        """Ensure we don't hit rate limits."""
        elapsed = time.time() - self._last_request_time
        if elapsed < REQUEST_DELAY:
            time.sleep(REQUEST_DELAY - elapsed)
        self._last_request_time = time.time()

    def _to_yahoo_symbol(self, asx_code: str) -> str:
        """Convert ASX code to Yahoo Finance symbol."""
        code = asx_code.upper().strip()
        if not code.endswith(".AX"):
            code = f"{code}.AX"
        return code

    def _from_yahoo_symbol(self, yahoo_symbol: str) -> str:
        """Convert Yahoo Finance symbol back to ASX code."""
        return yahoo_symbol.replace(".AX", "").upper()

    def get_quote(self, asx_code: str) -> Optional[PriceQuote]:
        """
        Get a single price quote.

        Args:
            asx_code: ASX ticker code (e.g., "CBA", "VAS")

        Returns:
            PriceQuote object or None if fetch failed
        """
        quotes = self.get_quotes([asx_code])
        return quotes.get(asx_code.upper())

    def get_quotes(self, asx_codes: List[str]) -> Dict[str, PriceQuote]:
        """
        Get price quotes for multiple securities.

        Args:
            asx_codes: List of ASX ticker codes

        Returns:
            Dictionary mapping ASX codes to PriceQuote objects
        """
        if not asx_codes:
            return {}

        results: Dict[str, PriceQuote] = {}

        # Process in batches
        for i in range(0, len(asx_codes), MAX_SYMBOLS_PER_REQUEST):
            batch = asx_codes[i:i + MAX_SYMBOLS_PER_REQUEST]
            batch_results = self._fetch_batch(batch)
            results.update(batch_results)

            # Rate limit between batches
            if i + MAX_SYMBOLS_PER_REQUEST < len(asx_codes):
                self._rate_limit()

        return results

    def _fetch_batch(self, asx_codes: List[str]) -> Dict[str, PriceQuote]:
        """Fetch a batch of quotes from Yahoo Finance."""
        yahoo_symbols = [self._to_yahoo_symbol(code) for code in asx_codes]
        symbols_str = ",".join(yahoo_symbols)

        params = {
            "symbols": symbols_str,
            "fields": "regularMarketPrice,regularMarketChange,regularMarketChangePercent,"
                     "regularMarketVolume,marketCap,regularMarketDayHigh,regularMarketDayLow,"
                     "fiftyTwoWeekHigh,fiftyTwoWeekLow,shortName,longName"
        }

        try:
            self._rate_limit()
            response = self.session.get(YAHOO_QUOTE_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to fetch quotes: {e}")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse response: {e}")
            return {}

        results: Dict[str, PriceQuote] = {}

        quote_response = data.get("quoteResponse", {})
        quotes = quote_response.get("result", [])

        for quote_data in quotes:
            try:
                yahoo_symbol = quote_data.get("symbol", "")
                asx_code = self._from_yahoo_symbol(yahoo_symbol)

                price = quote_data.get("regularMarketPrice", 0)
                if price is None or price == 0:
                    logger.warning(f"No price data for {asx_code}")
                    continue

                quote = PriceQuote(
                    code=asx_code,
                    price=Decimal(str(price)),
                    change=Decimal(str(quote_data.get("regularMarketChange", 0) or 0)),
                    change_percent=Decimal(str(quote_data.get("regularMarketChangePercent", 0) or 0)),
                    volume=int(quote_data.get("regularMarketVolume", 0) or 0),
                    market_cap=Decimal(str(quote_data.get("marketCap", 0) or 0)) if quote_data.get("marketCap") else None,
                    day_high=Decimal(str(quote_data.get("regularMarketDayHigh", 0) or 0)) if quote_data.get("regularMarketDayHigh") else None,
                    day_low=Decimal(str(quote_data.get("regularMarketDayLow", 0) or 0)) if quote_data.get("regularMarketDayLow") else None,
                    year_high=Decimal(str(quote_data.get("fiftyTwoWeekHigh", 0) or 0)) if quote_data.get("fiftyTwoWeekHigh") else None,
                    year_low=Decimal(str(quote_data.get("fiftyTwoWeekLow", 0) or 0)) if quote_data.get("fiftyTwoWeekLow") else None,
                    name=quote_data.get("longName") or quote_data.get("shortName") or asx_code,
                    timestamp=datetime.now(),
                )

                results[asx_code] = quote

            except (KeyError, TypeError, ValueError) as e:
                logger.warning(f"Failed to parse quote data: {e}")
                continue

        # Log any missing symbols
        fetched_codes = set(results.keys())
        requested_codes = set(code.upper() for code in asx_codes)
        missing = requested_codes - fetched_codes
        if missing:
            logger.warning(f"No data returned for: {', '.join(missing)}")

        return results


def update_portfolio_prices(portfolio, fetcher: Optional[ASXPriceFetcher] = None) -> Dict[str, Any]:
    """
    Update all holdings in a portfolio with live prices.

    Args:
        portfolio: Portfolio object to update
        fetcher: Optional ASXPriceFetcher instance

    Returns:
        Dictionary with update statistics
    """
    if fetcher is None:
        fetcher = ASXPriceFetcher()

    # Get all unique codes
    codes = [h.code for h in portfolio.holdings]

    # Fetch quotes
    quotes = fetcher.get_quotes(codes)

    updated = 0
    failed = 0
    total_old_value = portfolio.total_market_value

    for holding in portfolio.holdings:
        quote = quotes.get(holding.code)
        if quote and quote.is_valid:
            # Update holding with new price
            holding.current_price = quote.price
            holding.daily_change = quote.change
            holding.daily_change_percent = quote.change_percent

            # Update company name if we only had the code
            if holding.name == holding.code and quote.name:
                holding.name = quote.name

            # Recalculate derived values
            holding.market_value = Decimal(str(holding.quantity)) * holding.current_price
            holding.profit_loss = holding.market_value - holding.cost_base
            if holding.cost_base > 0:
                holding.profit_loss_percent = (holding.profit_loss / holding.cost_base) * Decimal("100")
            holding.value_change = Decimal(str(holding.quantity)) * holding.daily_change
            holding.last_updated = datetime.now()

            updated += 1
        else:
            failed += 1
            logger.warning(f"Could not update price for {holding.code}")

    # Recalculate portfolio totals
    portfolio.recalculate()

    total_new_value = portfolio.total_market_value
    value_change = total_new_value - total_old_value

    return {
        "updated": updated,
        "failed": failed,
        "total": len(codes),
        "old_value": float(total_old_value),
        "new_value": float(total_new_value),
        "value_change": float(value_change),
        "timestamp": datetime.now().isoformat(),
    }
