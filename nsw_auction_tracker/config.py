"""
Configuration settings for NSW Auction Tracker.
"""

import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

# Base directories
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

# Database
DATABASE_PATH = DATA_DIR / "auction_results.db"

# Scraper settings
BASE_URL = "https://www.realestate.com.au"
AUCTION_RESULTS_URL = f"{BASE_URL}/auction-results/nsw"

# Known NSW regions/areas for auction results
# These are the main areas listed on the auction results page
NSW_REGIONS = [
    "sydney",
    "central-coast",
    "hunter",
    "illawarra",
    "newcastle",
    "wollongong",
    "blue-mountains",
    "northern-beaches",
    "eastern-suburbs",
    "inner-west",
    "north-shore",
    "northern-suburbs",
    "south-west",
    "western-sydney",
    "sutherland-shire",
    "hills-district",
]

# =============================================================================
# PREFERRED POSTCODES - Configure your suburbs of interest here
# =============================================================================
# Add up to 10 postcodes you want to track. This is the recommended approach
# as it minimizes server load and respects the website.
#
# Example postcodes by area:
#   Eastern Suburbs: 2021 (Paddington), 2022 (Bondi Junction), 2026 (Bondi)
#   Inner West: 2042 (Newtown), 2043 (Erskineville), 2044 (St Peters)
#   North Shore: 2060 (North Sydney), 2061 (Kirribilli), 2065 (Crows Nest)
#   Northern Beaches: 2095 (Manly), 2097 (Collaroy), 2099 (Dee Why)
#   Hills District: 2153 (Baulkham Hills), 2154 (Castle Hill)
#   Sutherland: 2229 (Caringbah), 2230 (Cronulla)

PREFERRED_POSTCODES = [
    "2137",  # Breakfast Point, Cabarita, Mortlake, Rodd Point
    "2150",  # Parramatta, Harris Park
    "2138",  # Concord West, Liberty Grove, Rhodes
    "2127",  # Newington, Sydney Olympic Park, Wentworth Point
    "2481",  # Byron Bay, Suffolk Park
]

# Maximum postcodes to track (to stay API-friendly)
MAX_POSTCODES = 10

# =============================================================================
# Request settings - Conservative defaults to be respectful
# =============================================================================
REQUEST_TIMEOUT = 30
REQUEST_DELAY_MIN = 5   # Minimum seconds between requests (increased for safety)
REQUEST_DELAY_MAX = 10  # Maximum seconds between requests (increased for safety)
MAX_RETRIES = 2         # Fewer retries to avoid hammering

# User agent rotation pool (for ethical scraping)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]

# Scheduler settings
COLLECTION_DAY = "sunday"  # Day of the week to run collection
COLLECTION_TIME = "06:00"  # Time to run (after 5am refresh)


@dataclass
class ScraperConfig:
    """Configuration for the scraper."""
    base_url: str = BASE_URL
    timeout: int = REQUEST_TIMEOUT
    delay_min: float = REQUEST_DELAY_MIN
    delay_max: float = REQUEST_DELAY_MAX
    max_retries: int = MAX_RETRIES
    use_proxy: bool = False
    proxy_url: Optional[str] = None
    headless: bool = True  # For browser-based scraping


# Ensure directories exist
def ensure_directories():
    """Create necessary directories if they don't exist."""
    for directory in [DATA_DIR, RAW_DATA_DIR, PROCESSED_DATA_DIR]:
        directory.mkdir(parents=True, exist_ok=True)
