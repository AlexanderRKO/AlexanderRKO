"""
CommSec CSV Parser - Parse portfolio exports from CommSec.

CommSec CSV format (as of Dec 2025):
- Code: ASX ticker symbol
- Avail Units: Number of shares held
- Purchase: Average purchase price per share
- Last $: Current market price
- Change $: Daily price change
- Chg %: Daily change percentage
- Profit/Loss: Dollar profit/loss
- P/L %: Percentage profit/loss
- Mkt Value: Current market value
- Wgt %: Portfolio weight percentage
- Value Chg: Daily value change
"""

import csv
import re
import logging
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

from .models import Holding, Portfolio, AssetClass, Sector

logger = logging.getLogger(__name__)


# Known ETFs on ASX for classification
KNOWN_ETFS = {
    # Vanguard
    "VAS", "VGS", "VTS", "VEU", "VAP", "VAE", "VGB", "VGE", "VSO",
    "VDHG", "VDGR", "VDBA", "VDCO", "VHY",
    # BetaShares
    "A200", "QUAL", "ETHI", "FAIR", "NDQ", "ASIA", "TECH", "HACK",
    "DHHF", "DGGF", "GEAR", "GGUS", "BBOZ", "BBUS", "ACDC", "CRYP",
    "QFN", "QAU", "QRE", "QOZ", "HVST",
    # iShares
    "IOZ", "IVV", "IJH", "IJR", "IVE", "IEM", "IEU", "IAF", "IHVV",
    # SPDR
    "STW", "SYI", "SLF", "MVW", "MVB", "MVE", "MVS", "SFY",
    # VanEck
    "MOAT", "UMAX", "YMAX", "QMAX",
}

# Known REITs
KNOWN_REITS = {
    "DXS", "GPT", "MGR", "SCG", "SGP", "VCX", "CHC", "BWP", "GMG",
    "CLW", "CIP", "CQR", "HMC", "NSR", "SCP", "WPR", "ARF", "CNI",
}

# Known LICs
KNOWN_LICS = {
    "AFI", "ARG", "AUI", "BKI", "DJW", "DUI", "FGG", "FGX", "IGB",
    "MFF", "MIR", "MLT", "PIC", "SOL", "WAM", "WAX", "WGB", "WLE",
    "WMI", "WHF", "CAM", "VG1", "PL8", "PGF", "WAR", "OPH", "ALI",
}


