"""Context & Knowledge Intelligence — Data Models."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass
class KnowledgeEntry:
    """A single knowledge entry."""

    id: str = ""
    domain: str = ""  # repository, architecture, conventions, business_rules
    key: str = ""
    value: str = ""
    source: str = ""  # file_path, documentation, manual
    confidence: float = 1.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        if not self.id:
            self.id = f"KNOW-{uuid4().hex[:8].upper()}"


@dataclass
class DecisionRecord:
    """A recorded engineering decision."""

    id: str = ""
    decision: str = ""
    rationale: str = ""
    context: str = ""
    outcome: str = ""  # good, acceptable, poor
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        if not self.id:
            self.id = f"DEC-{uuid4().hex[:8].upper()}"


@dataclass
class ProjectContext:
    """Context delivered to engines."""

    project_id: str = ""
    repository_structure: dict = field(default_factory=dict)
    architecture_patterns: list[str] = field(default_factory=list)
    coding_conventions: dict = field(default_factory=dict)
    business_rules: list[str] = field(default_factory=list)
    past_decisions: list[DecisionRecord] = field(default_factory=list)
    knowledge_entries: list[KnowledgeEntry] = field(default_factory=list)
    freshness_score: float = 1.0

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "repository_structure": self.repository_structure,
            "architecture_patterns": self.architecture_patterns,
            "coding_conventions": self.coding_conventions,
            "business_rules": self.business_rules,
            "past_decisions": [
                {
                    "id": d.id,
                    "decision": d.decision,
                    "rationale": d.rationale,
                    "outcome": d.outcome,
                }
                for d in self.past_decisions
            ],
            "knowledge_entries": len(self.knowledge_entries),
            "freshness_score": self.freshness_score,
        }
