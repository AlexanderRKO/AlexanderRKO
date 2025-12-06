"""
Data models for NSW auction results.
"""

from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from enum import Enum
from typing import Optional, List, Dict, Any
import json


class AuctionOutcome(Enum):
    """Possible outcomes of an auction."""
    SOLD_AT_AUCTION = "sold_at_auction"
    SOLD_BEFORE_AUCTION = "sold_before_auction"
    SOLD_AFTER_AUCTION = "sold_after_auction"
    PASSED_IN = "passed_in"
    PASSED_IN_VENDOR_BID = "passed_in_vendor_bid"
    WITHDRAWN = "withdrawn"
    POSTPONED = "postponed"
    UNKNOWN = "unknown"

    @classmethod
    def from_string(cls, text: str) -> "AuctionOutcome":
        """Parse outcome from text found on website."""
        text_lower = text.lower().strip()

        if "sold at auction" in text_lower or "sold under the hammer" in text_lower:
            return cls.SOLD_AT_AUCTION
        elif "sold before" in text_lower or "sold prior" in text_lower:
            return cls.SOLD_BEFORE_AUCTION
        elif "sold after" in text_lower:
            return cls.SOLD_AFTER_AUCTION
        elif "passed in" in text_lower and "vendor" in text_lower:
            return cls.PASSED_IN_VENDOR_BID
        elif "passed in" in text_lower:
            return cls.PASSED_IN
        elif "withdrawn" in text_lower:
            return cls.WITHDRAWN
        elif "postponed" in text_lower:
            return cls.POSTPONED
        else:
            return cls.UNKNOWN


class PropertyType(Enum):
    """Types of properties."""
    HOUSE = "house"
    UNIT = "unit"
    APARTMENT = "apartment"
    TOWNHOUSE = "townhouse"
    VILLA = "villa"
    LAND = "land"
    RURAL = "rural"
    OTHER = "other"

    @classmethod
    def from_string(cls, text: str) -> "PropertyType":
        """Parse property type from text."""
        text_lower = text.lower().strip()

        for ptype in cls:
            if ptype.value in text_lower:
                return ptype
        return cls.OTHER


@dataclass
class AuctionResult:
    """
    Represents a single auction result for a property.
    """
    # Unique identifier
    id: Optional[str] = None

    # Location details
    address: str = ""
    suburb: str = ""
    postcode: str = ""
    state: str = "NSW"
    region: str = ""

    # Property details
    property_type: PropertyType = PropertyType.OTHER
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    parking: Optional[int] = None
    land_size: Optional[int] = None  # in sqm

    # Auction details
    auction_date: Optional[date] = None
    outcome: AuctionOutcome = AuctionOutcome.UNKNOWN

    # Price information
    sold_price: Optional[int] = None
    guide_price_low: Optional[int] = None
    guide_price_high: Optional[int] = None
    reserve_price: Optional[int] = None  # rarely available

    # Agent/Agency
    agent_name: Optional[str] = None
    agency_name: Optional[str] = None

    # Source information
    source_url: Optional[str] = None
    listing_id: Optional[str] = None

    # Metadata
    collected_at: datetime = field(default_factory=datetime.now)
    collection_week: Optional[str] = None  # Format: "2024-W01"

    def __post_init__(self):
        """Generate ID and collection week if not set."""
        if self.id is None and self.address and self.auction_date:
            # Create a unique ID from address and date
            import hashlib
            unique_str = f"{self.address}_{self.auction_date}"
            self.id = hashlib.md5(unique_str.encode()).hexdigest()[:12]

        if self.collection_week is None and self.auction_date:
            self.collection_week = self.auction_date.strftime("%Y-W%W")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        data = asdict(self)
        # Convert enums to strings
        data["property_type"] = self.property_type.value
        data["outcome"] = self.outcome.value
        # Convert dates to ISO format
        if self.auction_date:
            data["auction_date"] = self.auction_date.isoformat()
        if self.collected_at:
            data["collected_at"] = self.collected_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuctionResult":
        """Create from dictionary."""
        # Convert string values back to enums
        if "property_type" in data and isinstance(data["property_type"], str):
            data["property_type"] = PropertyType(data["property_type"])
        if "outcome" in data and isinstance(data["outcome"], str):
            data["outcome"] = AuctionOutcome(data["outcome"])
        # Convert date strings back to date objects
        if "auction_date" in data and isinstance(data["auction_date"], str):
            data["auction_date"] = date.fromisoformat(data["auction_date"])
        if "collected_at" in data and isinstance(data["collected_at"], str):
            data["collected_at"] = datetime.fromisoformat(data["collected_at"])
        return cls(**data)

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())

    @property
    def is_sold(self) -> bool:
        """Check if property was sold."""
        return self.outcome in [
            AuctionOutcome.SOLD_AT_AUCTION,
            AuctionOutcome.SOLD_BEFORE_AUCTION,
            AuctionOutcome.SOLD_AFTER_AUCTION,
        ]

    @property
    def clearance_status(self) -> str:
        """Return clearance status for statistics."""
        if self.is_sold:
            return "sold"
        elif self.outcome in [AuctionOutcome.PASSED_IN, AuctionOutcome.PASSED_IN_VENDOR_BID]:
            return "passed_in"
        else:
            return "other"


@dataclass
class SuburbSummary:
    """
    Summary statistics for a suburb's auction results.
    """
    suburb: str
    postcode: str
    region: str
    week: str  # Format: "2024-W01"

    # Counts
    total_auctions: int = 0
    sold_count: int = 0
    passed_in_count: int = 0
    withdrawn_count: int = 0

    # Prices
    median_price: Optional[int] = None
    average_price: Optional[int] = None
    min_price: Optional[int] = None
    max_price: Optional[int] = None
    total_value: Optional[int] = None

    # By property type
    houses_sold: int = 0
    units_sold: int = 0

    # Calculated at aggregation
    clearance_rate: Optional[float] = None

    def calculate_clearance_rate(self) -> float:
        """Calculate the clearance rate."""
        if self.total_auctions == 0:
            return 0.0
        self.clearance_rate = (self.sold_count / self.total_auctions) * 100
        return self.clearance_rate

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class WeeklySnapshot:
    """
    Weekly snapshot of all NSW auction data.
    """
    week: str  # Format: "2024-W01"
    collection_date: date

    # Overall NSW statistics
    total_auctions: int = 0
    total_sold: int = 0
    total_passed_in: int = 0
    overall_clearance_rate: float = 0.0

    # Price statistics
    median_price: Optional[int] = None
    average_price: Optional[int] = None
    total_value: Optional[int] = None

    # By region
    region_summaries: Dict[str, SuburbSummary] = field(default_factory=dict)

    # Raw data reference
    results_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = {
            "week": self.week,
            "collection_date": self.collection_date.isoformat(),
            "total_auctions": self.total_auctions,
            "total_sold": self.total_sold,
            "total_passed_in": self.total_passed_in,
            "overall_clearance_rate": self.overall_clearance_rate,
            "median_price": self.median_price,
            "average_price": self.average_price,
            "total_value": self.total_value,
            "results_count": self.results_count,
            "region_summaries": {
                k: v.to_dict() for k, v in self.region_summaries.items()
            },
        }
        return data
