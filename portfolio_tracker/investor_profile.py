"""
Investor Profile - Risk assessment questionnaire and profile management.

Features:
- 10-question risk profile assessment
- Retirement timeline calculation
- Risk score and profile classification
- Asset allocation recommendations
- Profile storage and retrieval
"""

import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import json

logger = logging.getLogger(__name__)


class RiskTolerance(Enum):
    """Risk tolerance levels."""
    VERY_CONSERVATIVE = "very_conservative"
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"
    VERY_AGGRESSIVE = "very_aggressive"


class InvestmentGoal(Enum):
    """Primary investment goals."""
    CAPITAL_PRESERVATION = "capital_preservation"
    INCOME = "income"
    BALANCED = "balanced"
    GROWTH = "growth"
    AGGRESSIVE_GROWTH = "aggressive_growth"


@dataclass
class Question:
    """A profile questionnaire question."""
    id: str
    text: str
    options: List[Tuple[str, int]]  # (option_text, score)
    category: str  # risk, timeline, financial


@dataclass
class InvestorProfile:
    """Complete investor profile."""
    id: Optional[int]
    name: str

    # Demographics
    age: int
    retirement_age: int

    # Questionnaire answers (question_id -> answer_index)
    answers: Dict[str, int]

    # Calculated scores
    risk_score: int  # 0-100
    timeline_score: int  # Years to retirement

    # Derived profile
    risk_tolerance: RiskTolerance
    investment_goal: InvestmentGoal

    # Recommended allocations
    recommended_stocks: int  # Percentage
    recommended_bonds: int
    recommended_cash: int
    recommended_property: int

    # Metadata
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    notes: str = ""

    @property
    def years_to_retirement(self) -> int:
        """Years until retirement."""
        return max(0, self.retirement_age - self.age)

    @property
    def investment_horizon(self) -> str:
        """Investment horizon category."""
        years = self.years_to_retirement
        if years <= 5:
            return "Short-term (0-5 years)"
        elif years <= 15:
            return "Medium-term (5-15 years)"
        else:
            return "Long-term (15+ years)"


# The 10 key questions for risk profiling
PROFILE_QUESTIONS: List[Question] = [
    Question(
        id="q1_age",
        text="What is your current age?",
        options=[
            ("Under 30", 10),
            ("30-39", 8),
            ("40-49", 6),
            ("50-59", 4),
            ("60-69", 2),
            ("70+", 1),
        ],
        category="timeline",
    ),
    Question(
        id="q2_retirement",
        text="At what age do you plan to retire (or access these investments)?",
        options=[
            ("Already retired / Within 5 years", 1),
            ("5-10 years", 3),
            ("10-20 years", 6),
            ("20-30 years", 8),
            ("30+ years", 10),
        ],
        category="timeline",
    ),
    Question(
        id="q3_experience",
        text="How would you describe your investment experience?",
        options=[
            ("None - I'm new to investing", 2),
            ("Limited - I've invested in term deposits/savings", 4),
            ("Moderate - I've invested in managed funds/ETFs", 6),
            ("Experienced - I actively manage a share portfolio", 8),
            ("Expert - I use advanced strategies (options, leverage, etc.)", 10),
        ],
        category="risk",
    ),
    Question(
        id="q4_income_stability",
        text="How stable is your current income?",
        options=[
            ("Very unstable - irregular/casual work", 2),
            ("Somewhat unstable - contract or variable income", 4),
            ("Stable - permanent employment", 6),
            ("Very stable - secure job or multiple income sources", 8),
            ("Not dependent on income - retired with sufficient assets", 7),
        ],
        category="financial",
    ),
    Question(
        id="q5_emergency_fund",
        text="How many months of expenses do you have in an emergency fund?",
        options=[
            ("None", 1),
            ("1-2 months", 3),
            ("3-5 months", 5),
            ("6-12 months", 8),
            ("More than 12 months", 10),
        ],
        category="financial",
    ),
    Question(
        id="q6_market_drop",
        text="If your portfolio dropped 20% in one month, what would you do?",
        options=[
            ("Sell everything immediately", 1),
            ("Sell some to reduce risk", 3),
            ("Hold and wait for recovery", 6),
            ("Buy more at the lower prices", 9),
            ("Significantly increase my position", 10),
        ],
        category="risk",
    ),
    Question(
        id="q7_goal_priority",
        text="What is your primary investment goal?",
        options=[
            ("Preserve capital - I can't afford any losses", 2),
            ("Generate income - I need regular dividends/interest", 4),
            ("Balanced growth and income", 6),
            ("Capital growth - I want my wealth to grow", 8),
            ("Maximum growth - I accept high risk for high returns", 10),
        ],
        category="risk",
    ),
    Question(
        id="q8_loss_tolerance",
        text="What is the maximum portfolio loss you could tolerate in a year?",
        options=[
            ("0% - I cannot accept any losses", 1),
            ("Up to 5%", 3),
            ("Up to 10%", 5),
            ("Up to 20%", 7),
            ("Up to 30%", 9),
            ("More than 30% for potential high returns", 10),
        ],
        category="risk",
    ),
    Question(
        id="q9_debt_level",
        text="What is your current debt situation (excluding home mortgage)?",
        options=[
            ("High debt - struggling to manage repayments", 2),
            ("Moderate debt - credit cards, car loans, etc.", 4),
            ("Low debt - small manageable debts", 6),
            ("Minimal - only a home mortgage", 8),
            ("Debt free", 10),
        ],
        category="financial",
    ),
    Question(
        id="q10_dependents",
        text="How many people are financially dependent on you?",
        options=[
            ("4 or more dependents", 3),
            ("2-3 dependents", 5),
            ("1 dependent (spouse/child)", 7),
            ("No dependents", 9),
        ],
        category="financial",
    ),
]


