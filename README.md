# NSW Auction Results Tracker

A Python framework for collecting, storing, and analyzing weekly auction results from realestate.com.au for NSW suburbs.

## Features

- **Postcode-Focused Collection**: Track up to 10 specific postcodes (API-friendly approach)
- **SQLite Storage**: Persistent storage with full history tracking
- **Weekly Scheduling**: Automated collection every Sunday (after 5am refresh)
- **Data Analysis**: Clearance rates, price statistics, suburb comparisons
- **Multiple Export Formats**: CSV, Excel, JSON
- **Respectful Scraping**: Conservative rate limiting (5-10s delays) to avoid server overload

## Project Structure

```
nsw_auction_tracker/
├── __init__.py
├── __main__.py
├── config.py              # Configuration settings
├── main.py                # CLI entry point
├── models/
│   ├── __init__.py
│   └── auction.py         # Data models (AuctionResult, SuburbSummary)
├── scrapers/
│   ├── __init__.py
│   ├── base.py            # Base scraper with rate limiting
│   └── realestate_scraper.py  # Main scraper implementation
├── storage/
│   ├── __init__.py
│   └── database.py        # SQLite storage layer
├── aggregator/
│   ├── __init__.py
│   └── analysis.py        # Statistics and reporting
└── scheduler/
    ├── __init__.py
    └── weekly_job.py      # Scheduling utilities
```

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd AlexanderRKO

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

### Quick Start (Recommended: Postcode-Based)

```bash
# 1. Configure your preferred postcodes in config.py
#    OR pass them directly via command line

# Collect data for specific postcodes (RECOMMENDED - API friendly)
python -m nsw_auction_tracker collect --postcodes 2021,2026,2042

# View statistics
python -m nsw_auction_tracker stats

# Analyze current week
python -m nsw_auction_tracker analyze

# Export to CSV
python -m nsw_auction_tracker export --format csv
```

### Configure Preferred Postcodes

Edit `nsw_auction_tracker/config.py` to set your preferred postcodes:

```python
PREFERRED_POSTCODES = [
    "2021",  # Paddington
    "2026",  # Bondi
    "2042",  # Newtown
    "2060",  # North Sydney
    "2095",  # Manly
    # Add up to 10 postcodes
]
```

Then simply run:
```bash
python -m nsw_auction_tracker collect  # Uses your configured postcodes
```

### Commands

| Command | Description |
|---------|-------------|
| `collect` | Run data collection |
| `analyze` | Analyze collected data |
| `export` | Export data to file |
| `stats` | Show database statistics |
| `suburbs` | List available suburb URLs |
| `test` | Test scraping a single URL |
| `setup` | Show scheduling options |

### Collection Options

```bash
# RECOMMENDED: Collect specific postcodes (API-friendly, max 10)
python -m nsw_auction_tracker collect --postcodes 2021,2026,2042,2060,2095

# Use postcodes from config.py
python -m nsw_auction_tracker collect

# Fallback: Limited collection by suburb count (if no postcodes)
python -m nsw_auction_tracker collect --max-suburbs 10

# Verbose output
python -m nsw_auction_tracker -v collect
```

**Why limit to postcodes?**
- Respects the website's servers (only 10 requests vs 1000+)
- Faster collection (minutes instead of hours)
- Focus on areas you actually care about
- More reliable (less chance of being blocked)

### Analysis Options

```bash
# Analyze current week
python -m nsw_auction_tracker analyze

# Analyze specific week
python -m nsw_auction_tracker analyze --week 2024-W49

# Save analysis report
python -m nsw_auction_tracker analyze --week 2024-W49 --save
```

### Export Options

```bash
# Export specific week to CSV
python -m nsw_auction_tracker export --week 2024-W49 --format csv

# Export all data to Excel
python -m nsw_auction_tracker export --format excel

# Export to specific location
python -m nsw_auction_tracker export --output /path/to/output
```

## Scheduling Weekly Collection

### Option 1: Cron Job (Linux/Mac)

```bash
# View cron command
python -m nsw_auction_tracker setup

# Add to crontab
crontab -e
# Add line: 0 6 * * 0 cd /path/to/project && python -m nsw_auction_tracker collect
```

### Option 2: GitHub Actions

Create `.github/workflows/collect.yml`:

```bash
python -m nsw_auction_tracker setup --github-actions
```

### Option 3: Python Scheduler

```python
from nsw_auction_tracker.scheduler import WeeklyCollector

collector = WeeklyCollector()
collector.schedule_weekly(day="sunday", time="06:00")
```

## Data Model

### AuctionResult

| Field | Type | Description |
|-------|------|-------------|
| `address` | str | Property address |
| `suburb` | str | Suburb name |
| `postcode` | str | Postcode |
| `property_type` | enum | house, unit, apartment, etc. |
| `bedrooms` | int | Number of bedrooms |
| `auction_date` | date | Date of auction |
| `outcome` | enum | sold_at_auction, passed_in, etc. |
| `sold_price` | int | Sale price (if sold) |
| `agent_name` | str | Agent name |
| `agency_name` | str | Agency name |
| `source_url` | str | Listing URL |
| `collection_week` | str | Week identifier (2024-W49) |

### Outcome Types

- `sold_at_auction` - Sold under the hammer
- `sold_before_auction` - Sold prior to auction
- `sold_after_auction` - Sold after passing in
- `passed_in` - Did not meet reserve
- `passed_in_vendor_bid` - Passed in on vendor bid
- `withdrawn` - Withdrawn from auction
- `postponed` - Postponed to later date

## Analysis Features

```python
from nsw_auction_tracker.aggregator import AuctionAnalyzer

# Load results
analyzer = AuctionAnalyzer(results)

# Get statistics
clearance_rate = analyzer.get_clearance_rate()  # e.g., 72.5%
price_stats = analyzer.get_price_stats()        # median, avg, min, max

# Group by suburb
by_suburb = analyzer.group_by_suburb()

# Top suburbs
top_by_price = analyzer.get_top_suburbs_by_price(n=10)
top_by_volume = analyzer.get_top_suburbs_by_volume(n=10)

# Price distribution
brackets = analyzer.get_price_brackets()
```

## Important Notes

### Terms of Service

This tool is for personal/research use. Please review realestate.com.au's terms of service before use:

> "In accessing or using our Websites you agree that you will not use any automated device, software, process or means to access, retrieve, scrape, or index our Websites."

### Rate Limiting

The scraper includes built-in rate limiting (2-5 seconds between requests) to avoid overloading servers. Please respect these limits.

### Anti-Bot Protection

realestate.com.au has anti-scraping measures. If you encounter 403 errors:

1. Increase delays between requests
2. Try the Selenium-based scraper for JavaScript rendering
3. Consider using a proxy service

## Development

```bash
# Run tests
pytest tests/ -v

# Type checking
mypy nsw_auction_tracker/

# Code formatting
black nsw_auction_tracker/

# Linting
flake8 nsw_auction_tracker/
```

## License

This project is for educational and personal research purposes.
