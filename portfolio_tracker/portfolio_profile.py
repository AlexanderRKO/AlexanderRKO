"""
Portfolio Profile Analyzer - Analyze portfolio for investment style and risk profile.

Determines if a portfolio is:
- Conservative (income-focused, low volatility)
- Balanced (mix of growth and income)
- Growth (capital appreciation focused)
- Aggressive (high risk, high reward)

Also provides:
- Risk metrics and scores
- Sector balance analysis
- Concentration risk
- Rebalancing suggestions
- Target allocation comparison
"""

import logging
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum

from .models import Portfolio, Holding, AssetClass, Sector
from .sector_lookup import get_sector, get_sector_summary

logger = logging.getLogger(__name__)


class RiskProfile(Enum):
    """Portfolio risk profile classifications."""
    CONSERVATIVE = "conservative"
    MODERATELY_CONSERVATIVE = "moderately_conservative"
    BALANCED = "balanced"
    GROWTH = "growth"
    AGGRESSIVE = "aggressive"


class InvestmentStyle(Enum):
    """Investment style classifications."""
    INCOME = "income"
    VALUE = "value"
    GROWTH = "growth"
    BLEND = "blend"
    SPECULATIVE = "speculative"


@dataclass
class SectorScore:
    """Risk/style score for a sector."""
    name: str
    weight: Decimal
    risk_score: int  # 1-10 (1=safest)
    income_score: int  # 1-10 (10=highest income)
    growth_score: int  # 1-10 (10=highest growth)
    contribution_to_risk: Decimal


@dataclass
class ProfileMetrics:
    """Detailed profile metrics."""
    # Overall scores (0-100)
    risk_score: int
    income_score: int
    growth_score: int
    diversification_score: int
    concentration_score: int

    # Profile classification
    risk_profile: RiskProfile
    investment_style: InvestmentStyle

    # Sector analysis
    sector_scores: List[SectorScore]

    # Risk factors
    risk_factors: List[str]
    strengths: List[str]

    # Target comparison
    target_allocation: Optional[Dict[str, Decimal]] = None
    allocation_drift: Optional[Dict[str, Decimal]] = None


@dataclass
class RebalanceSuggestion:
    """A single rebalancing suggestion."""
    action: str  # "buy", "sell", "reduce", "increase"
    code: Optional[str]
    sector: Optional[str]
    current_weight: Decimal
    target_weight: Decimal
    difference: Decimal
    reason: str
    priority: int  # 1=highest


@dataclass
class PortfolioProfile:
    """Complete portfolio profile analysis."""
    snapshot_date: date
    portfolio_value: Decimal
    metrics: ProfileMetrics
    rebalance_suggestions: List[RebalanceSuggestion]
    profile_summary: str
    detailed_analysis: Dict[str, Any]


# Sector risk and style scores (based on historical volatility and characteristics)
SECTOR_CHARACTERISTICS = {
    "Financials": {"risk": 5, "income": 8, "growth": 4},
    "Materials": {"risk": 7, "income": 4, "growth": 6},
    "Healthcare": {"risk": 5, "income": 3, "growth": 7},
    "Energy": {"risk": 8, "income": 5, "growth": 5},
    "Consumer Discretionary": {"risk": 6, "income": 3, "growth": 7},
    "Consumer Staples": {"risk": 3, "income": 6, "growth": 4},
    "Industrials": {"risk": 5, "income": 4, "growth": 5},
    "Technology": {"risk": 8, "income": 1, "growth": 9},
    "Real Estate": {"risk": 5, "income": 8, "growth": 3},
    "Utilities": {"risk": 3, "income": 7, "growth": 2},
    "Communication Services": {"risk": 6, "income": 4, "growth": 6},
    "ETF - Diversified": {"risk": 3, "income": 5, "growth": 5},
    "ETF - Fixed Income": {"risk": 2, "income": 7, "growth": 1},
    "ETF - International": {"risk": 5, "income": 4, "growth": 6},
    "Cash": {"risk": 1, "income": 3, "growth": 1},
    "Other": {"risk": 5, "income": 4, "growth": 5},
}

