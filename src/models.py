"""
Data models for NSW Auction Results

This module defines the data structures used to store and process
auction results data from realestate.com.au
"""
from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from typing import Optional, List
from enum import Enum


class AuctionOutcome(Enum):
    """Possible outcomes for an auction."""
    SOLD = "sold"
    SOLD_PRIOR = "sold_prior"
    SOLD_AFTER = "sold_after"
    PASSED_IN = "passed_in"
    WITHDRAWN = "withdrawn"
    POSTPONED = "postponed"
    UNKNOWN = "unknown"


class PropertyType(Enum):
    """Types of properties."""
    HOUSE = "house"
    UNIT = "unit"
    APARTMENT = "apartment"
    TOWNHOUSE = "townhouse"
    VILLA = "villa"
    LAND = "land"
    OTHER = "other"


@dataclass
class AuctionResult:
    """
    Individual auction result for a single property.

    Attributes:
        address: Full street address of the property
        suburb: Suburb name
        postcode: 4-digit postcode
        state: State (always NSW for this project)
        property_type: Type of property (house, unit, etc.)
        bedrooms: Number of bedrooms (if available)
        bathrooms: Number of bathrooms (if available)
        parking: Number of parking spaces (if available)
        price: Sale price in AUD (if sold and disclosed)
        outcome: Auction outcome (sold, passed in, etc.)
        agent: Real estate agent/agency name
        auction_date: Date of the auction
        scraped_at: Timestamp when data was scraped
        listing_url: URL to the original listing (if available)
    """
    address: str
    suburb: str
    postcode: str
    state: str = "NSW"
    property_type: Optional[PropertyType] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    parking: Optional[int] = None
    price: Optional[int] = None
    price_undisclosed: bool = False
    outcome: AuctionOutcome = AuctionOutcome.UNKNOWN
    agent: Optional[str] = None
    auction_date: Optional[date] = None
    scraped_at: datetime = field(default_factory=datetime.now)
    listing_url: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        data = asdict(self)
        data['property_type'] = self.property_type.value if self.property_type else None
        data['outcome'] = self.outcome.value
        data['auction_date'] = self.auction_date.isoformat() if self.auction_date else None
        data['scraped_at'] = self.scraped_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'AuctionResult':
        """Create instance from dictionary."""
        if data.get('property_type'):
            data['property_type'] = PropertyType(data['property_type'])
        if data.get('outcome'):
            data['outcome'] = AuctionOutcome(data['outcome'])
        if data.get('auction_date') and isinstance(data['auction_date'], str):
            data['auction_date'] = date.fromisoformat(data['auction_date'])
        if data.get('scraped_at') and isinstance(data['scraped_at'], str):
            data['scraped_at'] = datetime.fromisoformat(data['scraped_at'])
        return cls(**data)


@dataclass
class SuburbSummary:
    """
    Summary statistics for a suburb's auction results.

    Attributes:
        suburb: Suburb name
        postcode: 4-digit postcode
        region: Geographic region
        week_ending: The Saturday date for the auction week
        total_auctions: Total number of auctions scheduled
        total_sold: Number of properties sold (all methods)
        sold_at_auction: Sold under the hammer
        sold_prior: Sold before auction
        sold_after: Sold after auction
        passed_in: Properties that didn't sell
        withdrawn: Auctions that were withdrawn
        clearance_rate: Percentage of auctions that resulted in a sale
        median_price: Median sale price for the week
        total_sales_value: Sum of all disclosed sales
        scraped_at: Timestamp when data was scraped
    """
    suburb: str
    postcode: str
    region: str
    week_ending: date
    total_auctions: int = 0
    total_sold: int = 0
    sold_at_auction: int = 0
    sold_prior: int = 0
    sold_after: int = 0
    passed_in: int = 0
    withdrawn: int = 0
    clearance_rate: Optional[float] = None
    median_price: Optional[int] = None
    total_sales_value: Optional[int] = None
    scraped_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        data = asdict(self)
        data['week_ending'] = self.week_ending.isoformat()
        data['scraped_at'] = self.scraped_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'SuburbSummary':
        """Create instance from dictionary."""
        if isinstance(data.get('week_ending'), str):
            data['week_ending'] = date.fromisoformat(data['week_ending'])
        if isinstance(data.get('scraped_at'), str):
            data['scraped_at'] = datetime.fromisoformat(data['scraped_at'])
        return cls(**data)


@dataclass
class RegionalSummary:
    """
    Aggregated summary for a region (e.g., Sydney Inner, Sydney North).

    Attributes:
        region: Region name
        week_ending: The Saturday date for the auction week
        suburbs_count: Number of suburbs with auctions
        total_auctions: Total auctions in the region
        total_sold: Total properties sold
        clearance_rate: Regional clearance rate
        median_price: Regional median price
        total_sales_value: Total value of all sales
    """
    region: str
    week_ending: date
    suburbs_count: int = 0
    total_auctions: int = 0
    total_sold: int = 0
    clearance_rate: Optional[float] = None
    median_price: Optional[int] = None
    total_sales_value: Optional[int] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        data = asdict(self)
        data['week_ending'] = self.week_ending.isoformat()
        return data


@dataclass
class WeeklySummary:
    """
    State-wide weekly summary for NSW.

    Attributes:
        week_ending: The Saturday date for the auction week
        total_auctions: Total auctions state-wide
        total_sold: Total properties sold
        clearance_rate: State-wide clearance rate
        median_price: State-wide median price
        total_sales_value: Total value of all sales
        sydney_clearance_rate: Sydney metro clearance rate
        regional_clearance_rate: Regional NSW clearance rate
    """
    week_ending: date
    total_auctions: int = 0
    total_sold: int = 0
    clearance_rate: Optional[float] = None
    median_price: Optional[int] = None
    total_sales_value: Optional[int] = None
    sydney_clearance_rate: Optional[float] = None
    regional_clearance_rate: Optional[float] = None
    suburbs_with_auctions: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        data = asdict(self)
        data['week_ending'] = self.week_ending.isoformat()
        return data
