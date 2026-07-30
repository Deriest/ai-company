"""Autonomous Execution Intelligence — Data Models."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass
class AnomalyDetection:
    """Detected anomaly in execution."""

    id: str = ""
    anomaly_type: str = ""  # timeout, failure, deadlock, performance
    severity: str = "medium"  # low, medium, high, critical
    description: str = ""
    affected_component: str = ""
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        if not self.id:
            self.id = f"ANOM-{uuid4().hex[:8].upper()}"


@dataclass
class RecoveryAction:
    """Action to recover from failure."""

    id: str = ""
    action_type: str = ""  # retry, replan, escalate, abort
    target: str = ""
    parameters: dict = field(default_factory=dict)
    reason: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        if not self.id:
            self.id = f"REC-{uuid4().hex[:8].upper()}"


@dataclass
class HealingResult:
    """Result of a healing attempt."""

    id: str = ""
    anomaly_id: str = ""
    action_taken: str = ""
    success: bool = False
    details: str = ""
    attempts: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        if not self.id:
            self.id = f"HEAL-{uuid4().hex[:8].upper()}"
