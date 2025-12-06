# NSW Auction Results - Personal Tracker

A personal tool to track weekly auction results for specific suburbs you're interested in from realestate.com.au.

## Overview

Every Saturday, realestate.com.au publishes auction results for NSW. This tool lets you track **only the suburbs you care about** - checking them once per week like a person casually browsing the site.

This is designed for genuine personal use:
- Track only YOUR chosen postcodes (not mass scraping)
- Human-like browsing behavior (8-20 second delays between pages)
- Once per week, Sunday mornings
- Respectful to the website

## Quick Start

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Configure your postcodes:**

Edit `config/my_postcodes.py`:
```python
TRACKED_POSTCODES = {
    "2021": "paddington",
    "2026": "bondi",
    "2065": "crows-nest",
    # Add your suburbs here
}
```

To find the correct format:
- Go to https://www.realestate.com.au/auction-results/nsw
- Click on your suburb
- Copy the suburb-postcode from URL: `/auction-results/nsw/paddington-2021`

3. **Check your configuration:**
```bash
python src/runner.py config
```

4. **Run your weekly check:**
```bash
python src/runner.py scrape
```

## Commands

```bash
python src/runner.py config    # Show your tracked postcodes
python src/runner.py scrape    # Run weekly check
python src/runner.py report    # View latest results
python src/runner.py weeks     # List collected weeks
```

## Scheduling Weekly Runs

**Using cron (Linux/Mac):**
```bash
# Install (runs Sundays at 6am)
./scripts/schedule_scraper.sh install

# Check status
./scripts/schedule_scraper.sh status

# Run manually
./scripts/schedule_scraper.sh run
```

## Project Structure

```
AlexanderRKO/
├── config/
│   ├── settings.py        # Rate limiting and general config
│   └── my_postcodes.py    # YOUR tracked suburbs (edit this!)
├── src/
│   ├── scraper.py         # Fetches auction data
│   ├── storage.py         # SQLite database
│   ├── aggregator.py      # Statistics
│   └── runner.py          # Main CLI
├── data/
│   └── processed/         # Weekly CSV exports
└── logs/                  # Activity logs
```

## Data Collected

For each suburb you track:
- Clearance rate percentage
- Number of auctions
- Individual property results (address, price, outcome)
- Property details (beds, baths, type)

All data is stored locally in SQLite (`data/auction_results.db`) and exported to CSV.

## Browsing Behavior

The scraper behaves like a person casually checking auction results:

- **8-20 seconds** between page loads (random, natural delays)
- **Occasional longer pauses** (like checking your phone)
- **Single browser session** per run
- **Only visits your tracked suburbs** - nothing else
- **Backs off significantly** if there are any issues

For 5 suburbs, a typical run takes 1-2 minutes.

## API Usage

```python
from src.storage import Database
from src.aggregator import AuctionAggregator
from datetime import date

db = Database()
aggregator = AuctionAggregator(db)

# Get data for a specific week
week = date(2024, 12, 7)
summaries = db.get_suburb_summaries_by_week(week)

for s in summaries:
    print(f"{s.suburb}: {s.clearance_rate}% ({s.total_auctions} auctions)")
```

## Troubleshooting

**No data returned?**
- The HTML structure may have changed - check `src/scraper.py`
- Try running at a different time
- Check `logs/scraper.log` for details

**Rate limited?**
- The scraper will automatically back off for 3 minutes
- You can increase delays in `config/settings.py`

## Ethics

This tool is for personal tracking of publicly available information. It:
- Only fetches suburbs you explicitly configure
- Uses long delays to minimize server impact
- Behaves like normal browsing activity
- Runs once per week maximum

Please use responsibly and respect the website's resources.