def calculate_risk_profile(answers: Dict[str, int]) -> Tuple[int, RiskTolerance, InvestmentGoal]:
    """
    Calculate risk score and profile from questionnaire answers.

    Returns (risk_score, risk_tolerance, investment_goal)
    """
    total_score = 0
    max_score = 0

    for question in PROFILE_QUESTIONS:
        if question.id in answers:
            answer_idx = answers[question.id]
            if 0 <= answer_idx < len(question.options):
                total_score += question.options[answer_idx][1]
        max_score += max(opt[1] for opt in question.options)

    # Normalize to 0-100
    risk_score = int((total_score / max_score) * 100) if max_score > 0 else 50

    # Determine risk tolerance
    if risk_score < 25:
        risk_tolerance = RiskTolerance.VERY_CONSERVATIVE
    elif risk_score < 40:
        risk_tolerance = RiskTolerance.CONSERVATIVE
    elif risk_score < 60:
        risk_tolerance = RiskTolerance.MODERATE
    elif risk_score < 80:
        risk_tolerance = RiskTolerance.AGGRESSIVE
    else:
        risk_tolerance = RiskTolerance.VERY_AGGRESSIVE

    # Determine investment goal based on answers
    goal_answer = answers.get("q7_goal_priority", 2)
    goals = [
        InvestmentGoal.CAPITAL_PRESERVATION,
        InvestmentGoal.INCOME,
        InvestmentGoal.BALANCED,
        InvestmentGoal.GROWTH,
        InvestmentGoal.AGGRESSIVE_GROWTH,
    ]
    investment_goal = goals[min(goal_answer, len(goals) - 1)]

    return risk_score, risk_tolerance, investment_goal


