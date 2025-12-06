"""
Scraper for realestate.com.au auction results.

This module provides multiple strategies for collecting auction data:
1. HTML parsing with BeautifulSoup
2. JSON extraction from embedded page data
3. Browser-based scraping with Selenium (for JavaScript-rendered content)

IMPORTANT: This scraper is for personal/research use. Please respect:
- robots.txt directives
- Rate limiting to avoid server overload
- Terms of service considerations
"""

import re
import json
import logging
from datetime import date, datetime
from typing import List, Optional, Dict, Any, Generator
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .base import BaseScraper, ScraperError
from ..config import (
    BASE_URL,
    AUCTION_RESULTS_URL,
    NSW_REGIONS,
    ScraperConfig,
)
from ..models import AuctionResult, AuctionOutcome, PropertyType

logger = logging.getLogger(__name__)


class RealEstateAuctionScraper(BaseScraper):
    """
    Scraper for realestate.com.au auction results.

    Usage:
        with RealEstateAuctionScraper() as scraper:
            results = scraper.scrape_auction_results()
            for result in results:
                print(result.address, result.sold_price)
    """

    def __init__(self, config: Optional[ScraperConfig] = None):
        super().__init__(config)
        self.base_url = BASE_URL
        self.auction_url = AUCTION_RESULTS_URL

    def get_suburb_urls(self, state: str = "nsw") -> List[str]:
        """
        Get list of suburb-specific auction result URLs.

        The main auction results page lists all suburbs with results.
        This method extracts those suburb links.

        Args:
            state: State code (default: nsw)

        Returns:
            List of suburb auction result URLs
        """
        main_url = f"{self.base_url}/auction-results/{state}"
        suburb_urls = []

        try:
            html = self.fetch_page(main_url)
            soup = BeautifulSoup(html, "html.parser")

            # Look for suburb links in the auction results page
            # Pattern: /auction-results/nsw/suburb-name-postcode
            link_pattern = re.compile(rf"/auction-results/{state}/[\w-]+-\d{{4}}")

            for link in soup.find_all("a", href=True):
                href = link["href"]
                if link_pattern.match(href):
                    full_url = urljoin(self.base_url, href)
                    if full_url not in suburb_urls:
                        suburb_urls.append(full_url)

            self.logger.info(f"Found {len(suburb_urls)} suburb URLs")
            return suburb_urls

        except ScraperError as e:
            self.logger.error(f"Failed to get suburb URLs: {e}")
            return []

    def _extract_json_data(self, html: str) -> Optional[Dict[str, Any]]:
        """
        Extract JSON data embedded in the page.

        realestate.com.au often includes structured data in script tags
        that can be easier to parse than HTML.

        Args:
            html: Page HTML content

        Returns:
            Extracted JSON data or None
        """
        soup = BeautifulSoup(html, "html.parser")

        # Look for JSON-LD structured data
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
                if isinstance(data, dict):
                    return data
            except (json.JSONDecodeError, TypeError):
                continue

        # Look for embedded JavaScript data
        # Pattern: window.__INITIAL_STATE__ = {...}
        for script in soup.find_all("script"):
            if script.string:
                patterns = [
                    r"window\.__INITIAL_STATE__\s*=\s*({.+?});",
                    r"window\.__DATA__\s*=\s*({.+?});",
                    r'"auctionResults"\s*:\s*(\[.+?\])',
                ]
                for pattern in patterns:
                    match = re.search(pattern, script.string, re.DOTALL)
                    if match:
                        try:
                            return json.loads(match.group(1))
                        except json.JSONDecodeError:
                            continue

        return None

    def _parse_price(self, price_text: str) -> Optional[int]:
        """
        Parse price from text like "$1,250,000" or "$1.25M".

        Args:
            price_text: Price string

        Returns:
            Price as integer or None
        """
        if not price_text:
            return None

        # Remove common prefixes/suffixes
        text = price_text.strip().upper()
        text = re.sub(r"[^\d.MK]", "", text)

        if not text:
            return None

        try:
            # Handle M (millions) and K (thousands) suffixes
            if "M" in text:
                return int(float(text.replace("M", "")) * 1_000_000)
            elif "K" in text:
                return int(float(text.replace("K", "")) * 1_000)
            else:
                return int(float(text))
        except ValueError:
            return None

    def _parse_auction_row(
        self, row_element, suburb: str = "", postcode: str = ""
    ) -> Optional[AuctionResult]:
        """
        Parse a single auction result row from HTML.

        Args:
            row_element: BeautifulSoup element containing auction data
            suburb: Suburb name (from page context)
            postcode: Postcode (from page context)

        Returns:
            AuctionResult or None if parsing fails
        """
        try:
            result = AuctionResult(suburb=suburb, postcode=postcode)

            # Address
            address_elem = row_element.select_one(
                ".property-address, .address, [data-testid='address']"
            )
            if address_elem:
                result.address = address_elem.get_text(strip=True)

            # Price
            price_elem = row_element.select_one(
                ".property-price, .price, [data-testid='price']"
            )
            if price_elem:
                result.sold_price = self._parse_price(price_elem.get_text())

            # Outcome/Result
            result_elem = row_element.select_one(
                ".auction-result, .result, [data-testid='result']"
            )
            if result_elem:
                result.outcome = AuctionOutcome.from_string(result_elem.get_text())

            # Property features (beds, baths, parking)
            features = row_element.select(".property-feature, .feature")
            for feature in features:
                text = feature.get_text(strip=True).lower()
                value_match = re.search(r"(\d+)", text)
                if value_match:
                    value = int(value_match.group(1))
                    if "bed" in text:
                        result.bedrooms = value
                    elif "bath" in text:
                        result.bathrooms = value
                    elif "car" in text or "park" in text:
                        result.parking = value

            # Property type
            type_elem = row_element.select_one(".property-type, .type")
            if type_elem:
                result.property_type = PropertyType.from_string(type_elem.get_text())

            # Agent/Agency
            agent_elem = row_element.select_one(".agent-name, .agent")
            if agent_elem:
                result.agent_name = agent_elem.get_text(strip=True)

            agency_elem = row_element.select_one(".agency-name, .agency")
            if agency_elem:
                result.agency_name = agency_elem.get_text(strip=True)

            # Link to listing
            link_elem = row_element.select_one("a[href*='/property']")
            if link_elem and link_elem.get("href"):
                result.source_url = urljoin(self.base_url, link_elem["href"])

            # Only return if we have meaningful data
            if result.address or result.sold_price:
                return result

            return None

        except Exception as e:
            self.logger.warning(f"Failed to parse auction row: {e}")
            return None

    def _extract_suburb_postcode_from_url(self, url: str) -> tuple:
        """
        Extract suburb name and postcode from URL.

        URL pattern: /auction-results/nsw/suburb-name-2000

        Args:
            url: Suburb auction results URL

        Returns:
            Tuple of (suburb, postcode)
        """
        path = urlparse(url).path
        match = re.search(r"/([a-z-]+)-(\d{4})/?$", path)
        if match:
            suburb = match.group(1).replace("-", " ").title()
            postcode = match.group(2)
            return suburb, postcode
        return "", ""

    def scrape_suburb_page(self, url: str) -> List[AuctionResult]:
        """
        Scrape auction results from a suburb-specific page.

        Args:
            url: Suburb auction results URL

        Returns:
            List of AuctionResult objects
        """
        results = []
        suburb, postcode = self._extract_suburb_postcode_from_url(url)

        try:
            html = self.fetch_page(url)

            # First try to extract JSON data
            json_data = self._extract_json_data(html)
            if json_data and "results" in json_data:
                for item in json_data.get("results", []):
                    result = self._parse_json_result(item)
                    if result:
                        result.suburb = suburb
                        result.postcode = postcode
                        results.append(result)
                return results

            # Fall back to HTML parsing
            soup = BeautifulSoup(html, "html.parser")

            # Look for auction result rows
            # Common selectors for auction result items
            row_selectors = [
                ".auction-result-item",
                ".property-card",
                "[data-testid='auction-result']",
                ".results-list > div",
                "table.auction-results tbody tr",
            ]

            for selector in row_selectors:
                rows = soup.select(selector)
                if rows:
                    self.logger.debug(
                        f"Found {len(rows)} results with selector: {selector}"
                    )
                    for row in rows:
                        result = self._parse_auction_row(row, suburb, postcode)
                        if result:
                            results.append(result)
                    break

            self.logger.info(
                f"Scraped {len(results)} results from {suburb} {postcode}"
            )
            return results

        except ScraperError as e:
            self.logger.error(f"Failed to scrape {url}: {e}")
            return []

    def _parse_json_result(self, data: Dict[str, Any]) -> Optional[AuctionResult]:
        """
        Parse an auction result from JSON data.

        Args:
            data: JSON data for a single result

        Returns:
            AuctionResult or None
        """
        try:
            result = AuctionResult()

            # Map JSON fields to model
            result.address = data.get("address", "")

            # Location
            if "suburb" in data:
                result.suburb = data["suburb"]
            if "postcode" in data:
                result.postcode = str(data["postcode"])

            # Property details
            if "propertyType" in data:
                result.property_type = PropertyType.from_string(data["propertyType"])
            if "bedrooms" in data:
                result.bedrooms = int(data["bedrooms"])
            if "bathrooms" in data:
                result.bathrooms = int(data["bathrooms"])
            if "carSpaces" in data:
                result.parking = int(data["carSpaces"])

            # Prices
            if "price" in data:
                result.sold_price = self._parse_price(str(data["price"]))
            elif "soldPrice" in data:
                result.sold_price = self._parse_price(str(data["soldPrice"]))

            # Outcome
            if "result" in data:
                result.outcome = AuctionOutcome.from_string(data["result"])
            elif "auctionResult" in data:
                result.outcome = AuctionOutcome.from_string(data["auctionResult"])

            # Date
            if "auctionDate" in data:
                try:
                    result.auction_date = date.fromisoformat(data["auctionDate"])
                except ValueError:
                    pass

            # Agent
            if "agent" in data:
                result.agent_name = data["agent"]
            if "agency" in data:
                result.agency_name = data["agency"]

            # URL
            if "url" in data:
                result.source_url = urljoin(self.base_url, data["url"])

            return result if result.address else None

        except Exception as e:
            self.logger.warning(f"Failed to parse JSON result: {e}")
            return None

    def scrape_main_page(self) -> Dict[str, Any]:
        """
        Scrape the main NSW auction results page for summary data.

        Returns:
            Dictionary with summary statistics and suburb links
        """
        try:
            html = self.fetch_page(self.auction_url)
            soup = BeautifulSoup(html, "html.parser")

            summary = {
                "date": date.today().isoformat(),
                "state": "NSW",
                "suburbs": [],
                "total_auctions": 0,
                "clearance_rate": None,
            }

            # Extract overall stats if available
            stats_elem = soup.select_one(".clearance-rate, .summary-stats")
            if stats_elem:
                rate_match = re.search(r"(\d+(?:\.\d+)?)\s*%", stats_elem.get_text())
                if rate_match:
                    summary["clearance_rate"] = float(rate_match.group(1))

            # Get suburb links
            summary["suburbs"] = self.get_suburb_urls("nsw")

            return summary

        except ScraperError as e:
            self.logger.error(f"Failed to scrape main page: {e}")
            return {"error": str(e)}

    def scrape_auction_results(
        self,
        suburbs: Optional[List[str]] = None,
        max_suburbs: Optional[int] = None,
    ) -> List[AuctionResult]:
        """
        Scrape auction results for NSW suburbs.

        Args:
            suburbs: Optional list of suburb URLs to scrape.
                     If None, all suburbs will be discovered and scraped.
            max_suburbs: Optional limit on number of suburbs to scrape.

        Returns:
            List of AuctionResult objects
        """
        all_results: List[AuctionResult] = []

        # Get suburb URLs if not provided
        if suburbs is None:
            suburbs = self.get_suburb_urls("nsw")

        if max_suburbs:
            suburbs = suburbs[:max_suburbs]

        self.logger.info(f"Scraping {len(suburbs)} suburbs...")

        for i, suburb_url in enumerate(suburbs, 1):
            self.logger.info(f"Progress: {i}/{len(suburbs)} - {suburb_url}")

            results = self.scrape_suburb_page(suburb_url)
            all_results.extend(results)

            # Log progress periodically
            if i % 10 == 0:
                self.logger.info(
                    f"Collected {len(all_results)} results from {i} suburbs"
                )

        self.logger.info(
            f"Completed: {len(all_results)} total results from {len(suburbs)} suburbs"
        )
        return all_results

    def scrape_results_generator(
        self, suburbs: Optional[List[str]] = None
    ) -> Generator[AuctionResult, None, None]:
        """
        Generator version of scrape_auction_results for memory efficiency.

        Yields results one at a time instead of building a full list.

        Args:
            suburbs: Optional list of suburb URLs to scrape

        Yields:
            AuctionResult objects
        """
        if suburbs is None:
            suburbs = self.get_suburb_urls("nsw")

        for suburb_url in suburbs:
            results = self.scrape_suburb_page(suburb_url)
            for result in results:
                yield result


