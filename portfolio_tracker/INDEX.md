# Portfolio Tracker for CommSec CSV Exports

A comprehensive command-line portfolio management tool for Australian investors using CommSec.

---

## Quick Start

```bash
# Import your CommSec CSV export
python -m portfolio_tracker import portfolio.csv

# View your portfolio
python -m portfolio_tracker view --dashboard

# Get quick status
python -m portfolio_tracker status
```

---

## Feature Index

### Core Features (1-5)

| # | Feature | Command | Description |
|---|---------|---------|-------------|
| 1 | **CSV Import** | `import <file.csv>` | Parse and store CommSec portfolio exports |
| 2 | **Portfolio View** | `view` | Display holdings with P/L, weights, sectors |
| 3 | **Analysis** | `analyze` | Performance metrics, concentration risk, rebalancing suggestions |
| 4 | **Query/Filter** | `query` | Filter holdings by value, return %, asset class |
| 5 | **Storage** | `stats` | SQLite database with snapshot history |

### Market Data (6-8)

| # | Feature | Command | Description |
|---|---------|---------|-------------|
| 6 | **Live Prices** | `update` | Fetch real-time ASX prices via Yahoo Finance |
| 7 | **Stock Quotes** | `quote <CODE>` | Get live quote for any ASX stock |
| 8 | **News Feed** | `news` | Latest news for your holdings |

### Sector & Classification (9-10)

| # | Feature | Command | Description |
|---|---------|---------|-------------|
| 9 | **Sector Lookup** | `sectors` | GICS sector classification for 200+ ASX stocks |
| 10 | **Reclassify** | `sectors --reclassify` | Auto-classify all holdings |

### Income & Dividends (11-12)

| # | Feature | Command | Description |
|---|---------|---------|-------------|
| 11 | **Dividend Tracking** | `dividends` | Yield analysis, upcoming ex-dates |
| 12 | **Income Projection** | `dividends --projection` | 12-month dividend forecast |

### Alerts & Monitoring (13)

| # | Feature | Command | Description |
|---|---------|---------|-------------|
| 13 | **Price Alerts** | `alerts` | Set alerts for price, value, P/L thresholds |

### Visualization (14)

| # | Feature | Command | Description |
|---|---------|---------|-------------|
| 14 | **Visualization Export** | `viz` | Export to SankeyMATIC, Flourish, Plotly, Claude Artifacts, Markdown |

### Cashflow & Forecasting (15)

| # | Feature | Command | Description |
|---|---------|---------|-------------|
| 15 | **Cashflow Forecast** | `cashflow` | Dividend calendar, DRP simulation, income projections |

### Portfolio Analysis (16)

| # | Feature | Command | Description |
|---|---------|---------|-------------|
| 16 | **Portfolio Profile** | `profile` | Analyze risk profile (Conservative/Balanced/Growth/Aggressive) |

### Transaction Management (17)

| # | Feature | Command | Description |
|---|---------|---------|-------------|
| 17 | **Transaction Log** | `transactions` / `tx` | Record BUY/SELL/DIVIDEND, CGT calculations, realized gains |

### Goal Tracking (18)

| # | Feature | Command | Description |
|---|---------|---------|-------------|
| 18 | **Goal Tracker** | `goals` | Set and track portfolio value, income, share count targets |

### Investor Profile (19)

| # | Feature | Command | Description |
|---|---------|---------|-------------|
| 19 | **Investor Profile** | `investor` | 10-question risk assessment, retirement timeline, allocation recommendations |

### Tax & Reporting (20-22)

| # | Feature | Command | Description |
|---|---------|---------|-------------|
| 20 | **Tax Report** | `tax` | CGT analysis, unrealized gains, tax-loss harvesting |
| 21 | **FY Analysis** | `fy` | Australian Financial Year reporting (July-June) |
| 22 | **Change Tracking** | `changes` | Track portfolio changes between snapshots |

### Export & Integration (23-25)

| # | Feature | Command | Description |
|---|---------|---------|-------------|
| 23 | **CSV Export** | `export --format csv` | Export holdings to CSV |
| 24 | **Excel Export** | `export --format excel` | Multi-sheet XLSX workbook |
| 25 | **PDF Report** | `export --format pdf` | Professional PDF report |

### Utilities (26-28)

| # | Feature | Command | Description |
|---|---------|---------|-------------|
| 26 | **History** | `history` | View all portfolio snapshots |
| 27 | **Compare** | `compare` | Compare two snapshots side-by-side |
| 28 | **Charts** | `chart` | ASCII charts (sectors, performance, tree view) |

### Web Interface (29)

| # | Feature | Command | Description |
|---|---------|---------|-------------|
| 29 | **Web Dashboard** | `web` | Flask-based web UI (optional) |

---

## Command Reference

### Portfolio Management

```bash
# Import
import portfolio.csv              # Import CommSec CSV

# View
view                              # Summary view
view --dashboard                  # Full dashboard
view --limit 50                   # Show more holdings

# Analyze
analyze                           # Quick analysis
analyze --report                  # Full text report

# Query
query --min-return 10             # Holdings with >10% return
query --profitable                # Only profitable holdings
query --asset-class etf           # Filter by asset class
query --min-value 10000           # Holdings worth >$10k
```

### Market Data

```bash
# Live prices
update                            # Update all holdings
update --save                     # Save as new snapshot

# Single quote
quote CBA                         # Get CBA quote
quote BHP                         # Get BHP quote

# News
news                              # All portfolio news
news --code CBA                   # News for specific stock
```