def calculate_allocation(
    risk_tolerance: RiskTolerance,
    years_to_retirement: int,
) -> Dict[str, int]:
    """
    Calculate recommended asset allocation based on risk tolerance and timeline.

    Uses a lifecycle approach with risk adjustment.
    """
    # Base allocation by risk tolerance
    base_allocations = {
        RiskTolerance.VERY_CONSERVATIVE: {"stocks": 20, "bonds": 50, "cash": 25, "property": 5},
        RiskTolerance.CONSERVATIVE: {"stocks": 35, "bonds": 40, "cash": 15, "property": 10},
        RiskTolerance.MODERATE: {"stocks": 50, "bonds": 30, "cash": 10, "property": 10},
        RiskTolerance.AGGRESSIVE: {"stocks": 70, "bonds": 15, "cash": 5, "property": 10},
        RiskTolerance.VERY_AGGRESSIVE: {"stocks": 85, "bonds": 5, "cash": 5, "property": 5},
    }

    allocation = base_allocations[risk_tolerance].copy()

    # Adjust based on time horizon (lifecycle approach)
    # Reduce stocks as retirement approaches
    if years_to_retirement <= 5:
        # Near retirement - reduce risk
        stock_reduction = min(20, allocation["stocks"] - 20)
        allocation["stocks"] -= stock_reduction
        allocation["bonds"] += stock_reduction // 2
        allocation["cash"] += stock_reduction - (stock_reduction // 2)
    elif years_to_retirement <= 10:
        # Medium term - slight reduction
        stock_reduction = min(10, allocation["stocks"] - 30)
        allocation["stocks"] -= stock_reduction
        allocation["bonds"] += stock_reduction
    elif years_to_retirement > 25:
        # Long term - can take more risk
        if allocation["stocks"] < 70:
            stock_increase = min(10, 70 - allocation["stocks"])
            allocation["stocks"] += stock_increase
            allocation["bonds"] -= stock_increase

    # Ensure allocations sum to 100
    total = sum(allocation.values())
    if total != 100:
        allocation["bonds"] += 100 - total

    return allocation


class InvestorProfileManager:
    """Manages investor profile storage and retrieval."""

    def __init__(self, db_path: Path):
        """Initialize with database path."""
        self.db_path = db_path
        self._init_database()

    def _init_database(self) -> None:
        """Initialize the profiles table."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS investor_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    age INTEGER NOT NULL,
                    retirement_age INTEGER NOT NULL,
                    answers TEXT NOT NULL,
                    risk_score INTEGER NOT NULL,
                    risk_tolerance TEXT NOT NULL,
                    investment_goal TEXT NOT NULL,
                    recommended_stocks INTEGER,
                    recommended_bonds INTEGER,
                    recommended_cash INTEGER,
                    recommended_property INTEGER,
                    notes TEXT DEFAULT '',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT
                )
            """)
            conn.commit()

    def save_profile(self, profile: InvestorProfile) -> int:
        """Save or update a profile. Returns profile ID."""
        with sqlite3.connect(self.db_path) as conn:
            if profile.id:
                # Update existing
                conn.execute("""
                    UPDATE investor_profiles SET
                        name = ?, age = ?, retirement_age = ?, answers = ?,
                        risk_score = ?, risk_tolerance = ?, investment_goal = ?,
                        recommended_stocks = ?, recommended_bonds = ?,
                        recommended_cash = ?, recommended_property = ?,
                        notes = ?, updated_at = ?
                    WHERE id = ?
                """, (
                    profile.name, profile.age, profile.retirement_age,
                    json.dumps(profile.answers), profile.risk_score,
                    profile.risk_tolerance.value, profile.investment_goal.value,
                    profile.recommended_stocks, profile.recommended_bonds,
                    profile.recommended_cash, profile.recommended_property,
                    profile.notes, datetime.now().isoformat(), profile.id,
                ))
                conn.commit()
                return profile.id
            else:
                # Insert new
                cursor = conn.execute("""
                    INSERT INTO investor_profiles (
                        name, age, retirement_age, answers, risk_score,
                        risk_tolerance, investment_goal, recommended_stocks,
                        recommended_bonds, recommended_cash, recommended_property, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    profile.name, profile.age, profile.retirement_age,
                    json.dumps(profile.answers), profile.risk_score,
                    profile.risk_tolerance.value, profile.investment_goal.value,
                    profile.recommended_stocks, profile.recommended_bonds,
                    profile.recommended_cash, profile.recommended_property,
                    profile.notes,
                ))
                conn.commit()
                return cursor.lastrowid

    def get_profile(self, profile_id: int = None) -> Optional[InvestorProfile]:
        """Get a profile by ID, or the latest profile if no ID specified."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            if profile_id:
                cursor = conn.execute(
                    "SELECT * FROM investor_profiles WHERE id = ?",
                    (profile_id,)
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM investor_profiles ORDER BY id DESC LIMIT 1"
                )

            row = cursor.fetchone()
            if row:
                return self._row_to_profile(row)
            return None

    def get_all_profiles(self) -> List[InvestorProfile]:
        """Get all profiles."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM investor_profiles ORDER BY created_at DESC"
            )
            return [self._row_to_profile(row) for row in cursor.fetchall()]

    def delete_profile(self, profile_id: int) -> bool:
        """Delete a profile."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM investor_profiles WHERE id = ?",
                (profile_id,)
            )
            conn.commit()
            return cursor.rowcount > 0

    def _row_to_profile(self, row: sqlite3.Row) -> InvestorProfile:
        """Convert database row to InvestorProfile."""
        return InvestorProfile(
            id=row["id"],
            name=row["name"],
            age=row["age"],
            retirement_age=row["retirement_age"],
            answers=json.loads(row["answers"]),
            risk_score=row["risk_score"],
            timeline_score=row["retirement_age"] - row["age"],
            risk_tolerance=RiskTolerance(row["risk_tolerance"]),
            investment_goal=InvestmentGoal(row["investment_goal"]),
            recommended_stocks=row["recommended_stocks"],
            recommended_bonds=row["recommended_bonds"],
            recommended_cash=row["recommended_cash"],
            recommended_property=row["recommended_property"],
            notes=row["notes"] or "",
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
            updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else None,
        )


