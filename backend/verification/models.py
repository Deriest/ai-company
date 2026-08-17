"""Verification Engine — Data Models."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass
class RequirementCheck:
    """Check result for a single requirement."""

    requirement_id: str
    description: str
    status: str = "pending"  # passed, failed, pending
    evidence: str = ""


@dataclass
class QualityScore:
    """Quality score breakdown."""

    code_quality: float = 0.0
    test_coverage: float = 0.0
    documentation: float = 0.0
    security: float = 0.0
    overall: float = 0.0


@dataclass
class VerificationReport:
    """Output of the Verification Engine."""

    verification_id: str = ""
    brief_id: str = ""
    requirements_met: list[RequirementCheck] = field(default_factory=list)
    acceptance_met: list[RequirementCheck] = field(default_factory=list)
    quality_score: QualityScore = field(default_factory=QualityScore)
    regression_results: list[dict] = field(default_factory=list)
    security_findings: list[dict] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    blocking_issues: list[str] = field(default_factory=list)
    overall_status: str = "pending"  # passed, failed, partial
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        if not self.verification_id:
            self.verification_id = f"VER-{uuid4().hex[:12].upper()}"

    def to_dict(self) -> dict:
        return {
            "verification_id": self.verification_id,
            "brief_id": self.brief_id,
            "requirements_met": [
                {
                    "requirement_id": r.requirement_id,
                    "description": r.description,
                    "status": r.status,
                    "evidence": r.evidence,
                }
                for r in self.requirements_met
            ],
            "quality_score": {
                "code_quality": self.quality_score.code_quality,
                "test_coverage": self.quality_score.test_coverage,
                "documentation": self.quality_score.documentation,
                "security": self.quality_score.security,
                "overall": self.quality_score.overall,
            },
            "overall_status": self.overall_status,
            "recommendations": self.recommendations,
            "blocking_issues": self.blocking_issues,
            "created_at": self.created_at.isoformat(),
        }
