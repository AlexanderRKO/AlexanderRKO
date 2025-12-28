"""
Visualization Export - Export data for external visualization tools.

Supports:
- SankeyMATIC (flow diagrams)
- Plotly (interactive HTML charts)
- Flourish (animated visualizations)
- Generic CSV for any tool
"""

import json
import logging
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

from .models import Portfolio, Holding
from .sector_lookup import get_sector, get_sector_summary

logger = logging.getLogger(__name__)

# Check for Plotly
try:
    import plotly.graph_objects as go
    import plotly.express as px
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False


def check_plotly() -> bool:
    """Check if Plotly is available."""
    return PLOTLY_AVAILABLE


# =============================================================================
# SankeyMATIC Export
# =============================================================================

def export_sankey_format(
    portfolio: Portfolio,
    output_path: Optional[Path] = None,
    include_holdings: bool = True,
    min_holding_value: float = 1000,
) -> str:
    """
    Export portfolio data in SankeyMATIC format.

    Format: Source [Amount] Target
    Example: Portfolio [50000] Financials

    Args:
        portfolio: Portfolio to export
        output_path: Optional file path to save
        include_holdings: Include individual holdings (not just sectors)
        min_holding_value: Minimum value to include individual holdings

    Returns:
        SankeyMATIC formatted string
    """
    lines = []
    lines.append("// Portfolio Flow Diagram")
    lines.append(f"// Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"// Total Value: ${float(portfolio.total_market_value):,.0f}")
    lines.append("")
    lines.append("// Paste this into https://sankeymatic.com/build/")
    lines.append("")

    # Get sector summary
    sectors = get_sector_summary(portfolio)

    # Portfolio -> Sectors
    lines.append("// === Portfolio to Sectors ===")
    for sector_name, sector_data in sectors.items():
        value = float(sector_data["market_value"])
        if value > 0:
            lines.append(f"Portfolio [{value:.0f}] {sector_name}")

    lines.append("")

    # Sectors -> Holdings (if enabled)
    if include_holdings:
        lines.append("// === Sectors to Holdings ===")
        for holding in portfolio.holdings:
            value = float(holding.market_value)
            if value >= min_holding_value:
                sector = get_sector(holding.code)
                sector_name = sector.name if sector else "Other"
                # Truncate long names
                name = holding.code
                lines.append(f"{sector_name} [{value:.0f}] {name}")

    result = "\n".join(lines)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            f.write(result)
        logger.info(f"Saved SankeyMATIC format to {output_path}")

    return result


def export_sankey_profit_loss(
    portfolio: Portfolio,
    output_path: Optional[Path] = None,
) -> str:
    """
    Export profit/loss flow in SankeyMATIC format.

    Shows money flow: Cost Base -> Holdings -> (Profit or Loss)
    """
    lines = []
    lines.append("// Profit/Loss Flow Diagram")
    lines.append(f"// Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append("// Paste this into https://sankeymatic.com/build/")
    lines.append("// Use different colors for Gains vs Losses")
    lines.append("")

    # Cost base to holdings
    lines.append("// === Investment to Holdings ===")
    for holding in portfolio.holdings:
        cost = float(holding.cost_base)
        if cost > 0:
            lines.append(f"Investment [{cost:.0f}] {holding.code}")

    lines.append("")
    lines.append("// === Holdings to Profit/Loss ===")

    # Holdings to profit or loss
    total_profit = Decimal("0")
    total_loss = Decimal("0")

    for holding in portfolio.holdings:
        pl = holding.profit_loss
        if pl >= 0:
            total_profit += pl
            lines.append(f"{holding.code} [{float(pl):.0f}] Gains")
        else:
            total_loss += abs(pl)
            lines.append(f"{holding.code} [{float(abs(pl)):.0f}] Losses")

    lines.append("")
    lines.append(f"// Total Gains: ${float(total_profit):,.0f}")
    lines.append(f"// Total Losses: ${float(total_loss):,.0f}")

    result = "\n".join(lines)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            f.write(result)

    return result


# =============================================================================
# Flourish Export (CSV format)
# =============================================================================

def export_flourish_sankey(
    portfolio: Portfolio,
    output_path: Path,
) -> Path:
    """
    Export Sankey data for Flourish.

    Flourish expects CSV with: source, target, value
    """
    import csv

    rows = []

    # Portfolio -> Sectors
    sectors = get_sector_summary(portfolio)
    for sector_name, sector_data in sectors.items():
        value = float(sector_data["market_value"])
        if value > 0:
            rows.append({
                "source": "Portfolio",
                "target": sector_name,
                "value": value,
            })

    # Sectors -> Holdings
    for holding in portfolio.holdings:
        value = float(holding.market_value)
        if value > 500:  # Min threshold
            sector = get_sector(holding.code)
            sector_name = sector.name if sector else "Other"
            rows.append({
                "source": sector_name,
                "target": holding.code,
                "value": value,
            })

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["source", "target", "value"])
        writer.writeheader()
        writer.writerows(rows)

    return output_path


def export_flourish_treemap(
    portfolio: Portfolio,
    output_path: Path,
) -> Path:
    """
    Export treemap data for Flourish.

    Flourish expects: Category, Label, Value, Color Value
    """
    import csv

    rows = []
    for holding in portfolio.holdings:
        sector = get_sector(holding.code)
        sector_name = sector.name if sector else "Other"
        rows.append({
            "Category": sector_name,
            "Label": f"{holding.code}\n${float(holding.market_value):,.0f}",
            "Value": float(holding.market_value),
            "Color Value": float(holding.profit_loss_percent),
        })

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["Category", "Label", "Value", "Color Value"])
        writer.writeheader()
        writer.writerows(rows)

    return output_path


