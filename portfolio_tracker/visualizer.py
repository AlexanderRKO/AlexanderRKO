"""
Portfolio visualization tools.

Provides text-based and optional graphical visualizations.
Uses ASCII charts for CLI display and optional matplotlib for images.
"""

import logging
from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from .models import Portfolio, Holding, PortfolioSnapshot

logger = logging.getLogger(__name__)


class PortfolioVisualizer:
    """
    Visualizer for portfolio data.

    Provides ASCII charts for terminal display and optional
    matplotlib charts for image export.
    """

    def __init__(self, portfolio: Portfolio):
        self.portfolio = portfolio

    def holdings_table(self, limit: int = 20) -> str:
        """
        Generate an ASCII table of holdings.

        Args:
            limit: Maximum number of holdings to show

        Returns:
            Formatted table string
        """
        lines = []

        # Header
        header = (
            f"{'Code':<6} {'Name':<28} {'Qty':>8} {'Avg':>8} "
            f"{'Price':>8} {'Value':>12} {'P/L $':>12} {'P/L %':>8} {'Wt%':>6}"
        )
        lines.append("=" * len(header))
        lines.append(header)
        lines.append("=" * len(header))

        # Holdings
        for h in self.portfolio.top_holdings[:limit]:
            name = h.name[:27] + "…" if len(h.name) > 28 else h.name
            pl_indicator = "+" if h.profit_loss >= 0 else ""

            line = (
                f"{h.code:<6} {name:<28} {h.quantity:>8,} "
                f"${float(h.avg_cost):>7.2f} ${float(h.current_price):>7.2f} "
                f"${float(h.market_value):>11,.2f} "
                f"{pl_indicator}${float(h.profit_loss):>10,.2f} "
                f"{float(h.profit_loss_percent):>+7.1f}% "
                f"{float(h.portfolio_weight):>5.1f}%"
            )
            lines.append(line)

        if len(self.portfolio.holdings) > limit:
            lines.append(f"... and {len(self.portfolio.holdings) - limit} more holdings")

        # Totals
        lines.append("=" * len(header))
        pl_indicator = "+" if self.portfolio.total_profit_loss >= 0 else ""
        lines.append(
            f"{'TOTAL':<6} {'':<28} {'':<8} {'':<8} {'':<8} "
            f"${float(self.portfolio.total_market_value):>11,.2f} "
            f"{pl_indicator}${float(self.portfolio.total_profit_loss):>10,.2f} "
            f"{float(self.portfolio.total_profit_loss_percent):>+7.1f}% "
            f"{'100.0%':>6}"
        )

        return "\n".join(lines)

    def allocation_bar_chart(
        self,
        data: Dict[str, float],
        title: str = "Allocation",
        width: int = 50
    ) -> str:
        """
        Generate an ASCII horizontal bar chart.

        Args:
            data: Dictionary of label -> value pairs
            title: Chart title
            width: Maximum bar width in characters

        Returns:
            Formatted bar chart string
        """
        if not data:
            return f"{title}: No data"

        lines = [title, "-" * len(title)]

        max_value = max(data.values())
        max_label_len = max(len(str(k)) for k in data.keys())

        for label, value in data.items():
            bar_len = int((value / max_value) * width) if max_value > 0 else 0
            bar = "█" * bar_len
            lines.append(f"{str(label):<{max_label_len}} │ {bar} {value:.1f}%")

        return "\n".join(lines)

    def asset_allocation_chart(self, width: int = 40) -> str:
        """Generate asset class allocation bar chart."""
        allocations = self.portfolio.asset_class_allocation()
        data = {
            ac.value.replace("_", " ").title(): float(weight)
            for ac, weight in sorted(allocations.items(), key=lambda x: x[1], reverse=True)
        }
        return self.allocation_bar_chart(data, "Asset Class Allocation", width)

    def sector_allocation_chart(self, width: int = 40) -> str:
        """Generate sector allocation bar chart."""
        allocations = self.portfolio.sector_allocation()
        data = {
            sector.value.replace("_", " ").title(): float(weight)
            for sector, weight in sorted(allocations.items(), key=lambda x: x[1], reverse=True)
        }
        return self.allocation_bar_chart(data, "Sector Allocation", width)

    def performance_chart(self, width: int = 40) -> str:
        """
        Generate a performance chart showing gains/losses by holding.

        Returns:
            ASCII chart string
        """
        lines = ["Holdings Performance", "-" * 20]

        # Sort by profit/loss percent
        sorted_holdings = sorted(
            self.portfolio.holdings,
            key=lambda h: h.profit_loss_percent,
            reverse=True
        )

        if not sorted_holdings:
            return "\n".join(lines + ["No holdings"])

        max_gain = max(float(h.profit_loss_percent) for h in sorted_holdings)
        max_loss = min(float(h.profit_loss_percent) for h in sorted_holdings)
        max_abs = max(abs(max_gain), abs(max_loss)) or 1

        half_width = width // 2

        for h in sorted_holdings[:15]:  # Top 15
            pct = float(h.profit_loss_percent)
            bar_len = int((abs(pct) / max_abs) * half_width)

            if pct >= 0:
                bar = " " * half_width + "│" + "█" * bar_len
            else:
                bar = " " * (half_width - bar_len) + "█" * bar_len + "│"

            lines.append(f"{h.code:<6} {bar} {pct:>+7.1f}%")

        return "\n".join(lines)

    def top_holdings_pie(self, top_n: int = 10) -> str:
        """
        Generate a simple text representation of top holdings.

        Args:
            top_n: Number of top holdings to show

        Returns:
            Formatted string showing top holdings
        """
        lines = ["Top Holdings by Weight", "=" * 30]

        top = self.portfolio.top_holdings[:top_n]
        other_weight = Decimal("100") - sum(h.portfolio_weight for h in top)

        for h in top:
            pct = float(h.portfolio_weight)
            bars = int(pct / 2)  # 2% per bar
            lines.append(f"{h.code:<6} {'█' * bars} {pct:.1f}%")

        if other_weight > 0:
            bars = int(float(other_weight) / 2)
            lines.append(f"{'Other':<6} {'░' * bars} {float(other_weight):.1f}%")

        return "\n".join(lines)

    def dashboard(self) -> str:
        """
        Generate a complete dashboard view.

        Returns:
            Multi-section dashboard string
        """
        sections = [
            self._summary_box(),
            "",
            self.holdings_table(limit=15),
            "",
            self.asset_allocation_chart(width=35),
            "",
            self.performance_chart(width=30),
        ]

        return "\n".join(sections)

    def _summary_box(self) -> str:
        """Generate summary statistics box."""
        p = self.portfolio
        pl_arrow = "▲" if p.total_profit_loss >= 0 else "▼"
        pl_color_hint = "(profit)" if p.total_profit_loss >= 0 else "(loss)"

        return f"""
╔══════════════════════════════════════════════════════════════╗
║  PORTFOLIO SUMMARY - {p.snapshot_date.isoformat():<20}                   ║
╠══════════════════════════════════════════════════════════════╣
║  Holdings:  {p.holding_count:<8}    Cost Base:    ${float(p.total_cost_base):>15,.2f}  ║
║                        Market Value: ${float(p.total_market_value):>15,.2f}  ║
║                                                              ║
║  {pl_arrow} P/L: ${float(p.total_profit_loss):>+14,.2f} ({float(p.total_profit_loss_percent):>+6.2f}%) {pl_color_hint:<10}  ║
╚══════════════════════════════════════════════════════════════╝
""".strip()