# Target allocations for different profiles
TARGET_ALLOCATIONS = {
    RiskProfile.CONSERVATIVE: {
        "Financials": Decimal("15"),
        "Real Estate": Decimal("10"),
        "Utilities": Decimal("10"),
        "Consumer Staples": Decimal("10"),
        "Healthcare": Decimal("10"),
        "ETF - Diversified": Decimal("20"),
        "ETF - Fixed Income": Decimal("15"),
        "Cash": Decimal("10"),
    },
    RiskProfile.BALANCED: {
        "Financials": Decimal("15"),
        "Healthcare": Decimal("12"),
        "Technology": Decimal("10"),
        "Consumer Discretionary": Decimal("8"),
        "Consumer Staples": Decimal("8"),
        "Real Estate": Decimal("8"),
        "Industrials": Decimal("8"),
        "ETF - Diversified": Decimal("15"),
        "Materials": Decimal("8"),
        "Other": Decimal("8"),
    },
    RiskProfile.GROWTH: {
        "Technology": Decimal("20"),
        "Healthcare": Decimal("15"),
        "Consumer Discretionary": Decimal("12"),
        "Financials": Decimal("12"),
        "Industrials": Decimal("10"),
        "Materials": Decimal("10"),
        "ETF - International": Decimal("10"),
        "Communication Services": Decimal("6"),
        "Other": Decimal("5"),
    },
    RiskProfile.AGGRESSIVE: {
        "Technology": Decimal("30"),
        "Healthcare": Decimal("15"),
        "Consumer Discretionary": Decimal("15"),
        "Materials": Decimal("10"),
        "Energy": Decimal("10"),
        "ETF - International": Decimal("10"),
        "Industrials": Decimal("10"),
    },
}


def calculate_concentration_risk(portfolio: Portfolio) -> Tuple[int, List[str]]:
    """
    Calculate concentration risk score.

    Returns (score 0-100, list of risk factors)
    """
    factors = []

    # Check top holding concentration
    top_holding = max(portfolio.holdings, key=lambda h: h.market_value, default=None)
    if top_holding:
        top_weight = float(top_holding.portfolio_weight)
        if top_weight > 20:
            factors.append(f"Top holding ({top_holding.code}) is {top_weight:.1f}% - very concentrated")
        elif top_weight > 15:
            factors.append(f"Top holding ({top_holding.code}) is {top_weight:.1f}% - moderately concentrated")

    # Check top 5 concentration
    top_5 = sorted(portfolio.holdings, key=lambda h: h.market_value, reverse=True)[:5]
    top_5_weight = sum(float(h.portfolio_weight) for h in top_5)
    if top_5_weight > 60:
        factors.append(f"Top 5 holdings are {top_5_weight:.0f}% of portfolio")

    # Check sector concentration
    sectors = get_sector_summary(portfolio)
    for sector_name, data in sectors.items():
        if data["weight"] > 40:
            factors.append(f"{sector_name} sector is {data['weight']:.0f}% - over-concentrated")
        elif data["weight"] > 30:
            factors.append(f"{sector_name} sector is {data['weight']:.0f}% - high exposure")

    # Score: 100 = well diversified, 0 = highly concentrated
    score = 100
    if top_weight > 20:
        score -= 30
    elif top_weight > 15:
        score -= 15
    elif top_weight > 10:
        score -= 5

    if top_5_weight > 70:
        score -= 25
    elif top_5_weight > 60:
        score -= 15
    elif top_5_weight > 50:
        score -= 5

    # Number of holdings factor
    if portfolio.holding_count < 5:
        score -= 20
        factors.append(f"Only {portfolio.holding_count} holdings - consider more diversification")
    elif portfolio.holding_count < 10:
        score -= 10

    return max(0, min(100, score)), factors


