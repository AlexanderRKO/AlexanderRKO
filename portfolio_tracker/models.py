"""
Data models for portfolio tracking.
"""

from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, List, Dict, Any
import json


class AssetClass(Enum):
    """Classification of investment assets."""
    AUSTRALIAN_EQUITY = "australian_equity"
    INTERNATIONAL_EQUITY = "international_equity"
    ETF = "etf"
    LIC = "lic"  # Listed Investment Company
    REIT = "reit"  # Real Estate Investment Trust
    FIXED_INCOME = "fixed_income"
    HYBRID = "hybrid"
    CASH = "cash"
    OTHER = "other"


class Sector(Enum):
    """GICS Sectors for Australian equities."""
    ENERGY = "energy"
    MATERIALS = "materials"
    INDUSTRIALS = "industrials"
    CONSUMER_DISCRETIONARY = "consumer_discretionary"
    CONSUMER_STAPLES = "consumer_staples"
    HEALTH_CARE = "health_care"
    FINANCIALS = "financials"
    INFORMATION_TECHNOLOGY = "information_technology"
    COMMUNICATION_SERVICES = "communication_services"
    UTILITIES = "utilities"
    REAL_ESTATE = "real_estate"
    DIVERSIFIED = "diversified"
    UNKNOWN = "unknown"

    @classmethod
    def from_string(cls, text: str) -> "Sector":
        """Parse sector from text."""
        if not text:
            return cls.UNKNOWN
        text_lower = text.lower().strip()
        for sector in cls:
            if sector.value.replace("_", " ") in text_lower:
                return sector
        return cls.UNKNOWN


