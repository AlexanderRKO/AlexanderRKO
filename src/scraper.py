"""
Web scraper for NSW Auction Results from realestate.com.au

This module handles fetching and parsing auction data from the website.
It includes anti-blocking measures and respectful rate limiting.
"""
import re
import json
import time
import random
import logging
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple
from urllib.parse import urljoin
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import (
    BASE_URL, AUCTION_RESULTS_URL, REQUEST_HEADERS,
    REQUEST_DELAY_MIN, REQUEST_DELAY_MAX, MAX_RETRIES,
    RETRY_DELAY, get_region_for_postcode
)
from src.models import (
    AuctionResult, SuburbSummary, AuctionOutcome, PropertyType
)

logger = logging.getLogger(__name__)


class AuctionScraper:
    """
    Scraper for NSW auction results from realestate.com.au

    This scraper respects the website's resources by:
    - Using realistic browser headers
    - Rate limiting requests
    - Handling errors gracefully with retries
    """

    def __init__(self, session: Optional[requests.Session] = None):
        """Initialize the scraper with a requests session."""
        self.session = session or requests.Session()
        self.session.headers.update(REQUEST_HEADERS)
        self._last_request_time = 0

    def _rate_limit(self):
        """Implement rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
        if elapsed < delay:
            time.sleep(delay - elapsed)
        self._last_request_time = time.time()

    def _make_request(self, url: str, retries: int = MAX_RETRIES) -> Optional[requests.Response]:
        """
        Make a rate-limited request with retry logic.

        Args:
            url: The URL to fetch
            retries: Number of retries remaining

        Returns:
            Response object or None if all retries failed
        """
        self._rate_limit()

        for attempt in range(retries):
            try:
                logger.info(f"Fetching: {url} (attempt {attempt + 1}/{retries})")
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                return response

            except requests.exceptions.RequestException as e:
                logger.warning(f"Request failed: {e}")
                if attempt < retries - 1:
                    wait_time = RETRY_DELAY * (attempt + 1)
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"All retries exhausted for {url}")
                    return None

        return None

    def get_suburb_list(self) -> List[Dict[str, str]]:
        """
        Get the list of all suburbs with auction results.

        Returns:
            List of dicts with 'suburb', 'postcode', and 'url' keys
        """
        response = self._make_request(AUCTION_RESULTS_URL)
        if not response:
            logger.error("Failed to fetch main auction results page")
            return []

        suburbs = []
        soup = BeautifulSoup(response.text, 'html.parser')

        # Try to find suburb links - the actual selectors will need to be
        # adjusted based on the real page structure
        # Common patterns for suburb links:
        # - Links containing /auction-results/nsw/suburb-name-postcode
        # - Table rows with suburb data
        # - List items in a suburb directory

        # Pattern 1: Look for links with suburb URLs
        suburb_pattern = re.compile(r'/auction-results/nsw/([a-z\-]+)-(\d{4})')
        for link in soup.find_all('a', href=suburb_pattern):
            match = suburb_pattern.search(link.get('href', ''))
            if match:
                suburb_slug = match.group(1)
                postcode = match.group(2)
                suburb_name = suburb_slug.replace('-', ' ').title()

                suburbs.append({
                    'suburb': suburb_name,
                    'postcode': postcode,
                    'url': urljoin(BASE_URL, link['href']),
                    'region': get_region_for_postcode(postcode)
                })

        # Pattern 2: Look for JSON data embedded in the page
        # Many React/modern sites embed data in script tags
        for script in soup.find_all('script'):
            if script.string and 'suburbs' in script.string.lower():
                try:
                    # Try to extract JSON data
                    json_match = re.search(r'\{.*"suburbs".*\}', script.string)
                    if json_match:
                        data = json.loads(json_match.group())
                        # Process extracted data
                        logger.info("Found embedded JSON data")
                except json.JSONDecodeError:
                    pass

        logger.info(f"Found {len(suburbs)} suburbs")
        return suburbs

    def get_suburb_results(self, suburb_url: str) -> Tuple[Optional[SuburbSummary], List[AuctionResult]]:
        """
        Get auction results for a specific suburb.

        Args:
            suburb_url: URL to the suburb's auction results page

        Returns:
            Tuple of (SuburbSummary, List[AuctionResult])
        """
        response = self._make_request(suburb_url)
        if not response:
            logger.error(f"Failed to fetch suburb page: {suburb_url}")
            return None, []

        soup = BeautifulSoup(response.text, 'html.parser')
        results = []
        summary = None

        # Parse the page for auction results
        # These selectors will need to be adjusted based on actual page structure

        # Look for property cards/listings
        # Common patterns:
        # - div.property-card
        # - article.listing
        # - tr in a results table

        # Extract suburb info from URL
        url_match = re.search(r'/([a-z\-]+)-(\d{4})/?$', suburb_url)
        suburb_name = ""
        postcode = ""
        if url_match:
            suburb_name = url_match.group(1).replace('-', ' ').title()
            postcode = url_match.group(2)

        # Look for summary statistics
        # Common patterns:
        # - Clearance rate percentage
        # - Total auctions count
        # - Sold/passed in counts

        clearance_text = soup.find(string=re.compile(r'\d+\.?\d*%\s*clearance', re.I))
        clearance_rate = None
        if clearance_text:
            rate_match = re.search(r'(\d+\.?\d*)%', clearance_text)
            if rate_match:
                clearance_rate = float(rate_match.group(1))

        # Parse individual auction results
        # Look for property listings with auction outcomes
        property_cards = soup.find_all(['div', 'article'], class_=re.compile(r'(property|listing|result)', re.I))

        for card in property_cards:
            result = self._parse_property_card(card, suburb_name, postcode)
            if result:
                results.append(result)

        # Create summary if we have results
        if results or clearance_rate is not None:
            total_sold = sum(1 for r in results if r.outcome in [
                AuctionOutcome.SOLD, AuctionOutcome.SOLD_PRIOR, AuctionOutcome.SOLD_AFTER
            ])

            summary = SuburbSummary(
                suburb=suburb_name,
                postcode=postcode,
                region=get_region_for_postcode(postcode),
                week_ending=self._get_week_ending_date(),
                total_auctions=len(results),
                total_sold=total_sold,
                clearance_rate=clearance_rate,
                scraped_at=datetime.now()
            )

        return summary, results

    def _parse_property_card(self, card, suburb: str, postcode: str) -> Optional[AuctionResult]:
        """
        Parse a property card element to extract auction result data.

        Args:
            card: BeautifulSoup element containing property data
            suburb: Suburb name
            postcode: Postcode

        Returns:
            AuctionResult or None if parsing failed
        """
        try:
            # Extract address
            address_elem = card.find(['h2', 'h3', 'a'], class_=re.compile(r'address', re.I))
            if not address_elem:
                address_elem = card.find(['h2', 'h3', 'a'])
            address = address_elem.get_text(strip=True) if address_elem else ""

            # Extract price
            price = None
            price_undisclosed = False
            price_elem = card.find(string=re.compile(r'\$[\d,]+'))
            if price_elem:
                price_match = re.search(r'\$([\d,]+)', price_elem)
                if price_match:
                    price = int(price_match.group(1).replace(',', ''))
            else:
                # Check for undisclosed
                if card.find(string=re.compile(r'(undisclosed|not disclosed|price withheld)', re.I)):
                    price_undisclosed = True

            # Extract outcome
            outcome = AuctionOutcome.UNKNOWN
            outcome_text = card.get_text().lower()
            if 'sold prior' in outcome_text:
                outcome = AuctionOutcome.SOLD_PRIOR
            elif 'sold after' in outcome_text:
                outcome = AuctionOutcome.SOLD_AFTER
            elif 'sold' in outcome_text:
                outcome = AuctionOutcome.SOLD
            elif 'passed in' in outcome_text:
                outcome = AuctionOutcome.PASSED_IN
            elif 'withdrawn' in outcome_text:
                outcome = AuctionOutcome.WITHDRAWN

            # Extract property features (bedrooms, bathrooms, parking)
            bedrooms = None
            bathrooms = None
            parking = None

            bed_match = re.search(r'(\d+)\s*(?:bed|br)', card.get_text(), re.I)
            if bed_match:
                bedrooms = int(bed_match.group(1))

            bath_match = re.search(r'(\d+)\s*(?:bath|ba)', card.get_text(), re.I)
            if bath_match:
                bathrooms = int(bath_match.group(1))

            park_match = re.search(r'(\d+)\s*(?:car|parking|garage)', card.get_text(), re.I)
            if park_match:
                parking = int(park_match.group(1))

            # Extract property type
            property_type = None
            type_text = card.get_text().lower()
            if 'house' in type_text:
                property_type = PropertyType.HOUSE
            elif 'unit' in type_text:
                property_type = PropertyType.UNIT
            elif 'apartment' in type_text:
                property_type = PropertyType.APARTMENT
            elif 'townhouse' in type_text:
                property_type = PropertyType.TOWNHOUSE
            elif 'villa' in type_text:
                property_type = PropertyType.VILLA

            # Extract agent
            agent = None
            agent_elem = card.find(class_=re.compile(r'agent', re.I))
            if agent_elem:
                agent = agent_elem.get_text(strip=True)

            # Extract listing URL
            listing_url = None
            link_elem = card.find('a', href=True)
            if link_elem:
                listing_url = urljoin(BASE_URL, link_elem['href'])

            return AuctionResult(
                address=address,
                suburb=suburb,
                postcode=postcode,
                property_type=property_type,
                bedrooms=bedrooms,
                bathrooms=bathrooms,
                parking=parking,
                price=price,
                price_undisclosed=price_undisclosed,
                outcome=outcome,
                agent=agent,
                auction_date=self._get_week_ending_date(),
                listing_url=listing_url
            )

        except Exception as e:
            logger.warning(f"Failed to parse property card: {e}")
            return None

    def _get_week_ending_date(self) -> date:
        """Get the Saturday date for the current auction week."""
        today = date.today()
        # Find the most recent Saturday
        days_since_saturday = (today.weekday() + 2) % 7
        return today.replace(day=today.day - days_since_saturday)

    def scrape_all_suburbs(self, limit: Optional[int] = None) -> Tuple[List[SuburbSummary], List[AuctionResult]]:
        """
        Scrape auction results for all suburbs.

        Args:
            limit: Optional limit on number of suburbs to scrape (for testing)

        Returns:
            Tuple of (List[SuburbSummary], List[AuctionResult])
        """
        suburbs = self.get_suburb_list()
        if limit:
            suburbs = suburbs[:limit]

        all_summaries = []
        all_results = []

        for i, suburb in enumerate(suburbs):
            logger.info(f"Scraping {suburb['suburb']} ({i+1}/{len(suburbs)})")
            summary, results = self.get_suburb_results(suburb['url'])

            if summary:
                all_summaries.append(summary)
            all_results.extend(results)

        logger.info(f"Scraped {len(all_summaries)} suburbs with {len(all_results)} results")
        return all_summaries, all_results


class SeleniumScraper:
    """
    Alternative scraper using Selenium for JavaScript-rendered pages.

    Use this if the standard requests-based scraper fails due to
    dynamic content loading.
    """

    def __init__(self):
        """Initialize Selenium WebDriver."""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service

            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument(f'--user-agent={REQUEST_HEADERS["User-Agent"]}')

            self.driver = webdriver.Chrome(options=options)
            self.available = True
            logger.info("Selenium WebDriver initialized")

        except ImportError:
            logger.warning("Selenium not installed. Install with: pip install selenium")
            self.driver = None
            self.available = False
        except Exception as e:
            logger.warning(f"Failed to initialize Selenium: {e}")
            self.driver = None
            self.available = False

    def get_page_source(self, url: str, wait_time: int = 5) -> Optional[str]:
        """
        Get page source after JavaScript has rendered.

        Args:
            url: URL to fetch
            wait_time: Seconds to wait for page to load

        Returns:
            Page HTML source or None
        """
        if not self.available:
            return None

        try:
            self.driver.get(url)
            time.sleep(wait_time)  # Wait for JS to render
            return self.driver.page_source
        except Exception as e:
            logger.error(f"Selenium error: {e}")
            return None

    def close(self):
        """Close the WebDriver."""
        if self.driver:
            self.driver.quit()


def create_scraper(use_selenium: bool = False) -> AuctionScraper:
    """
    Factory function to create the appropriate scraper.

    Args:
        use_selenium: Whether to use Selenium for JS rendering

    Returns:
        Scraper instance
    """
    if use_selenium:
        selenium_scraper = SeleniumScraper()
        if selenium_scraper.available:
            # Wrap selenium in a compatible interface
            logger.info("Using Selenium scraper")
        else:
            logger.warning("Falling back to requests scraper")
            return AuctionScraper()

    return AuctionScraper()


if __name__ == "__main__":
    # Test the scraper
    logging.basicConfig(level=logging.INFO)
    scraper = AuctionScraper()

    print("Testing suburb list fetch...")
    suburbs = scraper.get_suburb_list()
    print(f"Found {len(suburbs)} suburbs")

    if suburbs:
        print(f"\nFirst 5 suburbs:")
        for s in suburbs[:5]:
            print(f"  - {s['suburb']} ({s['postcode']}) - {s['region']}")