def calculate_sector_scores(portfolio: Portfolio) -> List[SectorScore]:
    """Calculate risk and style scores for each sector in portfolio."""
    sectors = get_sector_summary(portfolio)
    scores = []

    for sector_name, data in sectors.items():
        chars = SECTOR_CHARACTERISTICS.get(sector_name, SECTOR_CHARACTERISTICS["Other"])
        weight = Decimal(str(data["weight"]))

        # Contribution to overall risk = weight * sector_risk
        contribution = weight * Decimal(str(chars["risk"])) / 100

        scores.append(SectorScore(
            name=sector_name,
            weight=weight,
            risk_score=chars["risk"],
            income_score=chars["income"],
            growth_score=chars["growth"],
            contribution_to_risk=contribution,
        ))

    return sorted(scores, key=lambda x: x.weight, reverse=True)


def determine_risk_profile(
    risk_score: int,
    income_score: int,
    growth_score: int,
) -> RiskProfile:
    """Determine overall risk profile from scores."""
    if risk_score <= 25:
        return RiskProfile.CONSERVATIVE
    elif risk_score <= 40:
        return RiskProfile.MODERATELY_CONSERVATIVE
    elif risk_score <= 55:
        return RiskProfile.BALANCED
    elif risk_score <= 70:
        return RiskProfile.GROWTH
    else:
        return RiskProfile.AGGRESSIVE


def determine_investment_style(
    income_score: int,
    growth_score: int,
    portfolio: Portfolio,
) -> InvestmentStyle:
    """Determine investment style from scores."""
    # Check dividend yield
    # For now, use a simple heuristic based on sector exposure

    sectors = get_sector_summary(portfolio)

    # Income-oriented sectors
    income_sectors = ["Real Estate", "Utilities", "Financials", "ETF - Fixed Income"]
    income_weight = sum(
        sectors.get(s, {}).get("weight", 0)
        for s in income_sectors
    )

    # Growth-oriented sectors
    growth_sectors = ["Technology", "Healthcare", "Consumer Discretionary"]
    growth_weight = sum(
        sectors.get(s, {}).get("weight", 0)
        for s in growth_sectors
    )

    if income_weight > 50:
        return InvestmentStyle.INCOME
    elif growth_weight > 50:
        return InvestmentStyle.GROWTH
    elif income_score > growth_score + 20:
        return InvestmentStyle.VALUE
    elif growth_score > income_score + 20:
        return InvestmentStyle.GROWTH
    else:
        return InvestmentStyle.BLEND