# =============================================================================
# Plotly Interactive HTML Charts
# =============================================================================

def create_plotly_sankey(
    portfolio: Portfolio,
    output_path: Optional[Path] = None,
) -> Optional[Any]:
    """
    Create an interactive Sankey diagram using Plotly.

    Returns Plotly figure object (or saves to HTML).
    """
    if not PLOTLY_AVAILABLE:
        logger.warning("Plotly not available. Install with: pip install plotly")
        return None

    # Build node and link lists
    nodes = ["Portfolio"]
    node_indices = {"Portfolio": 0}

    # Add sectors
    sectors = get_sector_summary(portfolio)
    for sector_name in sectors.keys():
        if sector_name not in node_indices:
            node_indices[sector_name] = len(nodes)
            nodes.append(sector_name)

    # Add holdings
    for holding in portfolio.holdings:
        if holding.code not in node_indices:
            node_indices[holding.code] = len(nodes)
            nodes.append(holding.code)

    # Build links
    sources = []
    targets = []
    values = []
    colors = []

    # Portfolio -> Sectors
    for sector_name, sector_data in sectors.items():
        value = float(sector_data["market_value"])
        if value > 0:
            sources.append(node_indices["Portfolio"])
            targets.append(node_indices[sector_name])
            values.append(value)
            colors.append("rgba(31, 119, 180, 0.4)")

    # Sectors -> Holdings
    for holding in portfolio.holdings:
        value = float(holding.market_value)
        if value > 500:
            sector = get_sector(holding.code)
            sector_name = sector.name if sector else "Other"
            sources.append(node_indices[sector_name])
            targets.append(node_indices[holding.code])
            values.append(value)

            # Color by profit/loss
            if holding.profit_loss >= 0:
                colors.append("rgba(44, 160, 44, 0.4)")  # Green
            else:
                colors.append("rgba(214, 39, 40, 0.4)")  # Red

    # Create figure
    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=15,
            thickness=20,
            line=dict(color="black", width=0.5),
            label=nodes,
            color="rgba(31, 119, 180, 0.8)",
        ),
        link=dict(
            source=sources,
            target=targets,
            value=values,
            color=colors,
        )
    )])

    fig.update_layout(
        title_text=f"Portfolio Flow - ${float(portfolio.total_market_value):,.0f}",
        font_size=12,
        template="plotly_dark",
        height=800,
    )

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.write_html(str(output_path))
        logger.info(f"Saved Plotly Sankey to {output_path}")

    return fig


