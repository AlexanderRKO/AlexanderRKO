"""
Goal Tracker - Set and track portfolio goals.

Features:
- Portfolio value targets
- Dividend income goals
- Sector allocation targets
- Savings milestones
- Time-based goal tracking
- Progress visualization
"""

import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import json

from .models import Portfolio, Holding

logger = logging.getLogger(__name__)


class GoalType(Enum):
    """Types of portfolio goals."""
    PORTFOLIO_VALUE = "portfolio_value"
    DIVIDEND_INCOME = "dividend_income"
    MONTHLY_INCOME = "monthly_income"
    HOLDING_VALUE = "holding_value"
    SECTOR_ALLOCATION = "sector_allocation"
    SAVINGS_MILESTONE = "savings_milestone"
    SHARES_OWNED = "shares_owned"
    YIELD_TARGET = "yield_target"
    CUSTOM = "custom"


class GoalStatus(Enum):
    """Status of a goal."""
    ACTIVE = "active"
    COMPLETED = "completed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


@dataclass
class Goal:
    """Represents a portfolio goal."""
    id: Optional[int]
    name: str
    goal_type: GoalType
    target_value: Decimal
    current_value: Decimal = Decimal("0")
    start_value: Decimal = Decimal("0")
    target_date: Optional[date] = None
    code: Optional[str] = None  # For holding-specific goals
    sector: Optional[str] = None  # For sector allocation goals
    status: GoalStatus = GoalStatus.ACTIVE
    notes: str = ""
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @property
    def progress_percent(self) -> float:
        """Calculate progress towards goal as percentage."""
        if self.target_value <= 0:
            return 0.0

        # For goals where we started from a value
        if self.start_value > 0:
            total_needed = float(self.target_value - self.start_value)
            if total_needed <= 0:
                return 100.0
            gained = float(self.current_value - self.start_value)
            return min(100.0, max(0.0, (gained / total_needed) * 100))

        # Simple progress
        return min(100.0, float(self.current_value / self.target_value) * 100)

    @property
    def remaining(self) -> Decimal:
        """Amount remaining to reach goal."""
        return max(Decimal("0"), self.target_value - self.current_value)

    @property
    def is_complete(self) -> bool:
        """Check if goal is complete."""
        return self.current_value >= self.target_value

    @property
    def days_remaining(self) -> Optional[int]:
        """Days until target date (None if no target date)."""
        if not self.target_date:
            return None
        return (self.target_date - date.today()).days

    @property
    def on_track(self) -> Optional[bool]:
        """Check if goal is on track (only for dated goals)."""
        if not self.target_date or not self.created_at:
            return None

        total_days = (self.target_date - self.created_at.date()).days
        if total_days <= 0:
            return self.is_complete

        elapsed_days = (date.today() - self.created_at.date()).days
        expected_progress = (elapsed_days / total_days) * 100

        return self.progress_percent >= expected_progress


@dataclass
class GoalProgress:
    """Progress snapshot for a goal."""
    goal_id: int
    date: date
    value: Decimal
    progress_percent: float


@dataclass
class GoalMilestone:
    """A milestone within a larger goal."""
    goal_id: int
    name: str
    target_value: Decimal
    achieved: bool = False
    achieved_date: Optional[date] = None