def analyze_portfolio_profile(portfolio: Portfolio) -> PortfolioProfile:
    """
    Perform complete portfolio profile analysis.
    """
    sector_scores = calculate_sector_scores(portfolio)

    # Calculate weighted scores
    total_weight = sum(float(s.weight) for s in sector_scores)
    if total_weight == 0:
        total_weight = 1

    risk_score = int(sum(
        float(s.weight) * s.risk_score for s in sector_scores
    ) / total_weight * 10)

    income_score = int(sum(
        float(s.weight) * s.income_score for s in sector_scores
    ) / total_weight * 10)

    growth_score = int(sum(
        float(s.weight) * s.growth_score for s in sector_scores
    ) / total_weight * 10)

    # Calculate concentration and diversification
    concentration_score, risk_factors = calculate_concentration_risk(portfolio)
    diversification_score = concentration_score  # They're related

    # Determine profile and style
    risk_profile = determine_risk_profile(risk_score, income_score, growth_score)
    investment_style = determine_investment_style(income_score, growth_score, portfolio)

    # Identify strengths
    strengths = []
    if diversification_score >= 80:
        strengths.append("Well diversified across multiple holdings")
    if len(sector_scores) >= 6:
        strengths.append(f"Good sector spread ({len(sector_scores)} sectors)")
    if portfolio.holding_count >= 15:
        strengths.append(f"Solid holding count ({portfolio.holding_count} positions)")

    # Check for balanced exposure
    sectors = get_sector_summary(portfolio)
    max_sector_weight = max((s["weight"] for s in sectors.values()), default=0)
    if max_sector_weight <= 25:
        strengths.append("No single sector dominates portfolio")

    # Get target allocation for this profile
    target_allocation = TARGET_ALLOCATIONS.get(risk_profile, {})

    # Calculate drift from target
    allocation_drift = {}
    for sector_name, target in target_allocation.items():
        current = Decimal(str(sectors.get(sector_name, {}).get("weight", 0)))
        allocation_drift[sector_name] = current - target

    metrics = ProfileMetrics(
        risk_score=risk_score,
        income_score=income_score,
        growth_score=growth_score,
        diversification_score=diversification_score,
        concentration_score=100 - concentration_score,  # Invert for "concentration" (higher = more concentrated)
        risk_profile=risk_profile,
        investment_style=investment_style,
        sector_scores=sector_scores,
        risk_factors=risk_factors,
        strengths=strengths,
        target_allocation=target_allocation,
        allocation_drift=allocation_drift,
    )

    # Generate rebalancing suggestions
    suggestions = generate_rebalance_suggestions(portfolio, metrics)

    # Generate summary
    profile_summary = generate_profile_summary(metrics, portfolio)

    # Detailed analysis
    detailed = {
        "sector_breakdown": {s.name: float(s.weight) for s in sector_scores},
        "risk_contributors": [
            {"sector": s.name, "contribution": float(s.contribution_to_risk)}
            for s in sorted(sector_scores, key=lambda x: x.contribution_to_risk, reverse=True)[:5]
        ],
        "holding_count": portfolio.holding_count,
        "profitable_holdings": len([h for h in portfolio.holdings if h.profit_loss >= 0]),
    }

    return PortfolioProfile(
        snapshot_date=portfolio.snapshot_date,
        portfolio_value=portfolio.total_market_value,
        metrics=metrics,
        rebalance_suggestions=suggestions,
        profile_summary=profile_summary,
        detailed_analysis=detailed,
    )


def generate_rebalance_suggestions(
    portfolio: Portfolio,
    metrics: ProfileMetrics,
) -> List[RebalanceSuggestion]:
    """Generate actionable rebalancing suggestions."""
    suggestions = []
    sectors = get_sector_summary(portfolio)

    # Check for overweight sectors
    for sector_name, data in sectors.items():
        weight = Decimal(str(data["weight"]))

        if weight > 35:
            suggestions.append(RebalanceSuggestion(
                action="reduce",
                code=None,
                sector=sector_name,
                current_weight=weight,
                target_weight=Decimal("25"),
                difference=weight - Decimal("25"),
                reason=f"{sector_name} is significantly overweight at {weight:.0f}%",
                priority=1,
            ))
        elif weight > 25:
            suggestions.append(RebalanceSuggestion(
                action="reduce",
                code=None,
                sector=sector_name,
                current_weight=weight,
                target_weight=Decimal("20"),
                difference=weight - Decimal("20"),
                reason=f"Consider reducing {sector_name} exposure ({weight:.0f}%)",
                priority=2,
            ))

    # Check for underweight defensive sectors (for balanced profiles)
    if metrics.risk_profile in (RiskProfile.BALANCED, RiskProfile.MODERATELY_CONSERVATIVE):
        defensive_sectors = ["Consumer Staples", "Utilities", "Healthcare"]
        defensive_weight = sum(
            sectors.get(s, {}).get("weight", 0)
            for s in defensive_sectors
        )
        if defensive_weight < 15:
            suggestions.append(RebalanceSuggestion(
                action="increase",
                code=None,
                sector="Defensive sectors",
                current_weight=Decimal(str(defensive_weight)),
                target_weight=Decimal("20"),
                difference=Decimal("20") - Decimal(str(defensive_weight)),
                reason="Consider adding defensive sector exposure for balance",
                priority=2,
            ))

    # Check individual holding concentration
    for holding in portfolio.holdings:
        if holding.portfolio_weight > 15:
            suggestions.append(RebalanceSuggestion(
                action="reduce",
                code=holding.code,
                sector=None,
                current_weight=holding.portfolio_weight,
                target_weight=Decimal("10"),
                difference=holding.portfolio_weight - Decimal("10"),
                reason=f"{holding.code} is {float(holding.portfolio_weight):.1f}% of portfolio - consider trimming",
                priority=1,
            ))

    # Check for missing sector diversity
    covered_sectors = set(sectors.keys())
    important_sectors = {"Financials", "Healthcare", "Technology", "Consumer Staples"}
    missing = important_sectors - covered_sectors

    for sector in missing:
        if metrics.risk_profile != RiskProfile.CONSERVATIVE or sector != "Technology":
            suggestions.append(RebalanceSuggestion(
                action="buy",
                code=None,
                sector=sector,
                current_weight=Decimal("0"),
                target_weight=Decimal("8"),
                difference=Decimal("8"),
                reason=f"No {sector} exposure - consider adding for diversification",
                priority=3,
            ))

    return sorted(suggestions, key=lambda x: x.priority)


