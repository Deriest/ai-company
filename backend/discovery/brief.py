"""Engineering Discovery Engine — Brief Generator.

Assembles and validates the Engineering Brief.
The Brief is the contract between Discovery and Planning.
"""

import logging
from datetime import datetime, timezone
from uuid import uuid4
from dataclasses import dataclass, field
from discovery.config import discovery_config
from discovery.intent import IntentResult
from discovery.requirements import ExtractionResult, Requirement
from discovery.readiness import ReadinessResult

logger = logging.getLogger("aic.discovery.brief")


@dataclass
class EngineeringBriefData:
    """Engineering Brief data structure.

    This is the internal representation before persistence.
    """
    # Identity
    id: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = 1
    discovery_rounds: int = 0

    # Core
    engineering_goal: str = ""
    user_intent: str = ""
    request_category: str = "feature"
    scope: dict = field(default_factory=lambda: {"in_scope": [], "out_of_scope": []})

    # Requirements
    functional_requirements: list[dict] = field(default_factory=list)
    non_functional_requirements: list[dict] = field(default_factory=list)
    constraints: list[dict] = field(default_factory=list)
    assumptions: list[dict] = field(default_factory=list)
    dependencies: list[dict] = field(default_factory=list)
    risks: list[dict] = field(default_factory=list)
    acceptance_criteria: list[dict] = field(default_factory=list)

    # Readiness
    readiness_status: str = "not_ready"
    readiness_score: float = 0.0
    readiness_dimensions: dict = field(default_factory=dict)

    # Metadata
    outstanding_unknowns: list[dict] = field(default_factory=list)
    discovery_metadata: dict = field(default_factory=dict)

    # Status
    status: str = "draft"  # draft, ready, handed_off, expired

    def to_dict(self) -> dict:
        """Serialize to dictionary for storage."""
        return {
            "id": self.id,
            "version": self.version,
            "discovery_rounds": self.discovery_rounds,
            "engineering_goal": self.engineering_goal,
            "user_intent": self.user_intent,
            "request_category": self.request_category,
            "scope": self.scope,
            "functional_requirements": self.functional_requirements,
            "non_functional_requirements": self.non_functional_requirements,
            "constraints": self.constraints,
            "assumptions": self.assumptions,
            "dependencies": self.dependencies,
            "risks": self.risks,
            "acceptance_criteria": self.acceptance_criteria,
            "readiness_status": self.readiness_status,
            "readiness_score": self.readiness_score,
            "readiness_dimensions": self.readiness_dimensions,
            "outstanding_unknowns": self.outstanding_unknowns,
            "discovery_metadata": self.discovery_metadata,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class BriefValidation:
    """Result of Brief validation."""

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


VALID_CATEGORIES = [
    "feature", "bugfix", "refactor", "docs", "test", "infra",
    "research", "architecture", "security", "performance",
    "devops", "database", "ui", "ai_llm", "chat",
]


class BriefGenerator:
    """Assembles and validates Engineering Briefs."""

    @classmethod
    def assemble(
        cls,
        intent: IntentResult,
        extraction: ExtractionResult,
        readiness: ReadinessResult,
        content: str,
        round_number: int = 0,
    ) -> EngineeringBriefData:
        """Assemble an Engineering Brief from discovery results.

        Args:
            intent: Intent classification result
            extraction: Requirement extraction result
            readiness: Readiness evaluation result
            content: Original user message
            round_number: Current clarification round

        Returns:
            EngineeringBriefData with all fields populated
        """
        # Generate unique ID
        brief_id = f"BRIEF-{uuid4().hex[:12].upper()}"

        # Extract engineering goal from content
        engineering_goal = cls._extract_goal(content, intent)

        # Build scope from requirements
        scope = cls._build_scope(extraction, content)

        # Convert requirements to dict format
        functional = cls._requirements_to_dict(extraction.functional)
        non_functional = cls._requirements_to_dict(extraction.non_functional)
        constraints = cls._requirements_to_dict(extraction.constraints)
        assumptions = cls._requirements_to_dict(extraction.assumptions)
        dependencies = cls._requirements_to_dict(extraction.dependencies)
        acceptance = cls._requirements_to_dict(extraction.acceptance_criteria)

        # Build risks
        risks = cls._build_risks(extraction, readiness)

        # Build outstanding unknowns
        outstanding = cls._build_outstanding_unknowns(readiness, extraction)

        # Build metadata
        metadata = {
            "domain": intent.domain,
            "domain_confidence": intent.confidence,
            "ambiguity_score": 0.0,  # Will be updated by engine
            "extraction_coverage": len(extraction.covered_fields),
            "extraction_missing": len(extraction.missing_fields),
            "round_number": round_number,
            "engine_version": "2.3.2",
        }

        return EngineeringBriefData(
            id=brief_id,
            version=round_number + 1,
            discovery_rounds=round_number,
            engineering_goal=engineering_goal,
            user_intent=content[:500],
            request_category=intent.domain,
            scope=scope,
            functional_requirements=functional,
            non_functional_requirements=non_functional,
            constraints=constraints,
            assumptions=assumptions,
            dependencies=dependencies,
            risks=risks,
            acceptance_criteria=acceptance,
            readiness_status="ready" if readiness.is_ready else "not_ready",
            readiness_score=readiness.overall_score,
            readiness_dimensions=readiness.dimensions,
            outstanding_unknowns=outstanding,
            discovery_metadata=metadata,
            status="ready" if readiness.is_ready else "draft",
        )

    @classmethod
    def validate(cls, brief: EngineeringBriefData) -> BriefValidation:
        """Validate an Engineering Brief.

        Args:
            brief: Brief to validate

        Returns:
            BriefValidation with is_valid, errors, warnings
        """
        errors = []
        warnings = []

        # Required fields
        if not brief.engineering_goal:
            errors.append("engineering_goal is required")
        if not brief.user_intent:
            errors.append("user_intent is required")
        if brief.request_category not in VALID_CATEGORIES:
            errors.append(f"invalid request_category: {brief.request_category}")

        # Readiness
        if brief.readiness_score < discovery_config.readiness_threshold:
            errors.append(
                f"readiness_score {brief.readiness_score:.2f} < "
                f"{discovery_config.readiness_threshold}"
            )

        # Dimension floor
        for dim_name, dim_score in brief.readiness_dimensions.items():
            if dim_score < discovery_config.dimension_floor:
                errors.append(
                    f"dimension {dim_name} = {dim_score:.2f} < "
                    f"{discovery_config.dimension_floor}"
                )

        # Acceptance criteria
        if not brief.acceptance_criteria:
            warnings.append("acceptance_criteria is empty — recommended for planning")

        # Scope
        if not brief.scope.get("in_scope"):
            warnings.append("scope.in_scope is empty — may lead to scope creep")

        return BriefValidation(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    @classmethod
    def _extract_goal(cls, content: str, intent: IntentResult) -> str:
        """Extract engineering goal from content."""
        # Take first sentence or first 200 chars
        sentences = content.split(".")
        goal = sentences[0].strip() if sentences else content.strip()

        # Limit length
        if len(goal) > 200:
            goal = goal[:197] + "..."

        # Add domain context
        if intent.domain and intent.domain != "chat":
            goal = f"[{intent.domain.title()}] {goal}"

        return goal

    @classmethod
    def _build_scope(
        cls,
        extraction: ExtractionResult,
        content: str,
    ) -> dict:
        """Build scope from extraction results."""
        in_scope = []
        out_of_scope = []

        # Functional requirements define in-scope
        for req in extraction.functional:
            in_scope.append(req.description[:100])

        # Constraints may define out-of-scope
        for req in extraction.constraints:
            if "not" in req.description.lower() or "exclude" in req.description.lower():
                out_of_scope.append(req.description[:100])

        # Default if empty
        if not in_scope:
            in_scope = [content[:100]]

        return {
            "in_scope": in_scope,
            "out_of_scope": out_of_scope,
        }

    @classmethod
    def _requirements_to_dict(cls, requirements: list[Requirement]) -> list[dict]:
        """Convert requirements to dictionary format."""
        return [
            {
                "id": req.id,
                "description": req.description,
                "priority": req.priority,
                "source": req.source,
            }
            for req in requirements
        ]

    @classmethod
    def _build_risks(
        cls,
        extraction: ExtractionResult,
        readiness: ReadinessResult,
    ) -> list[dict]:
        """Build risks from extraction and readiness."""
        risks = []

        # Risk from missing fields
        if readiness.missing_fields:
            risks.append({
                "description": f"Missing information: {', '.join(readiness.missing_fields[:3])}",
                "likelihood": "medium",
                "impact": "medium",
                "mitigation": "Proceed with assumptions, validate during implementation",
            })

        # Risk from low readiness
        if readiness.overall_score < 0.70:
            risks.append({
                "description": "Low readiness score — high uncertainty",
                "likelihood": "high",
                "impact": "high",
                "mitigation": "Additional clarification recommended",
            })

        return risks

    @classmethod
    def _build_outstanding_unknowns(
        cls,
        readiness: ReadinessResult,
        extraction: ExtractionResult,
    ) -> list[dict]:
        """Build outstanding unknowns."""
        unknowns = []

        for missing in readiness.missing_fields:
            unknowns.append({
                "description": f"Missing: {missing}",
                "resolution_plan": "To be determined during implementation",
                "blocks_planning": False,
            })

        for missing in extraction.missing_fields:
            if missing not in readiness.missing_fields:
                unknowns.append({
                    "description": f"Domain field not covered: {missing}",
                    "resolution_plan": "Will use reasonable defaults",
                    "blocks_planning": False,
                })

        return unknowns