### Dividends & Income

```bash
# Dividend analysis
dividends                         # Overview
dividends --list                  # All holdings with yields
dividends --projection            # 12-month forecast

# Cashflow
cashflow                          # Dividend calendar
cashflow --detailed               # Show individual payments
cashflow --drp                    # DRP simulation (10 years)
```

### Transactions

```bash
# Record transactions
tx --buy --code CBA --quantity 100 --price 115.50 --fees 19.95
tx --sell --code CBA --quantity 50 --price 120.00
tx --dividend --code VAS --amount 450.00 --franking 192.86

# View history
tx                                # All transactions
tx --code CBA                     # Filter by stock
tx --type sell                    # Filter by type
tx --summary                      # Transaction summary
tx --gains                        # Realized gains report
tx --gains --fy 2024-25           # CGT for financial year
```

### Goals

```bash
# Create goals
goals --add --name "Reach $1M" --type portfolio_value --target 1000000
goals --add --name "1000 CBA" --type shares_owned --code CBA --target 1000

# Track progress
goals                             # View all goals
goals --view 1                    # Detailed view
goals --update                    # Update from portfolio
goals --view 1 --project          # Project completion date
```

### Investor Profile

```bash
# Create profile
investor --new                    # Interactive questionnaire

# View profile
investor                          # Current profile
investor --list                   # All profiles
investor --view 1 --compare       # Compare to portfolio
```

### Tax & Reporting

```bash
# Tax report
tax                               # Current FY
tax --fy 2023-24                  # Specific FY
tax --harvest                     # Tax-loss harvesting

# Financial year
fy                                # Current FY analysis
fy 2023-24                        # Specific FY
fy --compare 2022-23,2023-24      # Compare two FYs

# Changes
changes                           # Latest changes
changes --history                 # Import history
changes --fy 2024-25              # FY comparison
```

### Visualization

```bash
# Export visualizations
viz                               # All formats
viz --format sankey               # SankeyMATIC
viz --format flourish             # Flourish CSV
viz --format plotly               # Interactive HTML
viz --format artifact             # Claude Artifacts
viz --format markdown             # Markdown report

# ASCII charts
chart sectors                     # Sector pie chart
chart tree                        # Holdings tree
chart performance                 # Top performers
chart holdings                    # By value
```

### Export

```bash
export                            # CSV (default)
export --format json              # JSON
export --format excel             # Multi-sheet XLSX
export --format pdf               # PDF report
export --format tax               # Tax package
```

### Alerts

```bash
# Create alerts
alerts --add price-above --code CBA --threshold 150
alerts --add value-below --threshold 2000000
alerts --add loss-below --code VAS --threshold 10

# Manage
alerts                            # List all
alerts --check                    # Check against portfolio
alerts --remove <ID>              # Remove alert
```

---

## Module Structure

```
portfolio_tracker/
├── __init__.py           # Package exports
├── __main__.py           # Entry point
├── main.py               # CLI commands (2300+ lines)
├── models.py             # Data models (Holding, Portfolio, Sector, AssetClass)
├── parser.py             # CommSec CSV parser
├── storage.py            # SQLite database
├── analysis.py           # Portfolio analysis
├── visualizer.py         # Text-based visualization
├── formatting.py         # Colors, formatting utilities
├── price_fetcher.py      # Yahoo Finance integration
├── sector_lookup.py      # GICS sector classification
├── dividend_tracker.py   # Dividend data fetching
├── alerts.py             # Alert system
├── tax_reporting.py      # CGT and tax reports
├── change_tracker.py     # Portfolio change tracking
├── fy_analysis.py        # Financial year analysis
├── status_dashboard.py   # Quick status view
├── charts.py             # ASCII charts
├── news_feed.py          # News fetching
├── export_formats.py     # Excel, PDF export
├── viz_export.py         # Visualization exports
├── cashflow_forecast.py  # Dividend forecasting
├── portfolio_profile.py  # Risk profile analysis
├── transaction_log.py    # Transaction management
├── goal_tracker.py       # Goal tracking
├── investor_profile.py   # Risk questionnaire
└── web_dashboard.py      # Flask web UI (optional)
```

---

## Data Storage

```
data/
└── portfolio/
    ├── portfolio.db          # Main portfolio database
    ├── transactions.db       # Transaction history
    ├── goals.db              # Goal tracking
    ├── investor_profiles.db  # Investor profiles
    ├── alerts.json           # Alert configuration
    └── visualizations/       # Exported charts
```

---

## Dependencies

**Required:**
- Python 3.8+

**Optional (for enhanced features):**
- `yfinance` - Live ASX prices
- `requests` - News feed
- `openpyxl` - Excel export
- `reportlab` - PDF export
- `plotly` - Interactive charts
- `flask` - Web dashboard
- `matplotlib` - PNG chart export

Install all optional:
```bash
pip install yfinance requests openpyxl reportlab plotly flask matplotlib
```

---

## Australian-Specific Features

- **ASX stock codes** (3-4 letter format)
- **Australian Financial Year** (July 1 - June 30)
- **CGT discount** (50% for holdings >12 months)
- **Franking credits** tracking
- **GICS sectors** for ASX 200 stocks
- **DRP** (Dividend Reinvestment Plan) simulation

---

## Quick Status

```bash
python -m portfolio_tracker
```

Shows at-a-glance:
- Portfolio value and daily change
- Top holdings
- Sector allocation
- Recent performance
- Upcoming dividends
