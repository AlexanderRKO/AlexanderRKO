"""
Charts - Terminal and image-based visualizations.

Provides:
- ASCII charts for terminal display
- Matplotlib charts for image export (optional)
- Interactive chart data for web dashboard
"""

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path

from .models import Portfolio, Holding
from .formatting import (
    green, red, yellow, blue, cyan, magenta, bold, dim,
    COLORS_ENABLED
)

logger = logging.getLogger(__name__)

# Check for matplotlib
try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    plt = None


# ============================================================
# ASCII TERMINAL CHARTS
# ============================================================

def ascii_bar_chart(
    data: Dict[str, float],
    width: int = 40,
    show_values: bool = True,
    color_positive: bool = True,
    title: Optional[str] = None,
) -> str:
    """
    Create an ASCII horizontal bar chart.

    Args:
        data: Dictionary of label -> value
        width: Width of the bar area
        show_values: Whether to show numeric values
        color_positive: Color bars based on positive/negative
        title: Optional chart title

    Returns:
        Formatted chart string
    """
    if not data:
        return "No data to display"

    lines = []

    if title:
        lines.append(bold(title))
        lines.append("")

    max_label = max(len(str(k)) for k in data.keys())
    max_val = max(abs(v) for v in data.values()) if data.values() else 1

    for label, value in data.items():
        # Calculate bar length
        bar_len = int((abs(value) / max_val) * width) if max_val > 0 else 0
        bar = "█" * bar_len

        # Color the bar
        if COLORS_ENABLED and color_positive:
            if value > 0:
                bar = green(bar)
            elif value < 0:
                bar = red(bar)

        # Format the line
        label_str = str(label).ljust(max_label)
        if show_values:
            if isinstance(value, float) and abs(value) < 1000:
                val_str = f"{value:>8.2f}"
            else:
                val_str = f"{value:>8,.0f}"
            lines.append(f"  {label_str}  {bar} {val_str}")
        else:
            lines.append(f"  {label_str}  {bar}")

    return "\n".join(lines)


def ascii_horizontal_bar(
    data: Dict[str, float],
    width: int = 50,
    title: Optional[str] = None,
) -> str:
    """
    Create a stacked horizontal bar showing proportions.

    Args:
        data: Dictionary of label -> value (will be shown as percentages)
        width: Total width of the bar
        title: Optional title

    Returns:
        Formatted chart string
    """
    if not data:
        return "No data"

    total = sum(data.values())
    if total <= 0:
        return "No data"

    lines = []
    if title:
        lines.append(bold(title))

    # Create the bar
    bar_chars = []
    colors = [cyan, green, yellow, magenta, blue, red]

    for i, (label, value) in enumerate(data.items()):
        pct = value / total
        char_count = max(1, int(pct * width))
        char = "█"
        if COLORS_ENABLED:
            char = colors[i % len(colors)](char)
        bar_chars.append(char * char_count)

    bar = "".join(bar_chars)[:width]
    lines.append(f"  [{bar}]")

    # Legend
    lines.append("")
    for i, (label, value) in enumerate(data.items()):
        pct = (value / total) * 100
        marker = "█"
        if COLORS_ENABLED:
            marker = colors[i % len(colors)](marker)
        lines.append(f"  {marker} {label}: {pct:.1f}%")

    return "\n".join(lines)


def ascii_sparkline(
    values: List[float],
    width: Optional[int] = None,
) -> str:
    """
    Create a sparkline from a list of values.

    Args:
        values: List of numeric values
        width: Optional width (will sample if needed)

    Returns:
        Sparkline string
    """
    if not values:
        return ""

    # Sample if needed
    if width and len(values) > width:
        step = len(values) / width
        values = [values[int(i * step)] for i in range(width)]

    chars = "▁▂▃▄▅▆▇█"
    min_val = min(values)
    max_val = max(values)

    if max_val == min_val:
        return chars[4] * len(values)

    result = ""
    for val in values:
        normalized = (val - min_val) / (max_val - min_val)
        idx = int(normalized * (len(chars) - 1))
        result += chars[idx]

    # Color based on trend
    if COLORS_ENABLED:
        if values[-1] > values[0]:
            result = green(result)
        elif values[-1] < values[0]:
            result = red(result)

    return result


def ascii_pie_chart(
    data: Dict[str, float],
    title: Optional[str] = None,
) -> str:
    """
    Create a text-based pie chart representation.

    Args:
        data: Dictionary of label -> value
        title: Optional title

    Returns:
        Formatted chart string
    """
    if not data:
        return "No data"

    total = sum(data.values())
    if total <= 0:
        return "No data"

    lines = []
    if title:
        lines.append(bold(title))
        lines.append("")

    # Sort by value descending
    sorted_items = sorted(data.items(), key=lambda x: x[1], reverse=True)

    colors = [cyan, green, yellow, magenta, blue, red]

    for i, (label, value) in enumerate(sorted_items):
        pct = (value / total) * 100
        bar_len = int(pct / 2)  # Scale to reasonable width
        bar = "█" * bar_len

        if COLORS_ENABLED:
            bar = colors[i % len(colors)](bar)

        lines.append(f"  {label:<20} {bar} {pct:>5.1f}%")

    return "\n".join(lines)