def create_plotly_treemap(
    portfolio: Portfolio,
    output_path: Optional[Path] = None,
) -> Optional[Any]:
    """
    Create an interactive treemap using Plotly.
    """
    if not PLOTLY_AVAILABLE:
        return None

    # Prepare data
    labels = ["Portfolio"]
    parents = [""]
    values = [0]  # Root has no value
    colors = [0]

    # Add sectors
    sectors = get_sector_summary(portfolio)
    for sector_name, sector_data in sectors.items():
        labels.append(sector_name)
        parents.append("Portfolio")
        values.append(0)  # Sectors are just containers
        colors.append(sector_data["weighted_return"])

    # Add holdings
    for holding in portfolio.holdings:
        sector = get_sector(holding.code)
        sector_name = sector.name if sector else "Other"
        labels.append(f"{holding.code}<br>${float(holding.market_value):,.0f}")
        parents.append(sector_name)
        values.append(float(holding.market_value))
        colors.append(float(holding.profit_loss_percent))

    fig = go.Figure(go.Treemap(
        labels=labels,
        parents=parents,
        values=values,
        marker=dict(
            colors=colors,
            colorscale="RdYlGn",
            cmid=0,
            showscale=True,
            colorbar=dict(title="Return %"),
        ),
        textinfo="label+value",
        hovertemplate="<b>%{label}</b><br>Value: $%{value:,.0f}<br>Return: %{color:.1f}%<extra></extra>",
    ))

    fig.update_layout(
        title=f"Portfolio Treemap - ${float(portfolio.total_market_value):,.0f}",
        template="plotly_dark",
        height=700,
    )

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.write_html(str(output_path))

    return fig


def create_plotly_sunburst(
    portfolio: Portfolio,
    output_path: Optional[Path] = None,
) -> Optional[Any]:
    """
    Create an interactive sunburst chart using Plotly.
    """
    if not PLOTLY_AVAILABLE:
        return None

    # Prepare data
    labels = []
    parents = []
    values = []
    colors = []

    # Add sectors
    sectors = get_sector_summary(portfolio)
    for sector_name in sectors.keys():
        labels.append(sector_name)
        parents.append("")
        values.append(0)
        colors.append(0)

    # Add holdings
    for holding in portfolio.holdings:
        sector = get_sector(holding.code)
        sector_name = sector.name if sector else "Other"
        labels.append(holding.code)
        parents.append(sector_name)
        values.append(float(holding.market_value))
        colors.append(float(holding.profit_loss_percent))

    fig = go.Figure(go.Sunburst(
        labels=labels,
        parents=parents,
        values=values,
        marker=dict(
            colors=colors,
            colorscale="RdYlGn",
            cmid=0,
            showscale=True,
        ),
        branchvalues="total",
        hovertemplate="<b>%{label}</b><br>$%{value:,.0f}<br>%{color:.1f}%<extra></extra>",
    ))

    fig.update_layout(
        title=f"Portfolio Sunburst - ${float(portfolio.total_market_value):,.0f}",
        template="plotly_dark",
        height=700,
    )

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.write_html(str(output_path))

    return fig