@dataclass
class Holding:
    """
    Represents a single stock/ETF holding in the portfolio.
    Maps to CommSec CSV export columns.
    """
    # Core identifiers
    code: str  # ASX ticker (e.g., "CBA", "VAS")
    name: str  # Company/ETF name

    # Position details
    quantity: int
    avg_cost: Decimal  # Average purchase price per unit
    current_price: Decimal  # Current market price per unit

    # Calculated values (from CSV or computed)
    cost_base: Decimal = Decimal("0")  # Total cost = quantity * avg_cost
    market_value: Decimal = Decimal("0")  # Current value = quantity * current_price
    profit_loss: Decimal = Decimal("0")  # market_value - cost_base
    profit_loss_percent: Decimal = Decimal("0")  # (profit_loss / cost_base) * 100

    # Optional income tracking
    dividends_received: Decimal = Decimal("0")
    franking_credits: Decimal = Decimal("0")

    # Classification
    asset_class: AssetClass = AssetClass.AUSTRALIAN_EQUITY
    sector: Sector = Sector.UNKNOWN

    # Weight in portfolio (calculated)
    portfolio_weight: Decimal = Decimal("0")

    # Metadata
    last_updated: datetime = field(default_factory=datetime.now)
    notes: str = ""

    def __post_init__(self):
        """Calculate derived values if not provided."""
        # Ensure Decimal types
        if isinstance(self.avg_cost, (int, float)):
            self.avg_cost = Decimal(str(self.avg_cost))
        if isinstance(self.current_price, (int, float)):
            self.current_price = Decimal(str(self.current_price))
        if isinstance(self.cost_base, (int, float)):
            self.cost_base = Decimal(str(self.cost_base))
        if isinstance(self.market_value, (int, float)):
            self.market_value = Decimal(str(self.market_value))
        if isinstance(self.profit_loss, (int, float)):
            self.profit_loss = Decimal(str(self.profit_loss))
        if isinstance(self.profit_loss_percent, (int, float)):
            self.profit_loss_percent = Decimal(str(self.profit_loss_percent))

        # Calculate if not provided
        if self.cost_base == 0:
            self.cost_base = Decimal(str(self.quantity)) * self.avg_cost
        if self.market_value == 0:
            self.market_value = Decimal(str(self.quantity)) * self.current_price
        if self.profit_loss == 0 and self.cost_base > 0:
            self.profit_loss = self.market_value - self.cost_base
        if self.profit_loss_percent == 0 and self.cost_base > 0:
            self.profit_loss_percent = (self.profit_loss / self.cost_base) * Decimal("100")

    @property
    def total_return(self) -> Decimal:
        """Total return including dividends."""
        return self.profit_loss + self.dividends_received

    @property
    def total_return_percent(self) -> Decimal:
        """Total return percentage including dividends."""
        if self.cost_base == 0:
            return Decimal("0")
        return (self.total_return / self.cost_base) * Decimal("100")

    @property
    def is_profitable(self) -> bool:
        """Check if holding is in profit."""
        return self.profit_loss > 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage/JSON."""
        return {
            "code": self.code,
            "name": self.name,
            "quantity": self.quantity,
            "avg_cost": float(self.avg_cost),
            "current_price": float(self.current_price),
            "cost_base": float(self.cost_base),
            "market_value": float(self.market_value),
            "profit_loss": float(self.profit_loss),
            "profit_loss_percent": float(self.profit_loss_percent),
            "dividends_received": float(self.dividends_received),
            "franking_credits": float(self.franking_credits),
            "asset_class": self.asset_class.value,
            "sector": self.sector.value,
            "portfolio_weight": float(self.portfolio_weight),
            "last_updated": self.last_updated.isoformat(),
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Holding":
        """Create from dictionary."""
        data = data.copy()
        if "asset_class" in data and isinstance(data["asset_class"], str):
            data["asset_class"] = AssetClass(data["asset_class"])
        if "sector" in data and isinstance(data["sector"], str):
            data["sector"] = Sector(data["sector"])
        if "last_updated" in data and isinstance(data["last_updated"], str):
            data["last_updated"] = datetime.fromisoformat(data["last_updated"])
        return cls(**data)


@dataclass
class Portfolio:
    """
    Represents the complete portfolio at a point in time.
    """
    holdings: List[Holding] = field(default_factory=list)
    snapshot_date: date = field(default_factory=date.today)
    snapshot_id: Optional[str] = None

    # Aggregated values (calculated)
    total_cost_base: Decimal = Decimal("0")
    total_market_value: Decimal = Decimal("0")
    total_profit_loss: Decimal = Decimal("0")
    total_profit_loss_percent: Decimal = Decimal("0")

    # Income tracking
    total_dividends: Decimal = Decimal("0")
    total_franking_credits: Decimal = Decimal("0")

    # Metadata
    source_file: str = ""
    import_timestamp: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Calculate aggregated values and weights."""
        self.recalculate()

    def recalculate(self):
        """Recalculate all aggregated values and weights."""
        if not self.holdings:
            return

        self.total_cost_base = sum(h.cost_base for h in self.holdings)
        self.total_market_value = sum(h.market_value for h in self.holdings)
        self.total_profit_loss = self.total_market_value - self.total_cost_base
        self.total_dividends = sum(h.dividends_received for h in self.holdings)
        self.total_franking_credits = sum(h.franking_credits for h in self.holdings)

        if self.total_cost_base > 0:
            self.total_profit_loss_percent = (
                self.total_profit_loss / self.total_cost_base
            ) * Decimal("100")

        # Calculate portfolio weights
        for holding in self.holdings:
            if self.total_market_value > 0:
                holding.portfolio_weight = (
                    holding.market_value / self.total_market_value
                ) * Decimal("100")

        # Generate snapshot ID if not set
        if not self.snapshot_id:
            import hashlib
            unique_str = f"{self.snapshot_date}_{len(self.holdings)}_{float(self.total_market_value)}"
            self.snapshot_id = hashlib.md5(unique_str.encode()).hexdigest()[:12]

    def add_holding(self, holding: Holding):
        """Add a holding and recalculate."""
        self.holdings.append(holding)
        self.recalculate()

    def get_holding(self, code: str) -> Optional[Holding]:
        """Get a holding by ticker code."""
        code_upper = code.upper()
        for holding in self.holdings:
            if holding.code.upper() == code_upper:
                return holding
        return None

    def get_holdings_by_sector(self, sector: Sector) -> List[Holding]:
        """Get all holdings in a sector."""
        return [h for h in self.holdings if h.sector == sector]

    def get_holdings_by_asset_class(self, asset_class: AssetClass) -> List[Holding]:
        """Get all holdings in an asset class."""
        return [h for h in self.holdings if h.asset_class == asset_class]

    @property
    def top_holdings(self) -> List[Holding]:
        """Get holdings sorted by weight (largest first)."""
        return sorted(self.holdings, key=lambda h: h.market_value, reverse=True)

    @property
    def best_performers(self) -> List[Holding]:
        """Get holdings sorted by return percentage (best first)."""
        return sorted(self.holdings, key=lambda h: h.profit_loss_percent, reverse=True)

    @property
    def worst_performers(self) -> List[Holding]:
        """Get holdings sorted by return percentage (worst first)."""
        return sorted(self.holdings, key=lambda h: h.profit_loss_percent)

    @property
    def profitable_holdings(self) -> List[Holding]:
        """Get all holdings in profit."""
        return [h for h in self.holdings if h.is_profitable]

    @property
    def losing_holdings(self) -> List[Holding]:
        """Get all holdings in loss."""
        return [h for h in self.holdings if not h.is_profitable]

    @property
    def holding_count(self) -> int:
        """Number of holdings."""
        return len(self.holdings)

    def sector_allocation(self) -> Dict[Sector, Decimal]:
        """Calculate allocation by sector."""
        allocation: Dict[Sector, Decimal] = {}
        for holding in self.holdings:
            if holding.sector not in allocation:
                allocation[holding.sector] = Decimal("0")
            allocation[holding.sector] += holding.portfolio_weight
        return allocation

    def asset_class_allocation(self) -> Dict[AssetClass, Decimal]:
        """Calculate allocation by asset class."""
        allocation: Dict[AssetClass, Decimal] = {}
        for holding in self.holdings:
            if holding.asset_class not in allocation:
                allocation[holding.asset_class] = Decimal("0")
            allocation[holding.asset_class] += holding.portfolio_weight
        return allocation

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "snapshot_id": self.snapshot_id,
            "snapshot_date": self.snapshot_date.isoformat(),
            "holdings": [h.to_dict() for h in self.holdings],
            "total_cost_base": float(self.total_cost_base),
            "total_market_value": float(self.total_market_value),
            "total_profit_loss": float(self.total_profit_loss),
            "total_profit_loss_percent": float(self.total_profit_loss_percent),
            "total_dividends": float(self.total_dividends),
            "total_franking_credits": float(self.total_franking_credits),
            "source_file": self.source_file,
            "import_timestamp": self.import_timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Portfolio":
        """Create from dictionary."""
        holdings = [Holding.from_dict(h) for h in data.get("holdings", [])]
        return cls(
            holdings=holdings,
            snapshot_date=date.fromisoformat(data["snapshot_date"]),
            snapshot_id=data.get("snapshot_id"),
            source_file=data.get("source_file", ""),
        )

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class PortfolioSnapshot:
    """
    A lightweight snapshot for historical tracking.
    Used for tracking portfolio value over time.
    """
    snapshot_id: str
    snapshot_date: date
    total_holdings: int
    total_market_value: Decimal
    total_cost_base: Decimal
    total_profit_loss: Decimal
    total_profit_loss_percent: Decimal

    @classmethod
    def from_portfolio(cls, portfolio: Portfolio) -> "PortfolioSnapshot":
        """Create snapshot from portfolio."""
        return cls(
            snapshot_id=portfolio.snapshot_id or "",
            snapshot_date=portfolio.snapshot_date,
            total_holdings=len(portfolio.holdings),
            total_market_value=portfolio.total_market_value,
            total_cost_base=portfolio.total_cost_base,
            total_profit_loss=portfolio.total_profit_loss,
            total_profit_loss_percent=portfolio.total_profit_loss_percent,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "snapshot_id": self.snapshot_id,
            "snapshot_date": self.snapshot_date.isoformat(),
            "total_holdings": self.total_holdings,
            "total_market_value": float(self.total_market_value),
            "total_cost_base": float(self.total_cost_base),
            "total_profit_loss": float(self.total_profit_loss),
            "total_profit_loss_percent": float(self.total_profit_loss_percent),
        }
