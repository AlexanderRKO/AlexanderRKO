"""Scraper modules for auction data collection."""

from .base import BaseScraper, ScraperError
from .realestate_scraper import RealEstateAuctionScraper

__all__ = [
    "BaseScraper",
    "ScraperError",
    "RealEstateAuctionScraper",
]