def generate_profile_summary(metrics: ProfileMetrics, portfolio: Portfolio) -> str:
    """Generate a human-readable profile summary."""
    profile_names = {
        RiskProfile.CONSERVATIVE: "Conservative",
        RiskProfile.MODERATELY_CONSERVATIVE: "Moderately Conservative",
        RiskProfile.BALANCED: "Balanced",
        RiskProfile.GROWTH: "Growth",
        RiskProfile.AGGRESSIVE: "Aggressive",
    }

    style_names = {
        InvestmentStyle.INCOME: "income-focused",
        InvestmentStyle.VALUE: "value-oriented",
        InvestmentStyle.GROWTH: "growth-oriented",
        InvestmentStyle.BLEND: "blended",
        InvestmentStyle.SPECULATIVE: "speculative",
    }

    profile_name = profile_names.get(metrics.risk_profile, "Unknown")
    style_name = style_names.get(metrics.investment_style, "mixed")

    summary = f"Your portfolio has a {profile_name} risk profile with a {style_name} investment style. "

    if metrics.diversification_score >= 80:
        summary += "It is well diversified. "
    elif metrics.diversification_score >= 60:
        summary += "Diversification is adequate but could be improved. "
    else:
        summary += "Concentration risk is elevated - consider diversifying. "

    if metrics.risk_factors:
        summary += f"Key considerations: {metrics.risk_factors[0].lower()}"

    return summary


