"""Planning Engine — Data Models.

Defines the Engineering Plan and related data structures.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass
class ArchitectureDecision:
    """An architectural decision made during planning."""

    decision: str
    rationale: str
    alternatives_considered: list[str] = field(default_factory=list)
    risk_level: str = "low"  # low, medium, high


@dataclass
class RiskMitigation:
    """A risk and its mitigation strategy."""

    risk: str
    likelihood: str = "medium"  # low, medium, high
    impact: str = "medium"      # low, medium, high
    mitigation: str = ""
    fallback: str = ""


@dataclass
class DependencyMap:
    """Map of dependencies."""

    external: list[str] = field(default_factory=list)
    internal: list[str] = field(default_factory=list)
    circular: list[str] = field(default_factory=list)


@dataclass
class EffortEstimate:
    """Effort estimate for a requirement."""

    requirement_id: str
    complexity: str = "medium"  # low, medium, high, very_high
    estimated_hours: float = 0.0
    confidence: float = 0.5


@dataclass
class AcceptanceCriterion:
    """An acceptance criterion for the plan."""

    id: str
    description: str
    verification_method: str = "manual"


@dataclass
class EngineeringPlan:
    """Structured Engineering Plan.

    Output of the Planning Engine, input to Task Graph Engine.
    """

    # Identity
    id: str = ""
    brief_id: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Core
    engineering_goal: str = ""
    technical_approach: str = ""
    implementation_strategy: str = "hybrid"  # sequential, parallel, hybrid, incremental

    # Decisions and risks
    architecture_decisions: list[ArchitectureDecision] = field(default_factory=list)
    risk_mitigations: list[RiskMitigation] = field(default_factory=list)
    dependency_map: DependencyMap = field(default_factory=DependencyMap)

    # Effort
    effort_estimates: list[EffortEstimate] = field(default_factory=list)
    acceptance_criteria: list[AcceptanceCriterion] = field(default_factory=list)

    # Metadata
    estimated_duration: str = ""
    confidence_score: float = 0.0
    status: str = "draft"  # draft, validated, handed_off

    def __post_init__(self):
        if not self.id:
            self.id = f"PLAN-{uuid4().hex[:12].upper()}"

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "brief_id": self.brief_id,
            "engineering_goal": self.engineering_goal,
            "technical_approach": self.technical_approach,
            "implementation_strategy": self.implementation_strategy,
            "architecture_decisions": [
                {
                    "decision": d.decision,
                    "rationale": d.rationale,
                    "alternatives_considered": d.alternatives_considered,
                    "risk_level": d.risk_level,
                }
                for d in self.architecture_decisions
            ],
            "risk_mitigations": [
                {
                    "risk": r.risk,
                    "likelihood": r.likelihood,
                    "impact": r.impact,
                    "mitigation": r.mitigation,
                    "fallback": r.fallback,
                }
                for r in self.risk_mitigations
            ],
            "dependency_map": {
                "external": self.dependency_map.external,
                "internal": self.dependency_map.internal,
                "circular": self.dependency_map.circular,
            },
            "effort_estimates": [
                {
                    "requirement_id": e.requirement_id,
                    "complexity": e.complexity,
                    "estimated_hours": e.estimated_hours,
                    "confidence": e.confidence,
                }
                for e in self.effort_estimates
            ],
            "acceptance_criteria": [
                {
                    "id": a.id,
                    "description": a.description,
                    "verification_method": a.verification_method,
                }
                for a in self.acceptance_criteria
            ],
            "estimated_duration": self.estimated_duration,
            "confidence_score": self.confidence_score,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class PlanValidation:
    """Result of plan validation."""

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
