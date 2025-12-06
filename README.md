# NSW Auction Results Scraper

A Python framework for collecting and analyzing weekly auction results from realestate.com.au for New South Wales suburbs.

## Overview

Every Saturday, realestate.com.au publishes auction results for NSW, updating them Sunday morning at 5am AEDT. This framework automates the collection, storage, and analysis of this data across thousands of Sydney and regional NSW postcodes.

## Features

- **Automated Weekly Collection**: Scrapes auction results from all NSW suburbs
- **Historical Database**: SQLite storage for tracking trends over time
- **CSV Exports**: Weekly data exports for external analysis
- **Regional Aggregation**: Pre-calculated summaries by region (Sydney Inner, North Shore, etc.)
- **Trend Analysis**: Track clearance rates and median prices over time
- **Flexible Scheduling**: Cron jobs or GitHub Actions for automation

## Project Structure

```
AlexanderRKO/
├── config/
│   └── settings.py        # Configuration and NSW region definitions
├── src/
│   ├── models.py          # Data models (AuctionResult, SuburbSummary, etc.)
│   ├── scraper.py         # Web scraping logic
│   ├── storage.py         # Database and CSV export
│   ├── aggregator.py      # Statistics and trend analysis
│   └── runner.py          # Main entry point
├── scripts/
│   └── schedule_scraper.sh  # Cron job management
├── data/
│   ├── raw/               # Raw scraped data
│   ├── processed/         # Weekly CSV exports and reports
│   └── archive/           # Historical archives
├── logs/                  # Scraper logs
├── tests/                 # Unit tests
└── .github/workflows/     # GitHub Actions for automated runs
```

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/AlexanderRKO.git
cd AlexanderRKO
```

2. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Run a Manual Scrape

```bash
# Full scrape of all suburbs
python src/runner.py scrape

# Test with limited suburbs
python src/runner.py scrape --limit 10

# Skip CSV export
python src/runner.py scrape --no-csv
```

### View Reports

```bash
# View the latest weekly report
python src/runner.py report

# View a specific week
python src/runner.py report --week 2024-12-07

# List all available weeks
python src/runner.py weeks
```

### Schedule Weekly Runs

**Using cron (Linux/Mac):**
```bash
# Install the cron job (runs Sundays at 6am)
./scripts/schedule_scraper.sh install

# Check status
./scripts/schedule_scraper.sh status

# Remove the cron job
./scripts/schedule_scraper.sh remove
```

**Using GitHub Actions:**

The included workflow runs automatically every Sunday. You can also trigger it manually from the GitHub Actions tab.

## Data Collected

### Individual Auction Results
- Property address and suburb
- Postcode and region
- Property type (house, unit, apartment, etc.)
- Bedrooms, bathrooms, parking
- Sale price (if disclosed)
- Outcome (sold, passed in, withdrawn, etc.)
- Real estate agent

### Suburb Summaries
- Total auctions and sales
- Clearance rate percentage
- Median sale price
- Regional classification

### Regional Aggregations
- Sydney Inner, East, North, South, West, Southwest
- Northern Beaches
- Central Coast
- Newcastle
- Wollongong
- Regional NSW

## Configuration

Edit `config/settings.py` to customize:

```python
# Rate limiting (be respectful to the server)
REQUEST_DELAY_MIN = 2  # Seconds between requests
REQUEST_DELAY_MAX = 5

# Schedule settings
SCHEDULE_DAY = "sunday"
SCHEDULE_TIME = "06:00"

# Add custom regions
NSW_REGIONS = {
    "sydney_inner": ["2000", "2010", ...],
    # Add your own groupings
}
```

## API Usage

```python
from src.storage import Database
from src.aggregator import AuctionAggregator
from datetime import date

# Initialize
db = Database()
aggregator = AuctionAggregator(db)

# Get weekly data
week = date(2024, 12, 7)
summaries = db.get_suburb_summaries_by_week(week)

# Get clearance rate trend
trend = aggregator.get_clearance_rate_trend(weeks=12)
for week_date, rate in trend:
    print(f"{week_date}: {rate}%")

# Compare regions
regions = aggregator.compare_regions(week)
for r in regions:
    print(f"{r.region}: {r.clearance_rate}% ({r.total_auctions} auctions)")

# Get top suburbs
top = aggregator.get_top_suburbs(week, metric='clearance_rate', limit=10)
```

## Troubleshooting

### Website Blocking

If the website blocks requests:

1. Try using Selenium for JavaScript rendering:
```bash
pip install selenium webdriver-manager
python src/runner.py scrape --selenium
```

2. Adjust rate limiting in `config/settings.py`:
```python
REQUEST_DELAY_MIN = 5
REQUEST_DELAY_MAX = 10
```

### No Data Returned

The website structure may have changed. Check the scraper's HTML parsing in `src/scraper.py`:
- `get_suburb_list()` - Extracts suburb links from main page
- `_parse_property_card()` - Extracts data from individual listings

## Legal & Ethical Considerations

- This tool is for personal/research use
- Respect the website's terms of service
- Use appropriate rate limiting to avoid overloading servers
- Data collected is publicly available information

## Contributing

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## License

MIT License - see LICENSE file for details
