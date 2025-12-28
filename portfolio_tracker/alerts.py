"""
Alerts - Price and value threshold notifications for portfolio monitoring.

Supports various alert types:
- Price alerts (above/below threshold)
- Portfolio value alerts
- Profit/loss threshold alerts
- Concentration alerts
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any

from .models import Portfolio, Holding

logger = logging.getLogger(__name__)


class AlertType(Enum):
    """Types of alerts supported."""
    PRICE_ABOVE = "price_above"
    PRICE_BELOW = "price_below"
    PROFIT_ABOVE = "profit_above"
    LOSS_BELOW = "loss_below"
    PORTFOLIO_VALUE_ABOVE = "portfolio_value_above"
    PORTFOLIO_VALUE_BELOW = "portfolio_value_below"
    WEIGHT_ABOVE = "weight_above"  # Concentration alert
    DAILY_CHANGE_ABOVE = "daily_change_above"
    DAILY_CHANGE_BELOW = "daily_change_below"


class AlertStatus(Enum):
    """Status of an alert."""
    ACTIVE = "active"
    TRIGGERED = "triggered"
    DISMISSED = "dismissed"
    EXPIRED = "expired"


@dataclass
class Alert:
    """Represents a single alert."""
    id: str
    alert_type: AlertType
    code: Optional[str]  # None for portfolio-level alerts
    threshold: Decimal
    status: AlertStatus = AlertStatus.ACTIVE
    created_at: datetime = field(default_factory=datetime.now)
    triggered_at: Optional[datetime] = None
    triggered_value: Optional[Decimal] = None
    description: str = ""
    notify_once: bool = True  # If True, only trigger once

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "alert_type": self.alert_type.value,
            "code": self.code,
            "threshold": float(self.threshold),
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "triggered_at": self.triggered_at.isoformat() if self.triggered_at else None,
            "triggered_value": float(self.triggered_value) if self.triggered_value else None,
            "description": self.description,
            "notify_once": self.notify_once,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Alert":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            alert_type=AlertType(data["alert_type"]),
            code=data.get("code"),
            threshold=Decimal(str(data["threshold"])),
            status=AlertStatus(data["status"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            triggered_at=datetime.fromisoformat(data["triggered_at"]) if data.get("triggered_at") else None,
            triggered_value=Decimal(str(data["triggered_value"])) if data.get("triggered_value") else None,
            description=data.get("description", ""),
            notify_once=data.get("notify_once", True),
        )


@dataclass
class TriggeredAlert:
    """Result of a triggered alert check."""
    alert: Alert
    current_value: Decimal
    message: str
    severity: str = "info"  # info, warning, critical


class AlertManager:
    """Manages portfolio alerts."""

    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is None:
            data_dir = Path(__file__).parent.parent / "data"
        self.alerts_file = data_dir / "alerts.json"
        self.alerts: List[Alert] = []
        self._load_alerts()

    def _load_alerts(self):
        """Load alerts from file."""
        if self.alerts_file.exists():
            try:
                with open(self.alerts_file, "r") as f:
                    data = json.load(f)
                    self.alerts = [Alert.from_dict(a) for a in data.get("alerts", [])]
                    logger.debug(f"Loaded {len(self.alerts)} alerts")
            except Exception as e:
                logger.warning(f"Error loading alerts: {e}")
                self.alerts = []
        else:
            self.alerts = []

    def _save_alerts(self):
        """Save alerts to file."""
        self.alerts_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.alerts_file, "w") as f:
            json.dump({"alerts": [a.to_dict() for a in self.alerts]}, f, indent=2)

    def _generate_id(self) -> str:
        """Generate a unique alert ID."""
        import hashlib
        unique = f"{datetime.now().isoformat()}_{len(self.alerts)}"
        return hashlib.md5(unique.encode()).hexdigest()[:8]

    def add_alert(
        self,
        alert_type: AlertType,
        threshold: Decimal,
        code: Optional[str] = None,
        description: str = "",
        notify_once: bool = True,
    ) -> Alert:
        """
        Add a new alert.

        Args:
            alert_type: Type of alert
            threshold: Threshold value to trigger
            code: Stock code (None for portfolio-level)
            description: Optional description
            notify_once: Only trigger once if True

        Returns:
            Created Alert object
        """
        alert = Alert(
            id=self._generate_id(),
            alert_type=alert_type,
            code=code.upper() if code else None,
            threshold=threshold,
            description=description,
            notify_once=notify_once,
        )
        self.alerts.append(alert)
        self._save_alerts()
        logger.info(f"Created alert {alert.id}: {alert_type.value} for {code or 'portfolio'}")
        return alert

    def remove_alert(self, alert_id: str) -> bool:
        """Remove an alert by ID."""
        for i, alert in enumerate(self.alerts):
            if alert.id == alert_id:
                del self.alerts[i]
                self._save_alerts()
                return True
        return False

    def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts."""
        return [a for a in self.alerts if a.status == AlertStatus.ACTIVE]

    def get_triggered_alerts(self) -> List[Alert]:
        """Get all triggered alerts."""
        return [a for a in self.alerts if a.status == AlertStatus.TRIGGERED]

    def dismiss_alert(self, alert_id: str) -> bool:
        """Dismiss a triggered alert."""
        for alert in self.alerts:
            if alert.id == alert_id:
                alert.status = AlertStatus.DISMISSED
                self._save_alerts()
                return True
        return False

    def reset_alert(self, alert_id: str) -> bool:
        """Reset an alert back to active."""
        for alert in self.alerts:
            if alert.id == alert_id:
                alert.status = AlertStatus.ACTIVE
                alert.triggered_at = None
                alert.triggered_value = None
                self._save_alerts()
                return True
        return False

    def check_alerts(self, portfolio: Portfolio) -> List[TriggeredAlert]:
        """
        Check all active alerts against portfolio.

        Args:
            portfolio: Current portfolio to check

        Returns:
            List of triggered alerts
        """
        triggered = []

        for alert in self.get_active_alerts():
            result = self._check_single_alert(alert, portfolio)
            if result:
                triggered.append(result)

                # Update alert status
                if alert.notify_once:
                    alert.status = AlertStatus.TRIGGERED
                    alert.triggered_at = datetime.now()
                    alert.triggered_value = result.current_value

        if triggered:
            self._save_alerts()

        return triggered

    def _check_single_alert(self, alert: Alert, portfolio: Portfolio) -> Optional[TriggeredAlert]:
        """Check a single alert."""
        if alert.code:
            # Stock-specific alert
            holding = portfolio.get_holding(alert.code)
            if not holding:
                return None
            return self._check_holding_alert(alert, holding)
        else:
            # Portfolio-level alert
            return self._check_portfolio_alert(alert, portfolio)

    def _check_holding_alert(self, alert: Alert, holding: Holding) -> Optional[TriggeredAlert]:
        """Check alerts for a specific holding."""
        current_value = Decimal("0")
        triggered = False
        message = ""
        severity = "info"

        if alert.alert_type == AlertType.PRICE_ABOVE:
            current_value = holding.current_price
            if current_value >= alert.threshold:
                triggered = True
                message = f"{holding.code} price ${current_value:.2f} reached target ${alert.threshold:.2f}"
                severity = "info"

        elif alert.alert_type == AlertType.PRICE_BELOW:
            current_value = holding.current_price
            if current_value <= alert.threshold:
                triggered = True
                message = f"{holding.code} price ${current_value:.2f} dropped below ${alert.threshold:.2f}"
                severity = "warning"

        elif alert.alert_type == AlertType.PROFIT_ABOVE:
            current_value = holding.profit_loss_percent
            if current_value >= alert.threshold:
                triggered = True
                message = f"{holding.code} profit {current_value:+.1f}% exceeded {alert.threshold:+.1f}%"
                severity = "info"

        elif alert.alert_type == AlertType.LOSS_BELOW:
            current_value = holding.profit_loss_percent
            if current_value <= -alert.threshold:  # threshold is positive, loss is negative
                triggered = True
                message = f"{holding.code} loss {current_value:+.1f}% exceeded -{alert.threshold:.1f}%"
                severity = "critical"

        elif alert.alert_type == AlertType.WEIGHT_ABOVE:
            current_value = holding.portfolio_weight
            if current_value >= alert.threshold:
                triggered = True
                message = f"{holding.code} weight {current_value:.1f}% exceeded {alert.threshold:.1f}% (concentration risk)"
                severity = "warning"

        elif alert.alert_type == AlertType.DAILY_CHANGE_ABOVE:
            current_value = holding.daily_change_percent
            if current_value >= alert.threshold:
                triggered = True
                message = f"{holding.code} up {current_value:+.1f}% today (threshold: +{alert.threshold:.1f}%)"
                severity = "info"

        elif alert.alert_type == AlertType.DAILY_CHANGE_BELOW:
            current_value = holding.daily_change_percent
            if current_value <= -alert.threshold:
                triggered = True
                message = f"{holding.code} down {current_value:+.1f}% today (threshold: -{alert.threshold:.1f}%)"
                severity = "warning"

        if triggered:
            return TriggeredAlert(
                alert=alert,
                current_value=current_value,
                message=message,
                severity=severity,
            )
        return None

    def _check_portfolio_alert(self, alert: Alert, portfolio: Portfolio) -> Optional[TriggeredAlert]:
        """Check portfolio-level alerts."""
        current_value = Decimal("0")
        triggered = False
        message = ""
        severity = "info"

        if alert.alert_type == AlertType.PORTFOLIO_VALUE_ABOVE:
            current_value = portfolio.total_market_value
            if current_value >= alert.threshold:
                triggered = True
                message = f"Portfolio value ${current_value:,.0f} reached ${alert.threshold:,.0f}"
                severity = "info"

        elif alert.alert_type == AlertType.PORTFOLIO_VALUE_BELOW:
            current_value = portfolio.total_market_value
            if current_value <= alert.threshold:
                triggered = True
                message = f"Portfolio value ${current_value:,.0f} dropped below ${alert.threshold:,.0f}"
                severity = "critical"

        if triggered:
            return TriggeredAlert(
                alert=alert,
                current_value=current_value,
                message=message,
                severity=severity,
            )
        return None