def ascii_table(
    headers: List[str],
    rows: List[List[Any]],
    alignments: Optional[List[str]] = None,
    title: Optional[str] = None,
) -> str:
    """
    Create a formatted ASCII table.

    Args:
        headers: Column headers
        rows: List of rows (each row is a list of values)
        alignments: List of 'l', 'r', 'c' for each column
        title: Optional title

    Returns:
        Formatted table string
    """
    if not headers or not rows:
        return "No data"

    if alignments is None:
        alignments = ['l'] * len(headers)

    # Calculate column widths
    widths = [len(str(h)) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(widths):
                widths[i] = max(widths[i], len(str(cell)))

    lines = []
    if title:
        lines.append(bold(title))
        lines.append("")

    # Header
    header_parts = []
    for i, h in enumerate(headers):
        if alignments[i] == 'r':
            header_parts.append(str(h).rjust(widths[i]))
        elif alignments[i] == 'c':
            header_parts.append(str(h).center(widths[i]))
        else:
            header_parts.append(str(h).ljust(widths[i]))

    header_line = "  " + "  ".join(header_parts)
    lines.append(dim(header_line) if COLORS_ENABLED else header_line)
    lines.append("  " + "─" * (sum(widths) + 2 * (len(widths) - 1)))

    # Rows
    for row in rows:
        row_parts = []
        for i, cell in enumerate(row):
            cell_str = str(cell)
            if i < len(widths):
                if alignments[i] == 'r':
                    row_parts.append(cell_str.rjust(widths[i]))
                elif alignments[i] == 'c':
                    row_parts.append(cell_str.center(widths[i]))
                else:
                    row_parts.append(cell_str.ljust(widths[i]))
        lines.append("  " + "  ".join(row_parts))

    return "\n".join(lines)


def sector_tree(portfolio: Portfolio) -> str:
    """
    Create a tree view of holdings by sector.

    Args:
        portfolio: Portfolio to display

    Returns:
        Formatted tree string
    """
    lines = []
    lines.append(bold("Portfolio by Sector"))
    lines.append("")

    # Group by sector
    sectors: Dict[str, List[Holding]] = {}
    for h in portfolio.holdings:
        sector_name = h.sector.value.replace("_", " ").title()
        if sector_name not in sectors:
            sectors[sector_name] = []
        sectors[sector_name].append(h)

    # Sort sectors by total value
    sector_totals = {
        s: sum(h.market_value for h in holdings)
        for s, holdings in sectors.items()
    }
    sorted_sectors = sorted(sector_totals.keys(), key=lambda s: sector_totals[s], reverse=True)

    for i, sector in enumerate(sorted_sectors):
        holdings = sorted(sectors[sector], key=lambda h: h.market_value, reverse=True)
        total = sector_totals[sector]
        pct = (float(total) / float(portfolio.total_market_value)) * 100

        # Sector line
        is_last_sector = (i == len(sorted_sectors) - 1)
        prefix = "└── " if is_last_sector else "├── "
        sector_line = f"{prefix}{bold(sector)} ({len(holdings)}) - ${float(total):,.0f} ({pct:.1f}%)"
        lines.append(sector_line)

        # Holdings under this sector
        for j, h in enumerate(holdings[:5]):  # Show top 5 per sector
            is_last = (j == min(4, len(holdings) - 1))
            h_prefix = "    └── " if is_last else "    ├── "
            if not is_last_sector:
                h_prefix = "│   └── " if is_last else "│   ├── "

            profit_str = f"+{float(h.profit_loss_percent):.1f}%" if h.profit_loss >= 0 else f"{float(h.profit_loss_percent):.1f}%"
            if COLORS_ENABLED:
                profit_str = green(profit_str) if h.profit_loss >= 0 else red(profit_str)

            lines.append(f"{h_prefix}{h.code}: ${float(h.market_value):,.0f} ({profit_str})")

        if len(holdings) > 5:
            more_prefix = "    " if is_last_sector else "│   "
            lines.append(f"{more_prefix}    ... and {len(holdings) - 5} more")

    return "\n".join(lines)


# ============================================================
# MATPLOTLIB CHARTS (optional)
# ============================================================

def check_matplotlib() -> bool:
    """Check if matplotlib is available."""
    return MATPLOTLIB_AVAILABLE


def create_pie_chart(
    data: Dict[str, float],
    title: str = "Portfolio Allocation",
    output_path: Optional[Path] = None,
) -> Optional[Path]:
    """
    Create a pie chart using matplotlib.

    Args:
        data: Dictionary of label -> value
        title: Chart title
        output_path: Where to save the image

    Returns:
        Path to saved image or None
    """
    if not MATPLOTLIB_AVAILABLE:
        logger.warning("matplotlib not available")
        return None

    if not data:
        return None

    fig, ax = plt.subplots(figsize=(10, 8))

    labels = list(data.keys())
    values = list(data.values())

    # Create pie chart
    wedges, texts, autotexts = ax.pie(
        values,
        labels=labels,
        autopct='%1.1f%%',
        startangle=90,
        pctdistance=0.85,
    )

    # Style
    ax.set_title(title, fontsize=14, fontweight='bold')

    # Save
    if output_path is None:
        output_path = Path("portfolio_pie.png")

    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()

    return output_path


def create_bar_chart(
    data: Dict[str, float],
    title: str = "Holdings Performance",
    xlabel: str = "",
    ylabel: str = "Value ($)",
    output_path: Optional[Path] = None,
    horizontal: bool = True,
) -> Optional[Path]:
    """
    Create a bar chart using matplotlib.

    Args:
        data: Dictionary of label -> value
        title: Chart title
        xlabel: X-axis label
        ylabel: Y-axis label
        output_path: Where to save the image
        horizontal: If True, create horizontal bars

    Returns:
        Path to saved image or None
    """
    if not MATPLOTLIB_AVAILABLE:
        return None

    if not data:
        return None

    fig, ax = plt.subplots(figsize=(12, 8))

    labels = list(data.keys())
    values = list(data.values())

    # Color based on positive/negative
    colors = ['#4ade80' if v >= 0 else '#f87171' for v in values]

    if horizontal:
        ax.barh(labels, values, color=colors)
        ax.set_xlabel(ylabel)
    else:
        ax.bar(labels, values, color=colors)
        ax.set_ylabel(ylabel)
        plt.xticks(rotation=45, ha='right')

    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.axvline(x=0, color='gray', linewidth=0.5) if horizontal else ax.axhline(y=0, color='gray', linewidth=0.5)

    # Save
    if output_path is None:
        output_path = Path("portfolio_bar.png")

    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()

    return output_path


def create_line_chart(
    data: List[Tuple[date, float]],
    title: str = "Portfolio Value Over Time",
    ylabel: str = "Value ($)",
    output_path: Optional[Path] = None,
) -> Optional[Path]:
    """
    Create a line chart using matplotlib.

    Args:
        data: List of (date, value) tuples
        title: Chart title
        ylabel: Y-axis label
        output_path: Where to save the image

    Returns:
        Path to saved image or None
    """
    if not MATPLOTLIB_AVAILABLE:
        return None

    if not data:
        return None

    fig, ax = plt.subplots(figsize=(12, 6))

    dates = [d[0] for d in data]
    values = [d[1] for d in data]

    ax.plot(dates, values, linewidth=2, color='#3b82f6')
    ax.fill_between(dates, values, alpha=0.3, color='#3b82f6')

    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_ylabel(ylabel)

    # Format x-axis dates
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.xticks(rotation=45, ha='right')

    ax.grid(True, alpha=0.3)

    # Save
    if output_path is None:
        output_path = Path("portfolio_line.png")

    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()

    return output_path


# ============================================================
# CHART DATA FOR WEB DASHBOARD
# ============================================================

def get_sector_chart_data(portfolio: Portfolio) -> Dict[str, Any]:
    """Get sector allocation data for charting."""
    sectors: Dict[str, float] = {}

    for h in portfolio.holdings:
        sector_name = h.sector.value.replace("_", " ").title()
        if sector_name not in sectors:
            sectors[sector_name] = 0
        sectors[sector_name] += float(h.market_value)

    # Sort by value
    sorted_sectors = sorted(sectors.items(), key=lambda x: x[1], reverse=True)

    return {
        "labels": [s[0] for s in sorted_sectors],
        "values": [s[1] for s in sorted_sectors],
    }


def get_performance_chart_data(portfolio: Portfolio) -> Dict[str, Any]:
    """Get performance data for charting."""
    holdings = sorted(portfolio.holdings, key=lambda h: h.profit_loss_percent, reverse=True)

    return {
        "labels": [h.code for h in holdings],
        "values": [float(h.profit_loss_percent) for h in holdings],
        "profits": [float(h.profit_loss) for h in holdings],
    }


def get_holdings_chart_data(portfolio: Portfolio, top_n: int = 10) -> Dict[str, Any]:
    """Get top holdings data for charting."""
    holdings = sorted(portfolio.holdings, key=lambda h: h.market_value, reverse=True)[:top_n]

    return {
        "labels": [h.code for h in holdings],
        "values": [float(h.market_value) for h in holdings],
        "weights": [float(h.portfolio_weight) for h in holdings],
    }
