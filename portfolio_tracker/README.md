# Portfolio Tracker

A portfolio tracking tool for Australian investors using CommSec. Import your CSV exports, visualize holdings, analyze performance, and query your portfolio to make informed investment decisions.

## Features

- **CSV Import**: Parse CommSec portfolio exports automatically
- **Portfolio Visualization**: ASCII tables, charts, and dashboards
- **Performance Analysis**: Track winners/losers, concentration risk, sector allocation
- **Historical Tracking**: Store multiple snapshots and compare over time
- **Flexible Queries**: Filter holdings by value, return, asset class, and more
- **Export Options**: CSV, JSON, and text reports

## Quick Start

### Import a Portfolio

```bash
# Import your CommSec CSV export
python -m portfolio_tracker import ~/Downloads/Portfolio_2024-01-15.csv
```

### View Your Portfolio

```bash
# Quick summary view
python -m portfolio_tracker view

# Full dashboard with charts
python -m portfolio_tracker view --dashboard

# Detailed analysis
python -m portfolio_tracker analyze --report
```

### Query Holdings

```bash
# Find all profitable holdings
python -m portfolio_tracker query --profitable

# Holdings with >10% return
python -m portfolio_tracker query --min-return 10

# ETFs only
python -m portfolio_tracker query --asset-class etf

# Large positions (>5% of portfolio)
python -m portfolio_tracker query --min-weight 5
```

### Track History

```bash
# View all snapshots
python -m portfolio_tracker history

# Compare two snapshots
python -m portfolio_tracker compare --old abc123 --new def456

# Generate history chart (requires matplotlib)
python -m portfolio_tracker history --chart
```

## CommSec CSV Format

The parser automatically handles CommSec CSV exports with these columns:

| Column | Description |
|--------|-------------|
| Code | ASX ticker symbol (e.g., CBA, VAS) |
| Company | Full company/ETF name |
| Quantity | Number of shares held |
| Avg Cost | Average purchase price per share |
| Current Price | Current market price |
| Market Value | Current total value |
| Profit/Loss $ | Dollar profit/loss |
| Profit/Loss % | Percentage profit/loss |

The parser is flexible and handles column name variations.

## Analysis Features

### Portfolio Summary
- Total market value and cost base
- Overall profit/loss ($ and %)
- Number of holdings

### Performance Metrics
- Win rate (% of profitable positions)
- Best and worst performers
- Average winner/loser returns

### Concentration Risk
- Top holding weight
- Top 5/10 concentration
- Herfindahl-Hirschman Index (HHI)
- Effective number of holdings

### Allocation Analysis
- Asset class breakdown (ETF, REIT, LIC, etc.)
- Sector allocation (if available)
- Rebalancing suggestions

## Commands Reference

| Command | Description |
|---------|-------------|
| `import <file>` | Import CommSec CSV |
| `view` | View current portfolio |
| `analyze` | Analyze portfolio |
| `query` | Query holdings with filters |
| `holding <code>` | View specific holding |
| `history` | Show portfolio history |
| `compare` | Compare two snapshots |
| `export` | Export portfolio |
| `stats` | Database statistics |

## Data Storage

Portfolio data is stored in SQLite at `data/portfolio.db`. Each import creates a snapshot that can be compared with previous imports to track changes over time.

## Future Enhancements

- **Live Price Data**: Fetch real-time ASX prices
- **Dividend Tracking**: Import dividend history
- **Tax Reports**: Generate CGT reports
- **Alerts**: Set price/return alerts
- **Web Interface**: Browser-based dashboard

## Requirements

- Python 3.9+
- pandas (for data handling)
- matplotlib (optional, for charts)

## Installation

```bash
# Install dependencies
pip install pandas

# Optional: for charts
pip install matplotlib
```

## Example Output

```
╔══════════════════════════════════════════════════════════════╗
║  PORTFOLIO SUMMARY - 2024-01-15                              ║
╠══════════════════════════════════════════════════════════════╣
║  Holdings:  15          Cost Base:    $    52,450.00         ║
║                        Market Value: $    68,157.50          ║
║                                                              ║
║  ▲ P/L: $  +15,707.50 (+29.95%)                             ║
╚══════════════════════════════════════════════════════════════╝

Code   Name                         Qty    Avg     Price        Value       P/L $   P/L %   Wt%
==================================================================================================
CBA    Commonwealth Bank of Austra   50   $95.50  $152.30  $  7,615.00  +$2,840.00  +59.1%  11.2%
VAS    Vanguard Australian Shares    80   $85.20   $95.40  $  7,632.00   +$816.00  +12.0%  11.2%
VGS    Vanguard MSCI Index Interna   60   $95.00  $118.50  $  7,110.00 +$1,410.00  +24.7%  10.4%
...
```