def format_portfolio_profile(profile: PortfolioProfile) -> str:
    """Format portfolio profile for terminal display."""
    lines = []

    lines.append("=" * 70)
    lines.append("PORTFOLIO PROFILE ANALYSIS")
    lines.append("=" * 70)

    # Profile badge
    profile_emoji = {
        RiskProfile.CONSERVATIVE: "🛡️",
        RiskProfile.MODERATELY_CONSERVATIVE: "⚖️",
        RiskProfile.BALANCED: "⚖️",
        RiskProfile.GROWTH: "📈",
        RiskProfile.AGGRESSIVE: "🚀",
    }

    emoji = profile_emoji.get(profile.metrics.risk_profile, "📊")
    profile_name = profile.metrics.risk_profile.value.replace("_", " ").title()
    style_name = profile.metrics.investment_style.value.title()

    lines.append("")
    lines.append(f"  {emoji} Profile: {profile_name}")
    lines.append(f"  📊 Style: {style_name}")
    lines.append(f"  💰 Value: ${float(profile.portfolio_value):,.0f}")
    lines.append("")

    # Summary
    lines.append("-" * 70)
    lines.append("SUMMARY")
    lines.append("-" * 70)
    lines.append(f"  {profile.profile_summary}")
    lines.append("")

    # Scores
    lines.append("-" * 70)
    lines.append("PROFILE SCORES")
    lines.append("-" * 70)

    def score_bar(score: int, label: str) -> str:
        filled = int(score / 10)
        empty = 10 - filled
        bar = "█" * filled + "░" * empty
        return f"  {label:<20} [{bar}] {score}/100"

    lines.append(score_bar(profile.metrics.risk_score, "Risk Level"))
    lines.append(score_bar(profile.metrics.income_score, "Income Focus"))
    lines.append(score_bar(profile.metrics.growth_score, "Growth Focus"))
    lines.append(score_bar(profile.metrics.diversification_score, "Diversification"))
    lines.append("")

    # Sector Exposure
    lines.append("-" * 70)
    lines.append("SECTOR EXPOSURE & RISK CONTRIBUTION")
    lines.append("-" * 70)
    lines.append(f"  {'Sector':<25} {'Weight':>8} {'Risk':>6} {'Income':>6} {'Growth':>6}")
    lines.append("  " + "-" * 55)

    for sector in profile.metrics.sector_scores[:8]:
        lines.append(
            f"  {sector.name:<25} {float(sector.weight):>7.1f}% "
            f"{sector.risk_score:>5}/10 {sector.income_score:>5}/10 {sector.growth_score:>5}/10"
        )
    lines.append("")

    # Strengths
    if profile.metrics.strengths:
        lines.append("-" * 70)
        lines.append("✓ STRENGTHS")
        lines.append("-" * 70)
        for strength in profile.metrics.strengths:
            lines.append(f"  • {strength}")
        lines.append("")

    # Risk Factors
    if profile.metrics.risk_factors:
        lines.append("-" * 70)
        lines.append("⚠️ RISK FACTORS")
        lines.append("-" * 70)
        for factor in profile.metrics.risk_factors:
            lines.append(f"  • {factor}")
        lines.append("")

    # Rebalancing Suggestions
    if profile.rebalance_suggestions:
        lines.append("-" * 70)
        lines.append("📋 REBALANCING SUGGESTIONS")
        lines.append("-" * 70)

        for i, suggestion in enumerate(profile.rebalance_suggestions[:5], 1):
            priority_marker = "❗" if suggestion.priority == 1 else "➤"
            if suggestion.code:
                target = suggestion.code
            else:
                target = suggestion.sector or "Portfolio"

            lines.append(f"  {priority_marker} {suggestion.reason}")
        lines.append("")

    return "\n".join(lines)


def get_profile_comparison(
    portfolio: Portfolio,
    target_profile: RiskProfile,
) -> Dict[str, Any]:
    """
    Compare current portfolio to a target risk profile.

    Returns allocation differences and required changes.
    """
    current = analyze_portfolio_profile(portfolio)
    target_allocation = TARGET_ALLOCATIONS.get(target_profile, {})
    current_sectors = get_sector_summary(portfolio)

    changes = []
    for sector, target_weight in target_allocation.items():
        current_weight = Decimal(str(current_sectors.get(sector, {}).get("weight", 0)))
        diff = target_weight - current_weight

        if abs(diff) > 5:  # Only significant differences
            action = "increase" if diff > 0 else "decrease"
            dollar_change = float(diff) / 100 * float(portfolio.total_market_value)

            changes.append({
                "sector": sector,
                "current": float(current_weight),
                "target": float(target_weight),
                "difference": float(diff),
                "action": action,
                "dollar_amount": abs(dollar_change),
            })

    return {
        "current_profile": current.metrics.risk_profile.value,
        "target_profile": target_profile.value,
        "changes_required": sorted(changes, key=lambda x: abs(x["difference"]), reverse=True),
        "total_rebalance_amount": sum(c["dollar_amount"] for c in changes) / 2,  # Each move is counted twice
    }