def run_questionnaire(input_func=None) -> Tuple[Dict[str, int], int, int]:
    """
    Run the interactive questionnaire.

    Returns (answers_dict, age, retirement_age).
    Uses input_func for testing (defaults to built-in input).
    """
    if input_func is None:
        input_func = input

    print("\n" + "=" * 70)
    print("INVESTOR PROFILE QUESTIONNAIRE")
    print("=" * 70)
    print("\nAnswer these 10 questions to determine your risk profile")
    print("and receive personalized investment recommendations.\n")

    answers = {}
    age = 0
    retirement_age = 0

    for i, question in enumerate(PROFILE_QUESTIONS, 1):
        print(f"\n{'-' * 60}")
        print(f"Question {i}/10: {question.text}")
        print(f"{'-' * 60}")

        for j, (option_text, _) in enumerate(question.options, 1):
            print(f"  {j}. {option_text}")

        while True:
            try:
                response = input_func(f"\nYour answer (1-{len(question.options)}): ").strip()
                choice = int(response)
                if 1 <= choice <= len(question.options):
                    answers[question.id] = choice - 1  # Store 0-indexed

                    # Extract age from first question
                    if question.id == "q1_age":
                        age_ranges = [25, 35, 45, 55, 65, 75]
                        age = age_ranges[choice - 1]

                    # Extract retirement age from second question
                    if question.id == "q2_retirement":
                        retirement_offsets = [0, 7, 15, 25, 35]
                        retirement_age = age + retirement_offsets[choice - 1]

                    break
                else:
                    print(f"Please enter a number between 1 and {len(question.options)}")
            except ValueError:
                print("Please enter a valid number")

    # Ask for specific age if they want
    print(f"\n{'-' * 60}")
    refine = input_func("\nWould you like to enter your exact age? (y/n): ").strip().lower()
    if refine == 'y':
        while True:
            try:
                age = int(input_func("Your current age: ").strip())
                if 18 <= age <= 100:
                    break
                print("Please enter an age between 18 and 100")
            except ValueError:
                print("Please enter a valid number")

        while True:
            try:
                retirement_age = int(input_func("Your planned retirement age: ").strip())
                if retirement_age >= age:
                    break
                print("Retirement age must be greater than or equal to current age")
            except ValueError:
                print("Please enter a valid number")

    return answers, age, retirement_age


def create_profile_from_answers(
    name: str,
    answers: Dict[str, int],
    age: int,
    retirement_age: int,
    notes: str = "",
) -> InvestorProfile:
    """Create an InvestorProfile from questionnaire answers."""
    # Calculate risk profile
    risk_score, risk_tolerance, investment_goal = calculate_risk_profile(answers)

    # Calculate recommended allocation
    years_to_retirement = max(0, retirement_age - age)
    allocation = calculate_allocation(risk_tolerance, years_to_retirement)

    return InvestorProfile(
        id=None,
        name=name,
        age=age,
        retirement_age=retirement_age,
        answers=answers,
        risk_score=risk_score,
        timeline_score=years_to_retirement,
        risk_tolerance=risk_tolerance,
        investment_goal=investment_goal,
        recommended_stocks=allocation["stocks"],
        recommended_bonds=allocation["bonds"],
        recommended_cash=allocation["cash"],
        recommended_property=allocation["property"],
        notes=notes,
    )