def create_plotly_dashboard(
    portfolio: Portfolio,
    output_path: Path,
) -> Optional[Path]:
    """
    Create a full interactive dashboard with multiple charts.
    """
    if not PLOTLY_AVAILABLE:
        logger.warning("Plotly not available. Install with: pip install plotly")
        return None

    # Create subplots
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            "Sector Allocation",
            "Top Holdings by Value",
            "Profit/Loss by Holding",
            "Portfolio Weight Distribution",
        ),
        specs=[
            [{"type": "pie"}, {"type": "bar"}],
            [{"type": "bar"}, {"type": "pie"}],
        ],
        vertical_spacing=0.12,
        horizontal_spacing=0.1,
    )

    # 1. Sector Pie Chart
    sectors = get_sector_summary(portfolio)
    fig.add_trace(
        go.Pie(
            labels=list(sectors.keys()),
            values=[float(s["market_value"]) for s in sectors.values()],
            hole=0.4,
            textinfo="label+percent",
        ),
        row=1, col=1,
    )

    # 2. Top Holdings Bar Chart
    top_holdings = sorted(portfolio.holdings, key=lambda h: h.market_value, reverse=True)[:10]
    fig.add_trace(
        go.Bar(
            x=[h.code for h in top_holdings],
            y=[float(h.market_value) for h in top_holdings],
            marker_color="rgb(55, 83, 109)",
            text=[f"${float(h.market_value):,.0f}" for h in top_holdings],
            textposition="auto",
        ),
        row=1, col=2,
    )

    # 3. Profit/Loss Bar Chart (sorted by P/L)
    sorted_by_pl = sorted(portfolio.holdings, key=lambda h: h.profit_loss, reverse=True)
    colors = ["green" if h.profit_loss >= 0 else "red" for h in sorted_by_pl[:15]]
    fig.add_trace(
        go.Bar(
            x=[h.code for h in sorted_by_pl[:15]],
            y=[float(h.profit_loss) for h in sorted_by_pl[:15]],
            marker_color=colors,
        ),
        row=2, col=1,
    )

    # 4. Weight Distribution Pie
    fig.add_trace(
        go.Pie(
            labels=[h.code for h in top_holdings],
            values=[float(h.market_value) for h in top_holdings],
            hole=0.3,
            textinfo="label+percent",
        ),
        row=2, col=2,
    )

    # Update layout
    fig.update_layout(
        title_text=f"Portfolio Dashboard - {portfolio.snapshot_date.strftime('%Y-%m-%d')}",
        showlegend=False,
        template="plotly_dark",
        height=900,
        annotations=[
            dict(
                text=f"Total: ${float(portfolio.total_market_value):,.0f}",
                x=0.18, y=0.78,
                font_size=14,
                showarrow=False,
            ),
        ],
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(output_path))
    logger.info(f"Saved Plotly dashboard to {output_path}")

    return output_path


# =============================================================================
# Markdown Export
# =============================================================================

