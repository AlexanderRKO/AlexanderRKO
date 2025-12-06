"""Tests for data models."""
import pytest
from datetime import date, datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models import (
    AuctionResult, SuburbSummary, AuctionOutcome, PropertyType
)


class TestAuctionResult:
    """Tests for AuctionResult model."""

    def test_create_auction_result(self):
        """Test creating an auction result."""
        result = AuctionResult(
            address="123 Test Street",
            suburb="Paddington",
            postcode="2021",
            price=2500000,
            outcome=AuctionOutcome.SOLD
        )

        assert result.address == "123 Test Street"
        assert result.suburb == "Paddington"
        assert result.postcode == "2021"
        assert result.price == 2500000
        assert result.outcome == AuctionOutcome.SOLD
        assert result.state == "NSW"

    def test_to_dict(self):
        """Test converting to dictionary."""
        result = AuctionResult(
            address="123 Test Street",
            suburb="Paddington",
            postcode="2021",
            property_type=PropertyType.HOUSE,
            price=2500000,
            outcome=AuctionOutcome.SOLD,
            auction_date=date(2024, 12, 7)
        )

        data = result.to_dict()

        assert data['address'] == "123 Test Street"
        assert data['property_type'] == "house"
        assert data['outcome'] == "sold"
        assert data['auction_date'] == "2024-12-07"

    def test_from_dict(self):
        """Test creating from dictionary."""
        data = {
            'address': "456 Example Ave",
            'suburb': "Bondi",
            'postcode': "2026",
            'state': "NSW",
            'property_type': "unit",
            'bedrooms': 2,
            'bathrooms': 1,
            'parking': 1,
            'price': 1200000,
            'price_undisclosed': False,
            'outcome': "sold_prior",
            'agent': "Test Agency",
            'auction_date': "2024-12-07",
            'scraped_at': "2024-12-08T10:00:00",
            'listing_url': None
        }

        result = AuctionResult.from_dict(data)

        assert result.address == "456 Example Ave"
        assert result.property_type == PropertyType.UNIT
        assert result.outcome == AuctionOutcome.SOLD_PRIOR
        assert result.auction_date == date(2024, 12, 7)


class TestSuburbSummary:
    """Tests for SuburbSummary model."""

    def test_create_suburb_summary(self):
        """Test creating a suburb summary."""
        summary = SuburbSummary(
            suburb="Paddington",
            postcode="2021",
            region="sydney_east",
            week_ending=date(2024, 12, 7),
            total_auctions=10,
            total_sold=8,
            clearance_rate=80.0
        )

        assert summary.suburb == "Paddington"
        assert summary.clearance_rate == 80.0
        assert summary.total_auctions == 10

    def test_to_dict(self):
        """Test converting to dictionary."""
        summary = SuburbSummary(
            suburb="Bondi",
            postcode="2026",
            region="sydney_east",
            week_ending=date(2024, 12, 7),
            total_auctions=15,
            total_sold=12
        )

        data = summary.to_dict()

        assert data['suburb'] == "Bondi"
        assert data['week_ending'] == "2024-12-07"
        assert isinstance(data['scraped_at'], str)


class TestAuctionOutcome:
    """Tests for AuctionOutcome enum."""

    def test_outcome_values(self):
        """Test outcome enum values."""
        assert AuctionOutcome.SOLD.value == "sold"
        assert AuctionOutcome.PASSED_IN.value == "passed_in"
        assert AuctionOutcome.WITHDRAWN.value == "withdrawn"


class TestPropertyType:
    """Tests for PropertyType enum."""

    def test_property_type_values(self):
        """Test property type enum values."""
        assert PropertyType.HOUSE.value == "house"
        assert PropertyType.UNIT.value == "unit"
        assert PropertyType.APARTMENT.value == "apartment"
