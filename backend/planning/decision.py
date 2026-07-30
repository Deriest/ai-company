"""Planning Engine — Technical Decision Making.

Makes architectural decisions based on brief analysis.
"""

import re
import logging
from planning.analyzer import BriefAnalysis
from planning.models import ArchitectureDecision

logger = logging.getLogger("aic.planning.decision")


# Decision templates based on patterns
DECISION_TEMPLATES = {
    "database_changes": {
        "decision": "Use database migrations for schema changes",
        "rationale": "Migrations ensure reproducible schema changes and rollback capability",
        "alternatives": ["Direct SQL", "ORM auto-migration"],
        "risk_level": "medium",
    },
    "api_changes": {
        "decision": "Follow RESTful API design patterns",
        "rationale": "REST is well-understood and compatible with existing architecture",
        "alternatives": ["GraphQL", "gRPC"],
        "risk_level": "low",
    },
    "ui_changes": {
        "decision": "Use component-based UI architecture",
        "rationale": "Components are reusable and testable",
        "alternatives": ["Template-based", "Server-side rendering"],
        "risk_level": "low",
    },
    "auth_changes": {
        "decision": "Use JWT-based authentication",
        "rationale": "JWT is stateless and works well with API-first architecture",
        "alternatives": ["Session-based", "OAuth2"],
        "risk_level": "medium",
    },
    "testing_strategy": {
        "decision": "Use pytest with integration tests",
        "rationale": "pytest is the project standard and supports async testing",
        "alternatives": ["unittest", "nose2"],
        "risk_level": "low",
    },
    "error_handling": {
        "decision": "Use structured error responses",
        "rationale": "Consistent error format improves client experience",
        "alternatives": ["Custom error codes", "HTTP status only"],
        "risk_level": "low",
    },
}


class DecisionMaker:
    """Makes architectural decisions based on analysis."""

    @classmethod
    def make_decisions(
        cls,
        analysis: BriefAnalysis,
        brief_data: dict,
    ) -> list[ArchitectureDecision]:
        """Make architectural decisions.

        Args:
            analysis: Brief analysis result
            brief_data: Original brief data

        Returns:
            List of architecture decisions
        """
        decisions = []

        # Database decisions
        if analysis.requires_database_changes:
            template = DECISION_TEMPLATES["database_changes"]
            decisions.append(ArchitectureDecision(
                decision=template["decision"],
                rationale=template["rationale"],
                alternatives_considered=template["alternatives"],
                risk_level=template["risk_level"],
            ))

        # API decisions
        if analysis.requires_api_changes:
            template = DECISION_TEMPLATES["api_changes"]
            decisions.append(ArchitectureDecision(
                decision=template["decision"],
                rationale=template["rationale"],
                alternatives_considered=template["alternatives"],
                risk_level=template["risk_level"],
            ))

        # UI decisions
        if analysis.requires_ui_changes:
            template = DECISION_TEMPLATES["ui_changes"]
            decisions.append(ArchitectureDecision(
                decision=template["decision"],
                rationale=template["rationale"],
                alternatives_considered=template["alternatives"],
                risk_level=template["risk_level"],
            ))

        # Auth decisions
        if "auth" in analysis.affected_components:
            template = DECISION_TEMPLATES["auth_changes"]
            decisions.append(ArchitectureDecision(
                decision=template["decision"],
                rationale=template["rationale"],
                alternatives_considered=template["alternatives"],
                risk_level=template["risk_level"],
            ))

        # Testing decisions (always)
        template = DECISION_TEMPLATES["testing_strategy"]
        decisions.append(ArchitectureDecision(
            decision=template["decision"],
            rationale=template["rationale"],
            alternatives_considered=template["alternatives"],
            risk_level=template["risk_level"],
        ))

        # Error handling decisions (always)
        template = DECISION_TEMPLATES["error_handling"]
        decisions.append(ArchitectureDecision(
            decision=template["decision"],
            rationale=template["rationale"],
            alternatives_considered=template["alternatives"],
            risk_level=template["risk_level"],
        ))

        return decisions

    @classmethod
    def select_strategy(cls, analysis: BriefAnalysis) -> str:
        """Select implementation strategy.

        Returns: sequential, parallel, hybrid, or incremental
        """
        # Small scope with few components -> sequential
        if analysis.scope_size == "small" and len(analysis.affected_components) <= 2:
            return "sequential"

        # Large scope with many components -> hybrid
        if analysis.scope_size in ("large", "very_large"):
            return "hybrid"

        # Multiple independent components -> parallel
        if len(analysis.affected_components) >= 3:
            return "parallel"

        # Default
        return "hybrid"