def export_to_markdown(
    portfolio: Portfolio,
    output_path: Optional[Path] = None,
    include_charts: bool = True,
) -> str:
    """
    Export portfolio to a formatted Markdown document.

    Great for GitHub, Notion, Obsidian, documentation, etc.
    """
    from datetime import datetime

    lines = []

    # Header
    lines.append(f"# Portfolio Report")
    lines.append(f"")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**Snapshot Date:** {portfolio.snapshot_date}")
    lines.append(f"")

    # Summary Box
    lines.append(f"## Summary")
    lines.append(f"")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Total Value | ${float(portfolio.total_market_value):,.2f} |")
    lines.append(f"| Cost Base | ${float(portfolio.total_cost_base):,.2f} |")
    lines.append(f"| Profit/Loss | ${float(portfolio.total_profit_loss):+,.2f} ({float(portfolio.total_profit_loss_percent):+.1f}%) |")
    lines.append(f"| Holdings | {portfolio.holding_count} |")
    lines.append(f"")

    # Performance Stats
    profitable = [h for h in portfolio.holdings if h.profit_loss >= 0]
    losing = [h for h in portfolio.holdings if h.profit_loss < 0]
    lines.append(f"### Performance")
    lines.append(f"")
    lines.append(f"- **Winners:** {len(profitable)} ({len(profitable)/portfolio.holding_count*100:.0f}%)")
    lines.append(f"- **Losers:** {len(losing)} ({len(losing)/portfolio.holding_count*100:.0f}%)")
    lines.append(f"")

    # Sector Allocation
    sectors = get_sector_summary(portfolio)
    lines.append(f"## Sector Allocation")
    lines.append(f"")
    lines.append(f"| Sector | Value | Weight | Return |")
    lines.append(f"|--------|------:|-------:|-------:|")
    for name, data in sorted(sectors.items(), key=lambda x: x[1]["market_value"], reverse=True):
        lines.append(
            f"| {name} | ${data['market_value']:,.0f} | {data['weight']:.1f}% | {data['return_percent']:+.1f}% |"
        )
    lines.append(f"")

    # ASCII Sector Chart (if enabled)
    if include_charts:
        lines.append(f"### Sector Distribution")
        lines.append(f"")
        lines.append(f"```")
        max_name_len = max(len(name) for name in sectors.keys())
        max_value = max(data["weight"] for data in sectors.values())
        for name, data in sorted(sectors.items(), key=lambda x: x[1]["weight"], reverse=True):
            bar_len = int(data["weight"] / max_value * 30) if max_value > 0 else 0
            bar = "█" * bar_len
            lines.append(f"{name:<{max_name_len}} │{bar} {data['weight']:.1f}%")
        lines.append(f"```")
        lines.append(f"")

    # Top Holdings
    lines.append(f"## Top 10 Holdings")
    lines.append(f"")
    lines.append(f"| Code | Name | Value | Weight | Return |")
    lines.append(f"|------|------|------:|-------:|-------:|")
    top_holdings = sorted(portfolio.holdings, key=lambda h: h.market_value, reverse=True)[:10]
    for h in top_holdings:
        name = h.name[:25] + "..." if len(h.name) > 25 else h.name
        pl_emoji = "🟢" if h.profit_loss >= 0 else "🔴"
        lines.append(
            f"| {h.code} | {name} | ${float(h.market_value):,.0f} | {float(h.portfolio_weight):.1f}% | {pl_emoji} {float(h.profit_loss_percent):+.1f}% |"
        )
    lines.append(f"")

    # Best & Worst Performers
    lines.append(f"## Performance Leaders")
    lines.append(f"")
    lines.append(f"### 🏆 Best Performers")
    lines.append(f"")
    lines.append(f"| Code | Return | P/L |")
    lines.append(f"|------|-------:|----:|")
    best = sorted(portfolio.holdings, key=lambda h: h.profit_loss_percent, reverse=True)[:5]
    for h in best:
        lines.append(f"| {h.code} | {float(h.profit_loss_percent):+.1f}% | ${float(h.profit_loss):+,.0f} |")
    lines.append(f"")

    lines.append(f"### 📉 Worst Performers")
    lines.append(f"")
    lines.append(f"| Code | Return | P/L |")
    lines.append(f"|------|-------:|----:|")
    worst = sorted(portfolio.holdings, key=lambda h: h.profit_loss_percent)[:5]
    for h in worst:
        lines.append(f"| {h.code} | {float(h.profit_loss_percent):+.1f}% | ${float(h.profit_loss):+,.0f} |")
    lines.append(f"")

    # All Holdings Table
    lines.append(f"## All Holdings")
    lines.append(f"")
    lines.append(f"<details>")
    lines.append(f"<summary>Click to expand ({portfolio.holding_count} holdings)</summary>")
    lines.append(f"")
    lines.append(f"| Code | Name | Qty | Avg Cost | Price | Value | P/L % |")
    lines.append(f"|------|------|----:|--------:|------:|------:|------:|")
    for h in sorted(portfolio.holdings, key=lambda x: x.market_value, reverse=True):
        name = h.name[:20] + "..." if len(h.name) > 20 else h.name
        lines.append(
            f"| {h.code} | {name} | {h.quantity:,} | ${float(h.avg_cost):.2f} | "
            f"${float(h.current_price):.2f} | ${float(h.market_value):,.0f} | {float(h.profit_loss_percent):+.1f}% |"
        )
    lines.append(f"")
    lines.append(f"</details>")
    lines.append(f"")

    # Footer
    lines.append(f"---")
    lines.append(f"*Generated by Portfolio Tracker*")

    result = "\n".join(lines)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            f.write(result)
        logger.info(f"Saved Markdown report to {output_path}")

    return result


# =============================================================================
# Claude Artifacts Export (React/Recharts)
# =============================================================================