def format_profile_summary(profile: InvestorProfile) -> str:
    """Format profile as a summary report."""
    lines = []

    lines.append("=" * 70)
    lines.append(f"INVESTOR PROFILE: {profile.name.upper()}")
    lines.append("=" * 70)

    # Demographics
    lines.append(f"\n{'DEMOGRAPHICS':-^70}")
    lines.append(f"  Age:                    {profile.age}")
    lines.append(f"  Retirement Age:         {profile.retirement_age}")
    lines.append(f"  Years to Retirement:    {profile.years_to_retirement}")
    lines.append(f"  Investment Horizon:     {profile.investment_horizon}")

    # Risk Profile
    lines.append(f"\n{'RISK PROFILE':-^70}")

    # Risk score bar
    score = profile.risk_score
    bar_width = 40
    filled = int(score / 100 * bar_width)
    bar = "█" * filled + "░" * (bar_width - filled)
    lines.append(f"  Risk Score:             [{bar}] {score}/100")

    tolerance_display = profile.risk_tolerance.value.replace("_", " ").title()
    lines.append(f"  Risk Tolerance:         {tolerance_display}")

    goal_display = profile.investment_goal.value.replace("_", " ").title()
    lines.append(f"  Investment Goal:        {goal_display}")

    # Recommended Allocation
    lines.append(f"\n{'RECOMMENDED ASSET ALLOCATION':-^70}")
    lines.append("")

    allocations = [
        ("Australian Shares", profile.recommended_stocks, "█"),
        ("Bonds/Fixed Income", profile.recommended_bonds, "▓"),
        ("Cash/Term Deposits", profile.recommended_cash, "░"),
        ("Property/REITs", profile.recommended_property, "▒"),
    ]

    for asset, pct, char in allocations:
        bar_len = pct // 2
        bar = char * bar_len
        lines.append(f"  {asset:<22} {bar:<25} {pct:>3}%")

    lines.append("")
    lines.append(f"  {'─' * 50}")
    lines.append(f"  Total                                            100%")

    # Visual pie representation
    lines.append(f"\n{'ALLOCATION BREAKDOWN':-^70}")
    lines.append("")

    total_width = 50
    stocks_w = int(profile.recommended_stocks / 100 * total_width)
    bonds_w = int(profile.recommended_bonds / 100 * total_width)
    cash_w = int(profile.recommended_cash / 100 * total_width)
    property_w = total_width - stocks_w - bonds_w - cash_w

    bar = "█" * stocks_w + "▓" * bonds_w + "░" * cash_w + "▒" * property_w
    lines.append(f"  [{bar}]")
    lines.append(f"   █ Stocks  ▓ Bonds  ░ Cash  ▒ Property")

    # Profile interpretation
    lines.append(f"\n{'PROFILE INTERPRETATION':-^70}")
    lines.append("")

    interpretations = get_profile_interpretation(profile)
    for line in interpretations:
        lines.append(f"  • {line}")

    # Recommendations
    lines.append(f"\n{'RECOMMENDATIONS':-^70}")
    lines.append("")

    recommendations = get_recommendations(profile)
    for rec in recommendations:
        lines.append(f"  → {rec}")

    if profile.notes:
        lines.append(f"\n{'NOTES':-^70}")
        lines.append(f"  {profile.notes}")

    if profile.created_at:
        lines.append(f"\n  Profile created: {profile.created_at.strftime('%Y-%m-%d %H:%M')}")

    lines.append("")

    return "\n".join(lines)