def format_alert_list(alerts: List[Alert]) -> str:
    """Format alerts for display."""
    if not alerts:
        return "No alerts configured."

    lines = []
    lines.append(f"{'ID':<10} {'Type':<20} {'Code':<6} {'Threshold':>12} {'Status':<12}")
    lines.append("-" * 65)

    for alert in alerts:
        code = alert.code or "ALL"
        threshold = f"${float(alert.threshold):,.2f}" if "value" in alert.alert_type.value or "price" in alert.alert_type.value else f"{float(alert.threshold):.1f}%"
        lines.append(
            f"{alert.id:<10} "
            f"{alert.alert_type.value:<20} "
            f"{code:<6} "
            f"{threshold:>12} "
            f"{alert.status.value:<12}"
        )

    return "\n".join(lines)


def format_triggered_alerts(triggered: List[TriggeredAlert]) -> str:
    """Format triggered alerts for display."""
    if not triggered:
        return "No alerts triggered."

    lines = []
    lines.append("=" * 70)
    lines.append("TRIGGERED ALERTS")
    lines.append("=" * 70)

    severity_icons = {
        "info": "ℹ️ ",
        "warning": "⚠️ ",
        "critical": "🚨",
    }

    for t in triggered:
        icon = severity_icons.get(t.severity, "")
        lines.append(f"\n{icon} {t.message}")
        if t.alert.description:
            lines.append(f"   Note: {t.alert.description}")

    return "\n".join(lines)