def export_artifact_data(portfolio: Portfolio) -> Dict[str, Any]:
    """
    Export portfolio data in a format optimized for Claude Artifacts.

    Returns a dictionary with all data needed for an interactive React dashboard.
    """
    # Sector data
    sectors = get_sector_summary(portfolio)
    sector_data = [
        {
            "name": name,
            "value": float(data["market_value"]),
            "weight": float(data["weight"]),
            "return": float(data["return_percent"]),
            "count": data["count"],
        }
        for name, data in sectors.items()
    ]

    # Holdings data
    holdings_data = [
        {
            "code": h.code,
            "name": h.name[:30],
            "value": float(h.market_value),
            "cost": float(h.cost_base),
            "profit": float(h.profit_loss),
            "return": float(h.profit_loss_percent),
            "weight": float(h.portfolio_weight),
            "sector": get_sector(h.code).name if get_sector(h.code) else "Other",
        }
        for h in sorted(portfolio.holdings, key=lambda x: x.market_value, reverse=True)
    ]

    # Performance summary
    profitable = [h for h in portfolio.holdings if h.profit_loss >= 0]
    losing = [h for h in portfolio.holdings if h.profit_loss < 0]

    return {
        "summary": {
            "totalValue": float(portfolio.total_market_value),
            "totalCost": float(portfolio.total_cost_base),
            "totalProfit": float(portfolio.total_profit_loss),
            "returnPercent": float(portfolio.total_profit_loss_percent),
            "holdingCount": portfolio.holding_count,
            "profitableCount": len(profitable),
            "losingCount": len(losing),
            "date": portfolio.snapshot_date.isoformat(),
        },
        "sectors": sector_data,
        "holdings": holdings_data,
        "topHoldings": holdings_data[:10],
        "bestPerformers": sorted(holdings_data, key=lambda x: x["return"], reverse=True)[:5],
        "worstPerformers": sorted(holdings_data, key=lambda x: x["return"])[:5],
    }