class GoalTracker:
    """
    Manages portfolio goals and tracking.

    Stores goals in SQLite database.
    """

    def __init__(self, db_path: Path):
        """Initialize goal tracker with database path."""
        self.db_path = db_path
        self._init_database()

    def _init_database(self) -> None:
        """Initialize the goals tables."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS goals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    goal_type TEXT NOT NULL,
                    target_value TEXT NOT NULL,
                    current_value TEXT DEFAULT '0',
                    start_value TEXT DEFAULT '0',
                    target_date TEXT,
                    code TEXT,
                    sector TEXT,
                    status TEXT DEFAULT 'active',
                    notes TEXT DEFAULT '',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    completed_at TEXT
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS goal_progress (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    goal_id INTEGER NOT NULL,
                    date TEXT NOT NULL,
                    value TEXT NOT NULL,
                    progress_percent REAL NOT NULL,
                    FOREIGN KEY (goal_id) REFERENCES goals(id)
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS goal_milestones (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    goal_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    target_value TEXT NOT NULL,
                    achieved INTEGER DEFAULT 0,
                    achieved_date TEXT,
                    FOREIGN KEY (goal_id) REFERENCES goals(id)
                )
            """)

            conn.execute("CREATE INDEX IF NOT EXISTS idx_goals_status ON goals(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_progress_goal ON goal_progress(goal_id)")
            conn.commit()

    def create_goal(
        self,
        name: str,
        goal_type: GoalType,
        target_value: Decimal,
        start_value: Decimal = Decimal("0"),
        target_date: Optional[date] = None,
        code: Optional[str] = None,
        sector: Optional[str] = None,
        notes: str = "",
    ) -> Goal:
        """Create a new goal."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO goals (
                    name, goal_type, target_value, current_value, start_value,
                    target_date, code, sector, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                name,
                goal_type.value,
                str(target_value),
                str(start_value),
                str(start_value),
                target_date.isoformat() if target_date else None,
                code.upper() if code else None,
                sector,
                notes,
            ))
            conn.commit()

            return Goal(
                id=cursor.lastrowid,
                name=name,
                goal_type=goal_type,
                target_value=target_value,
                current_value=start_value,
                start_value=start_value,
                target_date=target_date,
                code=code.upper() if code else None,
                sector=sector,
                notes=notes,
            )

    def get_goal(self, goal_id: int) -> Optional[Goal]:
        """Get a goal by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM goals WHERE id = ?", (goal_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_goal(row)
            return None

    def get_goals(
        self,
        status: Optional[GoalStatus] = None,
        goal_type: Optional[GoalType] = None,
    ) -> List[Goal]:
        """Get all goals with optional filters."""
        query = "SELECT * FROM goals WHERE 1=1"
        params = []

        if status:
            query += " AND status = ?"
            params.append(status.value)

        if goal_type:
            query += " AND goal_type = ?"
            params.append(goal_type.value)

        query += " ORDER BY created_at DESC"

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            return [self._row_to_goal(row) for row in cursor.fetchall()]

    def update_goal_progress(
        self,
        goal_id: int,
        current_value: Decimal,
    ) -> Goal:
        """Update the current value of a goal."""
        with sqlite3.connect(self.db_path) as conn:
            # Update goal
            conn.execute("""
                UPDATE goals SET current_value = ? WHERE id = ?
            """, (str(current_value), goal_id))

            # Record progress
            goal = self.get_goal(goal_id)
            if goal:
                conn.execute("""
                    INSERT INTO goal_progress (goal_id, date, value, progress_percent)
                    VALUES (?, ?, ?, ?)
                """, (
                    goal_id,
                    date.today().isoformat(),
                    str(current_value),
                    goal.progress_percent,
                ))

                # Check if goal is now complete
                if goal.is_complete and goal.status == GoalStatus.ACTIVE:
                    conn.execute("""
                        UPDATE goals SET status = 'completed', completed_at = ?
                        WHERE id = ?
                    """, (datetime.now().isoformat(), goal_id))

            conn.commit()

        return self.get_goal(goal_id)

    def update_goals_from_portfolio(self, portfolio: Portfolio) -> List[Goal]:
        """Update all goals based on current portfolio state."""
        updated = []

        for goal in self.get_goals(status=GoalStatus.ACTIVE):
            new_value = None

            if goal.goal_type == GoalType.PORTFOLIO_VALUE:
                new_value = portfolio.total_market_value

            elif goal.goal_type == GoalType.HOLDING_VALUE and goal.code:
                holding = portfolio.get_holding(goal.code)
                if holding:
                    new_value = holding.market_value

            elif goal.goal_type == GoalType.SHARES_OWNED and goal.code:
                holding = portfolio.get_holding(goal.code)
                if holding:
                    new_value = Decimal(str(holding.quantity))

            elif goal.goal_type == GoalType.SECTOR_ALLOCATION and goal.sector:
                sector_total = sum(
                    h.market_value for h in portfolio.holdings
                    if h.sector.value == goal.sector
                )
                if portfolio.total_market_value > 0:
                    new_value = (sector_total / portfolio.total_market_value) * 100

            if new_value is not None:
                updated_goal = self.update_goal_progress(goal.id, new_value)
                updated.append(updated_goal)

        return updated

    def delete_goal(self, goal_id: int) -> bool:
        """Delete a goal."""
        with sqlite3.connect(self.db_path) as conn:
            # Delete progress records first
            conn.execute("DELETE FROM goal_progress WHERE goal_id = ?", (goal_id,))
            conn.execute("DELETE FROM goal_milestones WHERE goal_id = ?", (goal_id,))

            cursor = conn.execute("DELETE FROM goals WHERE id = ?", (goal_id,))
            conn.commit()
            return cursor.rowcount > 0

    def pause_goal(self, goal_id: int) -> bool:
        """Pause a goal."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                UPDATE goals SET status = 'paused' WHERE id = ? AND status = 'active'
            """, (goal_id,))
            conn.commit()
            return cursor.rowcount > 0

    def resume_goal(self, goal_id: int) -> bool:
        """Resume a paused goal."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                UPDATE goals SET status = 'active' WHERE id = ? AND status = 'paused'
            """, (goal_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_progress_history(
        self,
        goal_id: int,
        limit: int = 30,
    ) -> List[GoalProgress]:
        """Get progress history for a goal."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM goal_progress
                WHERE goal_id = ?
                ORDER BY date DESC
                LIMIT ?
            """, (goal_id, limit))

            return [
                GoalProgress(
                    goal_id=row["goal_id"],
                    date=date.fromisoformat(row["date"]),
                    value=Decimal(row["value"]),
                    progress_percent=row["progress_percent"],
                )
                for row in cursor.fetchall()
            ]

    def _row_to_goal(self, row: sqlite3.Row) -> Goal:
        """Convert database row to Goal object."""
        return Goal(
            id=row["id"],
            name=row["name"],
            goal_type=GoalType(row["goal_type"]),
            target_value=Decimal(row["target_value"]),
            current_value=Decimal(row["current_value"]),
            start_value=Decimal(row["start_value"]),
            target_date=date.fromisoformat(row["target_date"]) if row["target_date"] else None,
            code=row["code"],
            sector=row["sector"],
            status=GoalStatus(row["status"]),
            notes=row["notes"] or "",
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
        )


