"""
Base scraper class with common functionality.
"""

import random
import time
import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..config import (
    USER_AGENTS,
    REQUEST_TIMEOUT,
    REQUEST_DELAY_MIN,
    REQUEST_DELAY_MAX,
    MAX_RETRIES,
    ScraperConfig,
)
from ..models import AuctionResult

logger = logging.getLogger(__name__)


class ScraperError(Exception):
    """Custom exception for scraper errors."""
    pass


class RateLimiter:
    """Simple rate limiter to avoid overwhelming servers."""

    def __init__(self, min_delay: float = 2.0, max_delay: float = 5.0):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.last_request_time: Optional[float] = None

    def wait(self):
        """Wait appropriate amount of time before next request."""
        if self.last_request_time is not None:
            elapsed = time.time() - self.last_request_time
            delay = random.uniform(self.min_delay, self.max_delay)
            if elapsed < delay:
                sleep_time = delay - elapsed
                logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f}s")
                time.sleep(sleep_time)

        self.last_request_time = time.time()


class BaseScraper(ABC):
    """
    Abstract base class for web scrapers.
    Provides common functionality like session management, rate limiting, and retries.
    """

    def __init__(self, config: Optional[ScraperConfig] = None):
        self.config = config or ScraperConfig()
        self.session: Optional[requests.Session] = None
        self.rate_limiter = RateLimiter(
            min_delay=self.config.delay_min,
            max_delay=self.config.delay_max,
        )
        self._setup_logging()

    def _setup_logging(self):
        """Configure logging for the scraper."""
        self.logger = logging.getLogger(self.__class__.__name__)

    def _get_session(self) -> requests.Session:
        """Get or create a requests session with retry logic."""
        if self.session is None:
            self.session = requests.Session()

            # Configure retries
            retry_strategy = Retry(
                total=self.config.max_retries,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            self.session.mount("http://", adapter)
            self.session.mount("https://", adapter)

            # Set default headers
            self.session.headers.update(self._get_headers())

        return self.session

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for requests with rotated user agent."""
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-AU,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0",
        }

    def fetch_page(self, url: str) -> str:
        """
        Fetch a page with rate limiting and error handling.

        Args:
            url: URL to fetch

        Returns:
            HTML content of the page

        Raises:
            ScraperError: If the page cannot be fetched
        """
        self.rate_limiter.wait()
        session = self._get_session()

        # Rotate user agent for each request
        session.headers["User-Agent"] = random.choice(USER_AGENTS)

        try:
            self.logger.info(f"Fetching: {url}")
            response = session.get(url, timeout=self.config.timeout)
            response.raise_for_status()
            return response.text

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                raise ScraperError(
                    f"Access forbidden (403) - Site may be blocking requests: {url}"
                )
            elif e.response.status_code == 404:
                raise ScraperError(f"Page not found (404): {url}")
            else:
                raise ScraperError(f"HTTP error {e.response.status_code}: {url}")

        except requests.exceptions.Timeout:
            raise ScraperError(f"Request timed out: {url}")

        except requests.exceptions.RequestException as e:
            raise ScraperError(f"Request failed: {e}")

    def fetch_json(self, url: str) -> Dict[str, Any]:
        """
        Fetch JSON data from a URL.

        Args:
            url: URL to fetch

        Returns:
            Parsed JSON data

        Raises:
            ScraperError: If the request fails or response isn't valid JSON
        """
        self.rate_limiter.wait()
        session = self._get_session()
        session.headers["Accept"] = "application/json"

        try:
            self.logger.info(f"Fetching JSON: {url}")
            response = session.get(url, timeout=self.config.timeout)
            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            raise ScraperError(f"Request failed: {e}")
        except ValueError as e:
            raise ScraperError(f"Invalid JSON response: {e}")

    @abstractmethod
    def scrape_auction_results(self, **kwargs) -> List[AuctionResult]:
        """
        Scrape auction results. Must be implemented by subclasses.

        Returns:
            List of AuctionResult objects
        """
        pass

    def close(self):
        """Clean up resources."""
        if self.session:
            self.session.close()
            self.session = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
