"""
Web scraper for NSW Auction Results from realestate.com.au

This scraper is designed for personal use - tracking auction results
in specific suburbs you're interested in. It behaves like a person
casually browsing the website on a Sunday morning.

Key principles:
- Only fetch YOUR tracked postcodes (defined in config/my_postcodes.py)
- Human-like delays between requests (8-20 seconds)
- Single browser session, just like a real person
- Respectful retry behavior - back off if there are issues
"""
import re
import time
import random
import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Tuple
from urllib.parse import urljoin
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import (
    BASE_URL, REQUEST_HEADERS,
    REQUEST_DELAY_MIN, REQUEST_DELAY_MAX, MAX_RETRIES,
    RETRY_DELAY, get_region_for_postcode
)
from config.my_postcodes import get_tracked_suburbs, validate_config
from src.models import (
    AuctionResult, SuburbSummary, AuctionOutcome, PropertyType
)

logger = logging.getLogger(__name__)


class AuctionScraper:
    """
    Personal auction results tracker.

    Fetches auction data only for your tracked postcodes,
    behaving like a genuine user browsing the site.
    """

    def __init__(self):
        """Initialize with a persistent browser-like session."""
        self.session = requests.Session()
        self.session.headers.update(REQUEST_HEADERS)
        self._last_request_time = 0
        self._request_count = 0

    def _human_delay(self):
        """
        Wait like a human would between page views.

        Real people don't click links instantly - they read the page,
        scroll around, maybe get distracted, then click the next link.
        """
        elapsed = time.time() - self._last_request_time

        # Base delay - like reading a page
        base_delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)

        # Occasionally take a longer pause (20% chance)
        # Like checking phone or getting a coffee
        if random.random() < 0.2:
            extra = random.uniform(10, 30)
            base_delay += extra
            logger.debug(f"Taking a longer pause (+{extra:.0f}s)...")

        # Don't wait if we've already waited long enough
        wait_time = max(0, base_delay - elapsed)

        if wait_time > 0:
            logger.debug(f"Waiting {wait_time:.1f}s...")
            time.sleep(wait_time)

        self._last_request_time = time.time()

    def _fetch_page(self, url: str) -> Optional[str]:
        """
        Fetch a single page, like browsing to it in a browser.

        Args:
            url: The URL to fetch

        Returns:
            Page HTML content or None if failed
        """
        self._human_delay()
        self._request_count += 1

        for attempt in range(MAX_RETRIES):
            try:
                logger.info(f"Fetching: {url}")
                response = self.session.get(url, timeout=30)

                if response.status_code == 200:
                    return response.text

                elif response.status_code == 429:
                    # Rate limited - back off significantly like a real user would
                    logger.warning("Got rate limited. Taking a 3 minute break...")
                    time.sleep(180)

                elif response.status_code == 403:
                    logger.error("Access denied (403). Site may be blocking automated access.")
                    logger.info("Try running at a different time or check if the site structure changed.")
                    return None

                else:
                    logger.warning(f"Unexpected status: {response.status_code}")

            except requests.exceptions.Timeout:
                logger.warning("Request timed out - connection might be slow")

            except requests.exceptions.RequestException as e:
                logger.warning(f"Request error: {e}")

            # Wait before retry (like refreshing after an error)
            if attempt < MAX_RETRIES - 1:
                wait = RETRY_DELAY * (attempt + 1)
                logger.info(f"Waiting {wait}s before trying again...")
                time.sleep(wait)

        logger.error(f"Could not fetch {url} after {MAX_RETRIES} attempts")
        return None

    def fetch_suburb_results(self, suburb_info: Dict) -> Tuple[Optional[SuburbSummary], List[AuctionResult]]:
        """
        Fetch auction results for a single suburb.

        Args:
            suburb_info: Dict with 'suburb', 'postcode', 'url' keys

        Returns:
            Tuple of (SuburbSummary, List[AuctionResult])
        """
        html = self._fetch_page(suburb_info['url'])
        if not html:
            return None, []

        soup = BeautifulSoup(html, 'html.parser')

        suburb = suburb_info['suburb']
        postcode = suburb_info['postcode']

        # Extract clearance rate from page
        clearance_rate = self._extract_clearance_rate(soup)

        # Extract individual property results
        results = self._extract_property_results(soup, suburb, postcode)

        # Calculate totals
        total_sold = sum(1 for r in results if r.outcome in [
            AuctionOutcome.SOLD, AuctionOutcome.SOLD_PRIOR, AuctionOutcome.SOLD_AFTER
        ])
        total_passed = sum(1 for r in results if r.outcome == AuctionOutcome.PASSED_IN)

        # Create summary if we found anything
        if clearance_rate is not None or results:
            summary = SuburbSummary(
                suburb=suburb,
                postcode=postcode,
                region=get_region_for_postcode(postcode),
                week_ending=self._get_week_ending(),
                total_auctions=len(results),
                total_sold=total_sold,
                passed_in=total_passed,
                clearance_rate=clearance_rate,
                scraped_at=datetime.now()
            )
            return summary, results

        logger.info(f"No auction data found for {suburb} ({postcode}) this week")
        return None, []

    def _extract_clearance_rate(self, soup: BeautifulSoup) -> Optional[float]:
        """Extract clearance rate from page text."""
        page_text = soup.get_text()

        # Common patterns for clearance rate
        patterns = [
            r'(\d+\.?\d*)%\s*clearance',
            r'clearance[:\s]+(\d+\.?\d*)%',
            r'(\d+\.?\d*)\s*%\s*(?:auction\s+)?clearance',
        ]

        for pattern in patterns:
            match = re.search(pattern, page_text, re.I)
            if match:
                return float(match.group(1))

        return None

    def _extract_property_results(
        self,
        soup: BeautifulSoup,
        suburb: str,
        postcode: str
    ) -> List[AuctionResult]:
        """Extract individual property auction results from page."""
        results = []

        # Look for property cards using common class patterns
        # Note: These may need adjustment based on actual site structure
        card_patterns = [
            {'class_': re.compile(r'property|listing|result|card', re.I)},
            {'class_': re.compile(r'auction', re.I)},
        ]

        cards = []
        for pattern in card_patterns:
            found = soup.find_all(['div', 'article', 'li'], **pattern)
            if found:
                cards = found
                break

        for card in cards:
            result = self._parse_property_card(card, suburb, postcode)
            if result and result.address:
                results.append(result)

        return results

    def _parse_property_card(self, card, suburb: str, postcode: str) -> Optional[AuctionResult]:
        """Parse a property card to extract auction data."""
        try:
            card_text = card.get_text(' ', strip=True)

            # Get address
            address = ""
            for tag in ['h2', 'h3', 'h4', 'a']:
                elem = card.find(tag, class_=re.compile(r'address', re.I))
                if elem:
                    address = elem.get_text(strip=True)
                    break
            if not address:
                elem = card.find(['h2', 'h3', 'h4'])
                if elem:
                    address = elem.get_text(strip=True)

            if not address or len(address) < 5:
                return None

            # Get price
            price = None
            price_undisclosed = False
            price_match = re.search(r'\$\s*([\d,]+)', card_text)
            if price_match:
                try:
                    price = int(price_match.group(1).replace(',', ''))
                except ValueError:
                    pass
            elif re.search(r'undisclosed|withheld|not\s+disclosed', card_text, re.I):
                price_undisclosed = True

            # Get outcome
            outcome = AuctionOutcome.UNKNOWN
            text_lower = card_text.lower()
            if 'sold prior' in text_lower:
                outcome = AuctionOutcome.SOLD_PRIOR
            elif 'sold after' in text_lower:
                outcome = AuctionOutcome.SOLD_AFTER
            elif 'passed in' in text_lower:
                outcome = AuctionOutcome.PASSED_IN
            elif 'withdrawn' in text_lower:
                outcome = AuctionOutcome.WITHDRAWN
            elif 'sold' in text_lower:
                outcome = AuctionOutcome.SOLD

            # Get features
            bedrooms = self._extract_number(card_text, r'(\d+)\s*(?:bed|br)')
            bathrooms = self._extract_number(card_text, r'(\d+)\s*(?:bath|ba)')
            parking = self._extract_number(card_text, r'(\d+)\s*(?:car|garage|parking)')

            # Get property type
            property_type = None
            if 'house' in text_lower:
                property_type = PropertyType.HOUSE
            elif 'unit' in text_lower:
                property_type = PropertyType.UNIT
            elif 'apartment' in text_lower:
                property_type = PropertyType.APARTMENT
            elif 'townhouse' in text_lower:
                property_type = PropertyType.TOWNHOUSE

            # Get agent
            agent = None
            agent_elem = card.find(class_=re.compile(r'agent|agency', re.I))
            if agent_elem:
                agent = agent_elem.get_text(strip=True)

            # Get listing URL
            listing_url = None
            link = card.find('a', href=True)
            if link:
                listing_url = urljoin(BASE_URL, link['href'])

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
                auction_date=self._get_week_ending(),
                listing_url=listing_url
            )

        except Exception as e:
            logger.debug(f"Could not parse card: {e}")
            return None

    def _extract_number(self, text: str, pattern: str) -> Optional[int]:
        """Extract a number from text using regex."""
        match = re.search(pattern, text, re.I)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                pass
        return None

    def _get_week_ending(self) -> date:
        """Get the Saturday date for the current auction week."""
        today = date.today()
        days_since_saturday = (today.weekday() + 2) % 7
        return today - timedelta(days=days_since_saturday)

    def scrape_my_suburbs(self) -> Tuple[List[SuburbSummary], List[AuctionResult]]:
        """
        Scrape auction results for YOUR tracked postcodes.

        This only fetches the suburbs you've configured in
        config/my_postcodes.py - nothing else.

        Returns:
            Tuple of (List[SuburbSummary], List[AuctionResult])
        """
        # Check configuration
        if not validate_config():
            logger.error("No postcodes configured. Edit config/my_postcodes.py first.")
            return [], []

        suburbs = get_tracked_suburbs()
        total = len(suburbs)

        logger.info(f"Starting weekly check for {total} suburb(s)")
        logger.info(f"This will take approximately {total * 15} seconds")

        all_summaries = []
        all_results = []

        for i, suburb in enumerate(suburbs, 1):
            logger.info(f"[{i}/{total}] Checking {suburb['suburb']} ({suburb['postcode']})")

            summary, results = self.fetch_suburb_results(suburb)

            if summary:
                all_summaries.append(summary)
                rate_str = f"{summary.clearance_rate}%" if summary.clearance_rate else "N/A"
                logger.info(f"  -> {summary.total_auctions} auctions, clearance: {rate_str}")

            if results:
                all_results.extend(results)

        # Summary
        logger.info("-" * 40)
        logger.info(f"Finished: {len(all_summaries)}/{total} suburbs had data")
        logger.info(f"Total individual results: {len(all_results)}")
        logger.info(f"Total page requests: {self._request_count}")

        return all_summaries, all_results


def create_scraper() -> AuctionScraper:
    """Create a scraper instance."""
    return AuctionScraper()


if __name__ == "__main__":
    # Test run
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    print("NSW Auction Results - Personal Tracker")
    print("=" * 40)

    if not validate_config():
        print("\nNo postcodes configured!")
        print("Edit config/my_postcodes.py to add your suburbs.")
        sys.exit(1)

    suburbs = get_tracked_suburbs()
    print(f"\nTracking {len(suburbs)} suburb(s):")
    for s in suburbs:
        print(f"  - {s['suburb']} ({s['postcode']})")

    print("\nStarting scrape...")
    scraper = AuctionScraper()
    summaries, results = scraper.scrape_my_suburbs()

    print(f"\nDone! Found {len(summaries)} suburb summaries, {len(results)} properties.")