class SeleniumAuctionScraper(RealEstateAuctionScraper):
    """
    Selenium-based scraper for JavaScript-rendered content.

    Use this when the regular scraper fails due to JavaScript rendering.

    Requires: selenium, webdriver-manager

    Usage:
        with SeleniumAuctionScraper() as scraper:
            results = scraper.scrape_auction_results()
    """

    def __init__(self, config: Optional[ScraperConfig] = None):
        super().__init__(config)
        self.driver = None

    def _get_driver(self):
        """Initialize Selenium WebDriver."""
        if self.driver is None:
            try:
                from selenium import webdriver
                from selenium.webdriver.chrome.options import Options
                from selenium.webdriver.chrome.service import Service
                from webdriver_manager.chrome import ChromeDriverManager

                options = Options()
                if self.config.headless:
                    options.add_argument("--headless")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
                options.add_argument(f"user-agent={self._get_headers()['User-Agent']}")

                service = Service(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=options)
                self.driver.set_page_load_timeout(self.config.timeout)

            except ImportError:
                raise ScraperError(
                    "Selenium not installed. Run: pip install selenium webdriver-manager"
                )

        return self.driver

    def fetch_page(self, url: str) -> str:
        """Fetch page using Selenium for JavaScript rendering."""
        import time

        self.rate_limiter.wait()
        driver = self._get_driver()

        try:
            self.logger.info(f"Fetching (Selenium): {url}")
            driver.get(url)
            time.sleep(2)  # Wait for JavaScript to render
            return driver.page_source

        except Exception as e:
            raise ScraperError(f"Selenium fetch failed: {e}")

    def close(self):
        """Clean up Selenium driver."""
        super().close()
        if self.driver:
            self.driver.quit()
            self.driver = None