def export_artifact_code(portfolio: Portfolio, output_path: Optional[Path] = None) -> str:
    """
    Generate a complete React component for Claude Artifacts.

    The generated code uses Recharts which is available in Claude Artifacts.
    """
    data = export_artifact_data(portfolio)

    # Generate the React component code
    code = '''import React, { useState } from "react";
import {
  PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, Legend, Treemap
} from "recharts";

// Portfolio data - replace with your data or paste from JSON export
const portfolioData = ''' + json.dumps(data, indent=2) + ''';

const COLORS = [
  "#0088FE", "#00C49F", "#FFBB28", "#FF8042", "#8884D8",
  "#82CA9D", "#FFC658", "#FF6B6B", "#4ECDC4", "#45B7D1"
];

const formatMoney = (value) => {
  if (value >= 1000000) return `$${(value / 1000000).toFixed(1)}M`;
  if (value >= 1000) return `$${(value / 1000).toFixed(0)}K`;
  return `$${value.toFixed(0)}`;
};

const SummaryCard = ({ label, value, subValue, positive }) => (
  <div style={{
    background: "#1a1a2e",
    borderRadius: "12px",
    padding: "16px",
    minWidth: "150px"
  }}>
    <div style={{ color: "#888", fontSize: "12px", textTransform: "uppercase" }}>
      {label}
    </div>
    <div style={{
      fontSize: "24px",
      fontWeight: "600",
      color: positive === undefined ? "#fff" : positive ? "#4ade80" : "#f87171"
    }}>
      {value}
    </div>
    {subValue && (
      <div style={{
        fontSize: "14px",
        color: positive === undefined ? "#666" : positive ? "#4ade80" : "#f87171"
      }}>
        {subValue}
      </div>
    )}
  </div>
);

export default function PortfolioDashboard() {
  const [activeTab, setActiveTab] = useState("overview");
  const { summary, sectors, holdings, topHoldings, bestPerformers, worstPerformers } = portfolioData;

  return (
    <div style={{
      fontFamily: "system-ui, sans-serif",
      background: "#0f0f1a",
      color: "#e0e0e0",
      padding: "20px",
      minHeight: "100vh"
    }}>
      {/* Header */}
      <div style={{ marginBottom: "24px" }}>
        <h1 style={{ margin: 0, color: "#fff" }}>Portfolio Dashboard</h1>
        <div style={{ color: "#888" }}>Snapshot: {summary.date}</div>
      </div>

      {/* Summary Cards */}
      <div style={{ display: "flex", gap: "16px", flexWrap: "wrap", marginBottom: "24px" }}>
        <SummaryCard
          label="Portfolio Value"
          value={formatMoney(summary.totalValue)}
          subValue={`${summary.holdingCount} holdings`}
        />
        <SummaryCard
          label="Total Profit/Loss"
          value={formatMoney(summary.totalProfit)}
          subValue={`${summary.returnPercent >= 0 ? "+" : ""}${summary.returnPercent.toFixed(1)}%`}
          positive={summary.totalProfit >= 0}
        />
        <SummaryCard
          label="Win/Loss"
          value={`${summary.profitableCount} / ${summary.losingCount}`}
          subValue="profitable / losing"
        />
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: "8px", marginBottom: "16px" }}>
        {["overview", "holdings", "performance"].map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              padding: "8px 16px",
              border: "none",
              borderRadius: "8px",
              background: activeTab === tab ? "#3b82f6" : "#1a1a2e",
              color: activeTab === tab ? "#fff" : "#888",
              cursor: "pointer",
              textTransform: "capitalize"
            }}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Content */}
      {activeTab === "overview" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px" }}>
          {/* Sector Pie Chart */}
          <div style={{ background: "#1a1a2e", borderRadius: "12px", padding: "16px" }}>
            <h3 style={{ margin: "0 0 16px 0" }}>Sector Allocation</h3>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={sectors}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={100}
                  label={({ name, weight }) => `${name}: ${weight.toFixed(1)}%`}
                >
                  {sectors.map((_, index) => (
                    <Cell key={index} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(value) => formatMoney(value)} />
              </PieChart>
            </ResponsiveContainer>
          </div>

          {/* Top Holdings Bar Chart */}
          <div style={{ background: "#1a1a2e", borderRadius: "12px", padding: "16px" }}>
            <h3 style={{ margin: "0 0 16px 0" }}>Top 10 Holdings</h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={topHoldings} layout="vertical">
                <XAxis type="number" tickFormatter={formatMoney} />
                <YAxis type="category" dataKey="code" width={50} />
                <Tooltip formatter={(value) => formatMoney(value)} />
                <Bar dataKey="value" fill="#3b82f6" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {activeTab === "holdings" && (
        <div style={{ background: "#1a1a2e", borderRadius: "12px", padding: "16px", overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid #333" }}>
                <th style={{ padding: "12px", textAlign: "left", color: "#888" }}>Code</th>
                <th style={{ padding: "12px", textAlign: "left", color: "#888" }}>Name</th>
                <th style={{ padding: "12px", textAlign: "right", color: "#888" }}>Value</th>
                <th style={{ padding: "12px", textAlign: "right", color: "#888" }}>Weight</th>
                <th style={{ padding: "12px", textAlign: "right", color: "#888" }}>Return</th>
              </tr>
            </thead>
            <tbody>
              {holdings.map((h) => (
                <tr key={h.code} style={{ borderBottom: "1px solid #222" }}>
                  <td style={{ padding: "12px", fontWeight: "bold" }}>{h.code}</td>
                  <td style={{ padding: "12px" }}>{h.name}</td>
                  <td style={{ padding: "12px", textAlign: "right" }}>{formatMoney(h.value)}</td>
                  <td style={{ padding: "12px", textAlign: "right" }}>{h.weight.toFixed(1)}%</td>
                  <td style={{
                    padding: "12px",
                    textAlign: "right",
                    color: h.return >= 0 ? "#4ade80" : "#f87171"
                  }}>
                    {h.return >= 0 ? "+" : ""}{h.return.toFixed(1)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {activeTab === "performance" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px" }}>
          {/* Best Performers */}
          <div style={{ background: "#1a1a2e", borderRadius: "12px", padding: "16px" }}>
            <h3 style={{ margin: "0 0 16px 0", color: "#4ade80" }}>Best Performers</h3>
            {bestPerformers.map((h) => (
              <div key={h.code} style={{
                display: "flex",
                justifyContent: "space-between",
                padding: "8px 0",
                borderBottom: "1px solid #222"
              }}>
                <span style={{ fontWeight: "bold" }}>{h.code}</span>
                <span style={{ color: "#4ade80" }}>+{h.return.toFixed(1)}%</span>
              </div>
            ))}
          </div>

          {/* Worst Performers */}
          <div style={{ background: "#1a1a2e", borderRadius: "12px", padding: "16px" }}>
            <h3 style={{ margin: "0 0 16px 0", color: "#f87171" }}>Worst Performers</h3>
            {worstPerformers.map((h) => (
              <div key={h.code} style={{
                display: "flex",
                justifyContent: "space-between",
                padding: "8px 0",
                borderBottom: "1px solid #222"
              }}>
                <span style={{ fontWeight: "bold" }}>{h.code}</span>
                <span style={{ color: h.return >= 0 ? "#4ade80" : "#f87171" }}>
                  {h.return >= 0 ? "+" : ""}{h.return.toFixed(1)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
'''

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            f.write(code)
        logger.info(f"Saved artifact code to {output_path}")

    return code


