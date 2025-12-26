"""
News Feed - Live news for portfolio holdings.

Fetches recent news and announcements for stocks in your portfolio.
Uses Yahoo Finance as the news source.
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

from .models import Portfolio
from .formatting import (
    bold, dim, cyan, yellow, green, red, blue,
    COLORS_ENABLED
)

logger = logging.getLogger(__name__)

# News settings
MAX_NEWS_AGE_DAYS = 30
NEWS_PER_STOCK = 3
REQUEST_TIMEOUT = 10


@dataclass
class NewsItem:
    """Represents a single news article."""
    title: str
    publisher: str
    link: str
    published: datetime
    stock_code: str
    summary: Optional[str] = None

    @property
    def age_days(self) -> int:
        """Days since publication."""
        return (datetime.now() - self.published).days

    @property
    def age_string(self) -> str:
        """Human-readable age."""
        days = self.age_days
        if days == 0:
            hours = (datetime.now() - self.published).seconds // 3600
            if hours == 0:
                return "Just now"
            return f"{hours}h ago"
        elif days == 1:
            return "Yesterday"
        elif days < 7:
            return f"{days}d ago"
        elif days < 14:
            return "1 week ago"
        else:
            return f"{days // 7} weeks ago"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "publisher": self.publisher,
            "link": self.link,
            "published": self.published.isoformat(),
            "stock_code": self.stock_code,
            "age_days": self.age_days,
        }


def fetch_stock_news(code: str, max_items: int = NEWS_PER_STOCK) -> List[NewsItem]:
    """
    Fetch news for a single stock from Yahoo Finance.

    Args:
        code: Stock code (without .AX suffix)
        max_items: Maximum news items to return

    Returns:
        List of NewsItem objects
    """
    news_items = []
    symbol = f"{code}.AX"

    try:
        # Yahoo Finance news endpoint
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        headers = {"User-Agent": "Mozilla/5.0"}

        # Try the news-specific endpoint
        news_url = f"https://query2.finance.yahoo.com/v1/finance/search?q={symbol}&newsCount={max_items}"

        response = requests.get(
            news_url,
            headers=headers,
            timeout=REQUEST_TIMEOUT
        )

        if response.status_code == 200:
            data = response.json()
            news_data = data.get("news", [])

            cutoff_date = datetime.now() - timedelta(days=MAX_NEWS_AGE_DAYS)

            for item in news_data[:max_items]:
                try:
                    # Parse publish time
                    pub_time = item.get("providerPublishTime", 0)
                    if pub_time:
                        published = datetime.fromtimestamp(pub_time)
                    else:
                        continue

                    # Skip old news
                    if published < cutoff_date:
                        continue

                    news_items.append(NewsItem(
                        title=item.get("title", ""),
                        publisher=item.get("publisher", "Unknown"),
                        link=item.get("link", ""),
                        published=published,
                        stock_code=code,
                        summary=item.get("summary"),
                    ))
                except Exception as e:
                    logger.debug(f"Error parsing news item for {code}: {e}")
                    continue

    except requests.exceptions.RequestException as e:
        logger.debug(f"Failed to fetch news for {code}: {e}")
    except Exception as e:
        logger.debug(f"Error fetching news for {code}: {e}")

    return news_items


def fetch_portfolio_news(
    portfolio: Portfolio,
    max_per_stock: int = NEWS_PER_STOCK,
    max_workers: int = 5,
) -> List[NewsItem]:
    """
    Fetch news for all holdings in portfolio.

    Args:
        portfolio: Portfolio to fetch news for
        max_per_stock: Max news items per stock
        max_workers: Concurrent fetch threads

    Returns:
        List of NewsItem sorted by date (newest first)
    """
    all_news = []
    codes = [h.code for h in portfolio.holdings]

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_code = {
            executor.submit(fetch_stock_news, code, max_per_stock): code
            for code in codes
        }

        for future in as_completed(future_to_code):
            code = future_to_code[future]
            try:
                news = future.result()
                all_news.extend(news)
            except Exception as e:
                logger.debug(f"Error fetching news for {code}: {e}")

    # Sort by date, newest first
    all_news.sort(key=lambda x: x.published, reverse=True)

    return all_news


def format_news_feed(
    news_items: List[NewsItem],
    portfolio: Optional[Portfolio] = None,
    max_items: int = 20,
) -> str:
    """
    Format news feed for terminal display.

    Clean, uncluttered layout with clear separation between items.
    """
    lines = []

    # Header
    if COLORS_ENABLED:
        lines.append("")
        lines.append(bold(cyan("  ╔════════════════════════════════════════════════════════════════╗")))
        lines.append(bold(cyan("  ║")) + bold("             PORTFOLIO NEWS FEED                       ") + bold(cyan("║")))
        lines.append(bold(cyan("  ╚════════════════════════════════════════════════════════════════╝")))
    else:
        lines.append("")
        lines.append("  ╔════════════════════════════════════════════════════════════════╗")
        lines.append("  ║             PORTFOLIO NEWS FEED                               ║")
        lines.append("  ╚════════════════════════════════════════════════════════════════╝")

    lines.append("")

    if not news_items:
        lines.append(dim("  No recent news found for your holdings."))
        lines.append(dim("  News is filtered to the last 30 days."))
        lines.append("")
        return "\n".join(lines)

    # Show count
    lines.append(dim(f"  Showing {min(len(news_items), max_items)} of {len(news_items)} articles (last 30 days)"))
    lines.append("")

    # Group by date for cleaner display
    current_date = None

    for i, item in enumerate(news_items[:max_items]):
        item_date = item.published.date()

        # Date separator
        if item_date != current_date:
            current_date = item_date
            if item.age_days == 0:
                date_str = "Today"
            elif item.age_days == 1:
                date_str = "Yesterday"
            else:
                date_str = item_date.strftime("%A, %d %b")

            if i > 0:
                lines.append("")
            lines.append(dim(f"  ── {date_str} ──────────────────────────────────────────────"))
            lines.append("")

        # Stock badge
        stock_badge = f"[{item.stock_code}]"
        if COLORS_ENABLED:
            stock_badge = cyan(stock_badge)

        # Title (truncate if too long)
        title = item.title
        if len(title) > 60:
            title = title[:57] + "..."

        # Time
        time_str = item.published.strftime("%H:%M")

        # Format the news item
        lines.append(f"  {stock_badge} {bold(title)}")
        lines.append(dim(f"      {item.publisher} · {time_str}"))
        lines.append("")

    # Footer
    if len(news_items) > max_items:
        remaining = len(news_items) - max_items
        lines.append(dim(f"  ... and {remaining} more articles"))
        lines.append("")

    # Tip
    lines.append(dim("  ─────────────────────────────────────────────────────────────────"))
    lines.append(dim("  Tip: Run 'news --code VHY' to filter by stock"))
    lines.append("")

    return "\n".join(lines)


def format_stock_news(
    code: str,
    news_items: List[NewsItem],
) -> str:
    """
    Format news for a single stock - detailed view.
    """
    lines = []

    # Header
    if COLORS_ENABLED:
        lines.append("")
        lines.append(bold(cyan(f"  ╔══════════════════════════════════════════════════════════════╗")))
        lines.append(bold(cyan(f"  ║")) + bold(f"  NEWS FOR {code.upper():<49}") + bold(cyan("║")))
        lines.append(bold(cyan(f"  ╚══════════════════════════════════════════════════════════════╝")))
    else:
        lines.append("")
        lines.append(f"  ╔══════════════════════════════════════════════════════════════╗")
        lines.append(f"  ║  NEWS FOR {code.upper():<49}║")
        lines.append(f"  ╚══════════════════════════════════════════════════════════════╝")

    lines.append("")

    # Filter to this stock
    stock_news = [n for n in news_items if n.stock_code.upper() == code.upper()]

    if not stock_news:
        lines.append(dim(f"  No recent news found for {code}."))
        lines.append("")
        return "\n".join(lines)

    for item in stock_news:
        lines.append(f"  {bold(item.title)}")
        lines.append(dim(f"  {item.publisher} · {item.age_string}"))
        if item.summary:
            # Wrap summary
            summary = item.summary[:200] + "..." if len(item.summary) > 200 else item.summary
            lines.append(f"  {summary}")
        lines.append(dim(f"  {item.link}"))
        lines.append("")

    return "\n".join(lines)


def get_news_summary(portfolio: Portfolio) -> Dict[str, Any]:
    """
    Get a summary of news activity for the portfolio.

    Returns:
        Dictionary with news statistics
    """
    news = fetch_portfolio_news(portfolio)

    # Count by stock
    by_stock = {}
    for item in news:
        if item.stock_code not in by_stock:
            by_stock[item.stock_code] = 0
        by_stock[item.stock_code] += 1

    # Most active
    most_active = sorted(by_stock.items(), key=lambda x: x[1], reverse=True)[:5]

    # Recent (last 7 days)
    recent = [n for n in news if n.age_days <= 7]

    return {
        "total_articles": len(news),
        "stocks_with_news": len(by_stock),
        "recent_count": len(recent),
        "most_active": most_active,
        "latest": news[0].to_dict() if news else None,
    }