class CommSecCSVParser:
    """
    Parser for CommSec portfolio CSV exports.

    Handles various CSV formats and column name variations that CommSec
    may use in their exports.
    """

    # Column name mappings (CommSec format as of Dec 2025)
    COLUMN_MAPPINGS = {
        "code": ["code", "ticker", "symbol", "asx code", "stock code"],
        "name": ["company", "name", "security", "stock name", "description"],
        "quantity": ["avail units", "quantity", "qty", "units", "shares", "holding"],
        "avg_cost": ["purchase", "avg cost", "average cost", "avg price", "average price", "cost price", "purchase price"],
        "current_price": ["last $", "current price", "price", "last price", "market price", "close price", "last"],
        "market_value": ["mkt value", "market value", "value", "current value", "total value"],
        "profit_loss": ["profit/loss", "profit/loss $", "gain/loss $", "gain/loss", "p/l $", "p&l $", "unrealised gain/loss"],
        "profit_loss_percent": ["p/l %", "profit/loss %", "gain/loss %", "p&l %", "return %", "% return"],
        "cost_base": ["cost base", "total cost", "cost", "purchase value"],
        "daily_change": ["change $", "change", "day change"],
        "daily_change_percent": ["chg %", "change %", "day change %"],
        "portfolio_weight": ["wgt %", "weight %", "weight", "portfolio weight"],
        "value_change": ["value chg", "value change"],
    }

    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def parse_file(self, file_path: str | Path) -> Portfolio:
        """
        Parse a CommSec CSV file and return a Portfolio.

        Args:
            file_path: Path to the CSV file

        Returns:
            Portfolio object with all holdings
        """
        file_path = Path(file_path)
        self.errors = []
        self.warnings = []

        if not file_path.exists():
            raise FileNotFoundError(f"CSV file not found: {file_path}")

        holdings = []
        snapshot_date = date.today()

        # Try to extract date from filename (e.g., "Portfolio_2024-01-15.csv")
        date_match = re.search(r"(\d{4}[-_]\d{2}[-_]\d{2})", file_path.stem)
        if date_match:
            try:
                date_str = date_match.group(1).replace("_", "-")
                snapshot_date = date.fromisoformat(date_str)
            except ValueError:
                pass

        with open(file_path, "r", encoding="utf-8-sig") as f:
            # Detect delimiter
            sample = f.read(4096)
            f.seek(0)
            delimiter = self._detect_delimiter(sample)

            reader = csv.DictReader(f, delimiter=delimiter)

            # Normalize column names
            if reader.fieldnames:
                column_map = self._map_columns(reader.fieldnames)
                logger.debug(f"Column mapping: {column_map}")

            for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is 1)
                try:
                    holding = self._parse_row(row, column_map, row_num)
                    if holding:
                        holdings.append(holding)
                except Exception as e:
                    self.errors.append(f"Row {row_num}: {str(e)}")
                    logger.warning(f"Error parsing row {row_num}: {e}")

        portfolio = Portfolio(
            holdings=holdings,
            snapshot_date=snapshot_date,
            source_file=str(file_path),
        )

        # Auto-classify sectors
        from .sector_lookup import classify_portfolio
        classify_result = classify_portfolio(portfolio)
        logger.debug(f"Classified {classify_result['classified']}/{classify_result['total']} holdings by sector")

        logger.info(
            f"Parsed {len(holdings)} holdings from {file_path.name}, "
            f"Total value: ${float(portfolio.total_market_value):,.2f}"
        )

        return portfolio

    def _detect_delimiter(self, sample: str) -> str:
        """Detect CSV delimiter from sample."""
        # Count occurrences of common delimiters
        delimiters = {",": 0, "\t": 0, ";": 0}
        for char, count in delimiters.items():
            delimiters[char] = sample.count(char)

        # Return most common delimiter
        return max(delimiters, key=delimiters.get)  # type: ignore

    def _map_columns(self, fieldnames: List[str]) -> Dict[str, str]:
        """
        Map actual column names to our standard names.

        Args:
            fieldnames: List of column names from CSV

        Returns:
            Dictionary mapping our field names to CSV column names
        """
        column_map: Dict[str, str] = {}
        fieldnames_lower = {f.lower().strip(): f for f in fieldnames}

        for our_field, possible_names in self.COLUMN_MAPPINGS.items():
            for name in possible_names:
                if name in fieldnames_lower:
                    column_map[our_field] = fieldnames_lower[name]
                    break

        return column_map

    def _parse_row(self, row: Dict[str, str], column_map: Dict[str, str], row_num: int) -> Optional[Holding]:
        """
        Parse a single CSV row into a Holding object.

        Args:
            row: CSV row as dictionary
            column_map: Mapping from our fields to CSV columns
            row_num: Row number for error reporting

        Returns:
            Holding object or None if row should be skipped
        """
        # Get code - skip if empty or header row
        code = self._get_value(row, column_map, "code", "").strip().upper()
        if not code or code in ("CODE", "TICKER", "SYMBOL"):
            return None

        # Get required fields
        name = self._get_value(row, column_map, "name", code)
        quantity = self._parse_int(self._get_value(row, column_map, "quantity", "0"))

        # Skip if no quantity
        if quantity == 0:
            self.warnings.append(f"Row {row_num}: Skipping {code} with zero quantity")
            return None

        # Parse price fields
        avg_cost = self._parse_decimal(self._get_value(row, column_map, "avg_cost", "0"))
        current_price = self._parse_decimal(self._get_value(row, column_map, "current_price", "0"))
        market_value = self._parse_decimal(self._get_value(row, column_map, "market_value", "0"))
        cost_base = self._parse_decimal(self._get_value(row, column_map, "cost_base", "0"))
        profit_loss = self._parse_decimal(self._get_value(row, column_map, "profit_loss", "0"))
        profit_loss_pct = self._parse_decimal(self._get_value(row, column_map, "profit_loss_percent", "0"))

        # Parse daily change fields (CommSec real-time data)
        daily_change = self._parse_decimal(self._get_value(row, column_map, "daily_change", "0"))
        daily_change_pct = self._parse_decimal(self._get_value(row, column_map, "daily_change_percent", "0"))
        value_change = self._parse_decimal(self._get_value(row, column_map, "value_change", "0"))

        # Classify the holding
        asset_class = self._classify_asset(code, name)

        return Holding(
            code=code,
            name=name,
            quantity=quantity,
            avg_cost=avg_cost,
            current_price=current_price,
            cost_base=cost_base,
            market_value=market_value,
            profit_loss=profit_loss,
            profit_loss_percent=profit_loss_pct,
            daily_change=daily_change,
            daily_change_percent=daily_change_pct,
            value_change=value_change,
            asset_class=asset_class,
        )

    def _get_value(self, row: Dict[str, str], column_map: Dict[str, str], field: str, default: str = "") -> str:
        """Get a value from the row using the column map."""
        if field in column_map:
            return row.get(column_map[field], default)
        return default

    def _parse_decimal(self, value: str) -> Decimal:
        """Parse a string to Decimal, handling various formats."""
        if not value:
            return Decimal("0")

        # Remove currency symbols, commas, spaces
        cleaned = re.sub(r"[$,\s]", "", value)

        # Handle parentheses for negative numbers (accounting format)
        if cleaned.startswith("(") and cleaned.endswith(")"):
            cleaned = "-" + cleaned[1:-1]

        # Handle percentage signs
        cleaned = cleaned.rstrip("%")

        try:
            return Decimal(cleaned)
        except InvalidOperation:
            return Decimal("0")

    def _parse_int(self, value: str) -> int:
        """Parse a string to int, handling various formats."""
        if not value:
            return 0

        # Remove commas and spaces
        cleaned = re.sub(r"[,\s]", "", value)

        try:
            # Handle decimal quantities (round to int)
            return int(float(cleaned))
        except ValueError:
            return 0

    def _classify_asset(self, code: str, name: str) -> AssetClass:
        """Classify an asset based on code and name."""
        code_upper = code.upper()
        name_lower = name.lower()

        if code_upper in KNOWN_ETFS:
            return AssetClass.ETF
        if code_upper in KNOWN_REITS:
            return AssetClass.REIT
        if code_upper in KNOWN_LICS:
            return AssetClass.LIC

        # Check name for keywords
        if any(kw in name_lower for kw in ["etf", "exchange traded", "index fund"]):
            return AssetClass.ETF
        if any(kw in name_lower for kw in ["reit", "property trust", "real estate"]):
            return AssetClass.REIT
        if any(kw in name_lower for kw in ["bond", "fixed income", "note"]):
            return AssetClass.FIXED_INCOME

        return AssetClass.AUSTRALIAN_EQUITY


def parse_commsec_csv(file_path: str | Path) -> Portfolio:
    """
    Convenience function to parse a CommSec CSV file.

    Args:
        file_path: Path to the CSV file

    Returns:
        Portfolio object with all holdings
    """
    parser = CommSecCSVParser()
    return parser.parse_file(file_path)