def plot_portfolio_history(
    snapshots: List[PortfolioSnapshot],
    output_path: Optional[Path] = None
) -> Optional[str]:
    """
    Plot portfolio value over time using matplotlib.

    Args:
        snapshots: List of portfolio snapshots
        output_path: Optional path to save the image

    Returns:
        Path to saved image, or None if matplotlib not available
    """
    try:
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
    except ImportError:
        logger.warning("matplotlib not installed. Install with: pip install matplotlib")
        return None

    if not snapshots:
        return None

    # Sort by date
    snapshots = sorted(snapshots, key=lambda s: s.snapshot_date)

    dates = [s.snapshot_date for s in snapshots]
    values = [float(s.total_market_value) for s in snapshots]
    costs = [float(s.total_cost_base) for s in snapshots]

    fig, ax = plt.subplots(figsize=(12, 6))

    ax.plot(dates, values, label="Market Value", linewidth=2, color="green")
    ax.plot(dates, costs, label="Cost Base", linewidth=2, color="blue", linestyle="--")

    ax.fill_between(dates, costs, values, alpha=0.3, color="green", where=[v >= c for v, c in zip(values, costs)])
    ax.fill_between(dates, costs, values, alpha=0.3, color="red", where=[v < c for v, c in zip(values, costs)])

    ax.set_xlabel("Date")
    ax.set_ylabel("Value ($)")
    ax.set_title("Portfolio Value Over Time")
    ax.legend()
    ax.grid(True, alpha=0.3)

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    fig.autofmt_xdate()

    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"${x:,.0f}"))

    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close()
        return str(output_path)
    else:
        plt.show()
        return None


def plot_allocation_pie(
    portfolio: Portfolio,
    by: str = "asset_class",
    output_path: Optional[Path] = None
) -> Optional[str]:
    """
    Create a pie chart of portfolio allocation.

    Args:
        portfolio: Portfolio to visualize
        by: "asset_class" or "sector"
        output_path: Optional path to save the image

    Returns:
        Path to saved image, or None if matplotlib not available
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib not installed. Install with: pip install matplotlib")
        return None

    if by == "sector":
        allocations = portfolio.sector_allocation()
        title = "Portfolio by Sector"
    else:
        allocations = portfolio.asset_class_allocation()
        title = "Portfolio by Asset Class"

    labels = [k.value.replace("_", " ").title() for k in allocations.keys()]
    sizes = [float(v) for v in allocations.values()]

    # Filter out very small allocations for cleaner chart
    threshold = 2.0
    other = sum(s for s in sizes if s < threshold)
    labels_filtered = [l for l, s in zip(labels, sizes) if s >= threshold]
    sizes_filtered = [s for s in sizes if s >= threshold]

    if other > 0:
        labels_filtered.append("Other")
        sizes_filtered.append(other)

    fig, ax = plt.subplots(figsize=(10, 8))
    colors = plt.cm.Set3(range(len(labels_filtered)))

    wedges, texts, autotexts = ax.pie(
        sizes_filtered,
        labels=labels_filtered,
        autopct="%1.1f%%",
        colors=colors,
        startangle=90,
    )

    ax.set_title(title)
    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close()
        return str(output_path)
    else:
        plt.show()
        return None
