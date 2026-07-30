"""Delivery & Continuous Improvement — Data Models."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass
class LessonLearned:
    """A lesson learned from execution."""

    id: str = ""
    lesson: str = ""
    category: str = ""  # planning, execution, verification
    impact: str = "medium"  # low, medium, high
    recommendation: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        if not self.id:
            self.id = f"LESSON-{uuid4().hex[:8].upper()}"


@dataclass
class EngineeringReport:
    """Comprehensive engineering report."""

    report_id: str = ""
    brief_id: str = ""
    plan_id: str = ""
    graph_id: str = ""
    verification_id: str = ""

    # Summary
    goal: str = ""
    outcome: str = "pending"  # success, partial, failure
    duration: str = ""
    quality_score: float = 0.0

    # Metrics
    total_tasks: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0
    retried_tasks: int = 0

    # Lessons
    lessons: list[LessonLearned] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    # Status
    status: str = "draft"  # draft, final, delivered
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        if not self.report_id:
            self.report_id = f"RPT-{uuid4().hex[:12].upper()}"

    def to_dict(self) -> dict:
        return {
            "report_id": self.report_id,
            "brief_id": self.brief_id,
            "goal": self.goal,
            "outcome": self.outcome,
            "duration": self.duration,
            "quality_score": self.quality_score,
            "total_tasks": self.total_tasks,
            "successful_tasks": self.successful_tasks,
            "failed_tasks": self.failed_tasks,
            "lessons": [
                {
                    "id": l.id,
                    "lesson": l.lesson,
                    "category": l.category,
                    "impact": l.impact,
                }
                for l in self.lessons
            ],
            "recommendations": self.recommendations,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class DeliveryResult:
    """Result of delivery operation."""

    report: EngineeringReport | None = None
    message: str = ""
    metadata: dict = field(default_factory=dict)