def create_common_goals(
    tracker: GoalTracker,
    portfolio: Portfolio,
) -> List[Goal]:
    """Create common goal templates based on portfolio."""
    goals = []

    # Portfolio value milestone goals
    current_value = float(portfolio.total_market_value)

    # Next round number milestones
    milestones = [50000, 100000, 250000, 500000, 750000, 1000000, 2000000, 5000000]
    next_milestone = next((m for m in milestones if m > current_value), None)

    if next_milestone:
        goal = tracker.create_goal(
            name=f"Reach ${next_milestone:,}",
            goal_type=GoalType.PORTFOLIO_VALUE,
            target_value=Decimal(str(next_milestone)),
            start_value=portfolio.total_market_value,
        )
        goals.append(goal)

    return goals


def calculate_goal_projection(
    goal: Goal,
    monthly_contribution: Decimal = Decimal("0"),
    annual_return: Decimal = Decimal("0.07"),
) -> Dict[str, Any]:
    """Project when a goal will be reached."""
    current = float(goal.current_value)
    target = float(goal.target_value)
    monthly = float(monthly_contribution)
    monthly_return = float(annual_return) / 12

    if current >= target:
        return {
            "already_complete": True,
            "months_to_goal": 0,
            "projected_date": date.today(),
        }

    # Simple projection with compound returns
    months = 0
    value = current

    while value < target and months < 600:  # Max 50 years
        value = value * (1 + monthly_return) + monthly
        months += 1

    projected_date = date.today() + timedelta(days=months * 30)

    return {
        "already_complete": False,
        "months_to_goal": months,
        "years_to_goal": months / 12,
        "projected_date": projected_date,
        "assumptions": {
            "monthly_contribution": monthly,
            "annual_return": f"{float(annual_return)*100:.1f}%",
        },
    }