def export_artifact_json(portfolio: Portfolio, output_path: Path) -> Path:
    """
    Export just the JSON data for use in Claude Artifacts.

    Users can paste this data into their own React components.
    """
    data = export_artifact_data(portfolio)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)

    return output_path


# =============================================================================
# All-in-One Export Function
# =============================================================================

def export_visualizations(
    portfolio: Portfolio,
    output_dir: Path,
    formats: Optional[List[str]] = None,
) -> Dict[str, Path]:
    """
    Export portfolio data in multiple visualization formats.

    Args:
        portfolio: Portfolio to export
        output_dir: Directory for output files
        formats: List of formats to export. Options:
                 'sankey', 'flourish', 'plotly', 'treemap', 'sunburst', 'dashboard'
                 If None, exports all available formats.

    Returns:
        Dictionary mapping format names to file paths
    """
    if formats is None:
        formats = ["sankey", "flourish", "plotly", "treemap", "sunburst", "dashboard"]

    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results = {}

    if "sankey" in formats:
        path = output_dir / f"sankey_{timestamp}.txt"
        export_sankey_format(portfolio, path)
        results["sankey"] = path

        # Also export P/L version
        pl_path = output_dir / f"sankey_profitloss_{timestamp}.txt"
        export_sankey_profit_loss(portfolio, pl_path)
        results["sankey_profitloss"] = pl_path

    if "flourish" in formats:
        sankey_path = output_dir / f"flourish_sankey_{timestamp}.csv"
        export_flourish_sankey(portfolio, sankey_path)
        results["flourish_sankey"] = sankey_path

        treemap_path = output_dir / f"flourish_treemap_{timestamp}.csv"
        export_flourish_treemap(portfolio, treemap_path)
        results["flourish_treemap"] = treemap_path

    if PLOTLY_AVAILABLE:
        if "plotly" in formats or "sankey" in formats:
            path = output_dir / f"plotly_sankey_{timestamp}.html"
            create_plotly_sankey(portfolio, path)
            results["plotly_sankey"] = path

        if "treemap" in formats:
            path = output_dir / f"plotly_treemap_{timestamp}.html"
            create_plotly_treemap(portfolio, path)
            results["plotly_treemap"] = path

        if "sunburst" in formats:
            path = output_dir / f"plotly_sunburst_{timestamp}.html"
            create_plotly_sunburst(portfolio, path)
            results["plotly_sunburst"] = path

        if "dashboard" in formats:
            path = output_dir / f"plotly_dashboard_{timestamp}.html"
            create_plotly_dashboard(portfolio, path)
            results["dashboard"] = path

    return results