def get_profile_interpretation(profile: InvestorProfile) -> List[str]:
    """Get interpretation text based on profile."""
    interpretations = []

    # Risk interpretation
    if profile.risk_tolerance == RiskTolerance.VERY_CONSERVATIVE:
        interpretations.append(
            "You have a very low risk tolerance. Capital preservation is your priority."
        )
    elif profile.risk_tolerance == RiskTolerance.CONSERVATIVE:
        interpretations.append(
            "You prefer lower-risk investments with steady, predictable returns."
        )
    elif profile.risk_tolerance == RiskTolerance.MODERATE:
        interpretations.append(
            "You're comfortable with moderate risk for balanced growth and stability."
        )
    elif profile.risk_tolerance == RiskTolerance.AGGRESSIVE:
        interpretations.append(
            "You accept higher volatility in pursuit of above-average returns."
        )
    else:
        interpretations.append(
            "You have a high risk tolerance and seek maximum growth potential."
        )

    # Timeline interpretation
    years = profile.years_to_retirement
    if years <= 5:
        interpretations.append(
            "With retirement near, focus shifts to capital preservation and income."
        )
    elif years <= 10:
        interpretations.append(
            "A medium-term horizon allows for moderate growth with some protection."
        )
    elif years <= 20:
        interpretations.append(
            "Your timeline allows for recovery from market downturns."
        )
    else:
        interpretations.append(
            "A long investment horizon allows you to ride out market volatility."
        )

    # Goal interpretation
    if profile.investment_goal == InvestmentGoal.INCOME:
        interpretations.append(
            "Focus on dividend-paying stocks and bonds for regular income."
        )
    elif profile.investment_goal == InvestmentGoal.GROWTH:
        interpretations.append(
            "Growth-oriented portfolio with reinvested dividends."
        )
    elif profile.investment_goal == InvestmentGoal.BALANCED:
        interpretations.append(
            "A mix of growth and income investments suits your goals."
        )

    return interpretations


def get_recommendations(profile: InvestorProfile) -> List[str]:
    """Get actionable recommendations based on profile."""
    recommendations = []

    years = profile.years_to_retirement

    # ETF suggestions based on allocation
    if profile.recommended_stocks >= 50:
        recommendations.append(
            f"Consider broad market ETFs like VAS (ASX 300) or A200 for {profile.recommended_stocks}% equity exposure"
        )

    if profile.recommended_bonds >= 20:
        recommendations.append(
            f"Bond ETFs like VAF or IAF can provide your {profile.recommended_bonds}% fixed income allocation"
        )

    if profile.recommended_property >= 10:
        recommendations.append(
            f"A-REITs or property ETFs (VAP) for your {profile.recommended_property}% property allocation"
        )

    # Timeline-specific advice
    if years <= 5:
        recommendations.append(
            "Consider shifting towards defensive sectors (utilities, healthcare, consumer staples)"
        )
        recommendations.append(
            "Build a cash buffer of 2-3 years of retirement expenses"
        )
    elif years <= 15:
        recommendations.append(
            "Begin gradually reducing growth stock exposure as retirement approaches"
        )
    else:
        recommendations.append(
            "Maximize growth exposure while you have time to recover from downturns"
        )

    # Goal-specific advice
    if profile.investment_goal in (InvestmentGoal.INCOME, InvestmentGoal.CAPITAL_PRESERVATION):
        recommendations.append(
            "Focus on fully-franked dividends for tax-effective income"
        )

    # Diversification
    recommendations.append(
        "Ensure diversification across at least 20+ individual holdings or use diversified ETFs"
    )

    return recommendations


def compare_portfolio_to_profile(
    profile: InvestorProfile,
    portfolio_allocation: Dict[str, float],
) -> Dict[str, Any]:
    """
    Compare actual portfolio allocation to recommended allocation.

    Returns comparison with suggested adjustments.
    """
    recommended = {
        "stocks": profile.recommended_stocks,
        "bonds": profile.recommended_bonds,
        "cash": profile.recommended_cash,
        "property": profile.recommended_property,
    }

    # Calculate differences
    differences = {}
    adjustments = []
    total_adjustment = Decimal("0")

    for asset, target in recommended.items():
        actual = portfolio_allocation.get(asset, 0)
        diff = actual - target
        differences[asset] = {
            "actual": actual,
            "target": target,
            "difference": diff,
            "status": "overweight" if diff > 5 else "underweight" if diff < -5 else "on target",
        }

        if abs(diff) > 5:
            action = "reduce" if diff > 0 else "increase"
            adjustments.append({
                "asset": asset,
                "action": action,
                "amount": abs(diff),
            })

    return {
        "profile_name": profile.name,
        "risk_tolerance": profile.risk_tolerance.value,
        "differences": differences,
        "adjustments": adjustments,
        "aligned": len(adjustments) == 0,
    }