def format_goals_dashboard(
    goals: List[Goal],
    portfolio: Optional[Portfolio] = None,
) -> str:
    """Format goals as a dashboard view."""
    lines = []

    lines.append("=" * 70)
    lines.append("PORTFOLIO GOALS")
    lines.append("=" * 70)

    if not goals:
        lines.append("\n  No goals set yet.")
        lines.append("\n  Create goals with:")
        lines.append("    goals --add --name 'Reach $1M' --type portfolio_value --target 1000000")
        lines.append("    goals --add --name '1000 CBA shares' --type shares_owned --code CBA --target 1000")
        lines.append("    goals --add --name '$50k dividend income' --type dividend_income --target 50000")
        return "\n".join(lines)

    # Active goals
    active = [g for g in goals if g.status == GoalStatus.ACTIVE]
    completed = [g for g in goals if g.status == GoalStatus.COMPLETED]

    if active:
        lines.append(f"\n{'ACTIVE GOALS':^70}")
        lines.append("-" * 70)

        for goal in active:
            lines.append(f"\n  📎 {goal.name}")
            lines.append(f"     Type: {goal.goal_type.value.replace('_', ' ').title()}")

            if goal.code:
                lines.append(f"     Stock: {goal.code}")

            # Progress bar
            progress = goal.progress_percent
            bar_width = 30
            filled = int(progress / 100 * bar_width)
            bar = "█" * filled + "░" * (bar_width - filled)
            lines.append(f"     Progress: [{bar}] {progress:.1f}%")

            # Values
            if goal.goal_type == GoalType.SHARES_OWNED:
                lines.append(
                    f"     {int(goal.current_value):,} / {int(goal.target_value):,} shares"
                )
            elif goal.goal_type == GoalType.SECTOR_ALLOCATION:
                lines.append(
                    f"     {float(goal.current_value):.1f}% / {float(goal.target_value):.1f}%"
                )
            else:
                lines.append(
                    f"     ${float(goal.current_value):,.0f} / ${float(goal.target_value):,.0f}"
                )
                lines.append(f"     Remaining: ${float(goal.remaining):,.0f}")

            # Target date
            if goal.target_date:
                days = goal.days_remaining
                if days is not None:
                    if days > 0:
                        status = "⏰" if goal.on_track else "⚠️"
                        lines.append(f"     {status} {days} days remaining ({goal.target_date})")
                    elif days == 0:
                        lines.append(f"     📅 Due today!")
                    else:
                        lines.append(f"     ❌ Overdue by {abs(days)} days")

    if completed:
        lines.append(f"\n{'COMPLETED GOALS':^70}")
        lines.append("-" * 70)

        for goal in completed[:5]:  # Show last 5 completed
            completed_str = ""
            if goal.completed_at:
                completed_str = f" (completed {goal.completed_at.strftime('%Y-%m-%d')})"
            lines.append(f"  ✅ {goal.name}{completed_str}")

        if len(completed) > 5:
            lines.append(f"  ... and {len(completed) - 5} more completed goals")

    # Summary stats
    lines.append("")
    lines.append("-" * 70)
    lines.append(f"  Active: {len(active)} | Completed: {len(completed)}")

    if active:
        avg_progress = sum(g.progress_percent for g in active) / len(active)
        lines.append(f"  Average Progress: {avg_progress:.1f}%")

    lines.append("")

    return "\n".join(lines)


def format_goal_detail(
    goal: Goal,
    history: List[GoalProgress],
) -> str:
    """Format detailed view of a single goal."""
    lines = []

    lines.append("=" * 60)
    lines.append(f"GOAL: {goal.name}")
    lines.append("=" * 60)

    lines.append(f"\n  Type:        {goal.goal_type.value.replace('_', ' ').title()}")
    lines.append(f"  Status:      {goal.status.value.title()}")

    if goal.code:
        lines.append(f"  Stock:       {goal.code}")
    if goal.sector:
        lines.append(f"  Sector:      {goal.sector}")

    lines.append("")

    # Progress visualization
    progress = goal.progress_percent
    bar_width = 40
    filled = int(progress / 100 * bar_width)
    bar = "█" * filled + "░" * (bar_width - filled)
    lines.append(f"  [{bar}] {progress:.1f}%")
    lines.append("")

    # Values
    lines.append(f"  Started at:  ${float(goal.start_value):>14,.2f}")
    lines.append(f"  Current:     ${float(goal.current_value):>14,.2f}")
    lines.append(f"  Target:      ${float(goal.target_value):>14,.2f}")
    lines.append(f"  Remaining:   ${float(goal.remaining):>14,.2f}")

    # Progress gained
    gained = goal.current_value - goal.start_value
    if gained != 0:
        lines.append(f"  Progress:    ${float(gained):>+14,.2f}")

    # Dates
    if goal.target_date:
        lines.append(f"\n  Target Date: {goal.target_date}")
        if goal.days_remaining is not None:
            if goal.days_remaining > 0:
                lines.append(f"  Days Left:   {goal.days_remaining}")
            elif goal.days_remaining == 0:
                lines.append(f"  Due:         TODAY")
            else:
                lines.append(f"  Overdue:     {abs(goal.days_remaining)} days")

    if goal.created_at:
        lines.append(f"  Created:     {goal.created_at.strftime('%Y-%m-%d')}")

    if goal.notes:
        lines.append(f"\n  Notes: {goal.notes}")

    # Progress history
    if history:
        lines.append("")
        lines.append("-" * 60)
        lines.append("PROGRESS HISTORY")
        lines.append("-" * 60)
        lines.append(f"\n  {'Date':<12} {'Value':>15} {'Progress':>10}")
        lines.append("  " + "-" * 40)

        for h in history[:10]:
            lines.append(
                f"  {h.date.isoformat():<12} ${float(h.value):>13,.0f} {h.progress_percent:>9.1f}%"
            )

    lines.append("")

    return "\n".join(lines)
