"""Planning Engine — Risk Assessment.

Identifies risks and mitigation strategies.
"""

import logging
from planning.analyzer import BriefAnalysis
from planning.models import RiskMitigation

logger = logging.getLogger("aic.planning.risk")


# Risk templates
RISK_TEMPLATES = {
    "database_migration": {
        "risk": "Database migration may fail or cause data loss",
        "likelihood": "medium",
        "impact": "high",
        "mitigation": "Test migration on copy of production data first",
        "fallback": "Rollback migration and restore from backup",
    },
    "breaking_api_changes": {
        "risk": "API changes may break existing clients",
        "likelihood": "medium",
        "impact": "high",
        "mitigation": "Version API endpoints, maintain backward compatibility",
        "fallback": "Revert to previous API version",
    },
    "ui_regression": {
        "risk": "UI changes may introduce visual regressions",
        "likelihood": "medium",
        "impact": "medium",
        "mitigation": "Visual regression testing, screenshot comparison",
        "fallback": "Revert UI changes",
    },
    "auth_vulnerability": {
        "risk": "Authentication changes may introduce security vulnerabilities",
        "likelihood": "low",
        "impact": "critical",
        "mitigation": "Security review, penetration testing",
        "fallback": "Revert auth changes, notify users",
    },
    "integration_failure": {
        "risk": "Component integration may fail",
        "likelihood": "medium",
        "impact": "medium",
        "mitigation": "Integration tests, staged rollout",
        "fallback": "Rollback to last working state",
    },
    "performance_degradation": {
        "risk": "Changes may degrade performance",
        "likelihood": "medium",
        "impact": "medium",
        "mitigation": "Performance testing, benchmarking",
        "fallback": "Optimize or revert changes",
    },
    "test_coverage_gap": {
        "risk": "Insufficient test coverage may miss bugs",
        "likelihood": "medium",
        "impact": "medium",
        "mitigation": "Require minimum coverage, code review",
        "fallback": "Add tests for missed areas",
    },
    "dependency_conflict": {
        "risk": "New dependencies may conflict with existing ones",
        "likelihood": "low",
        "impact": "medium",
        "mitigation": "Dependency analysis, version pinning",
        "fallback": "Find alternative dependencies",
    },
}


class RiskAssessor:
    """Identifies risks and mitigation strategies."""

    @classmethod
    def assess_risks(
        cls,
        analysis: BriefAnalysis,
        brief_data: dict,
    ) -> list[RiskMitigation]:
        """Assess risks based on analysis.

        Args:
            analysis: Brief analysis result
            brief_data: Original brief data

        Returns:
            List of risk mitigations
        """
        risks = []

        # Database risks
        if analysis.requires_database_changes:
            template = RISK_TEMPLATES["database_migration"]
            risks.append(RiskMitigation(**template))

        # API risks
        if analysis.requires_api_changes:
            template = RISK_TEMPLATES["breaking_api_changes"]
            risks.append(RiskMitigation(**template))

        # UI risks
        if analysis.requires_ui_changes:
            template = RISK_TEMPLATES["ui_regression"]
            risks.append(RiskMitigation(**template))

        # Auth risks
        if "auth" in analysis.affected_components:
            template = RISK_TEMPLATES["auth_vulnerability"]
            risks.append(RiskMitigation(**template))

        # Integration risks (always)
        template = RISK_TEMPLATES["integration_failure"]
        risks.append(RiskMitigation(**template))

        # Performance risks (for high complexity)
        if analysis.complexity in ("high", "very_high"):
            template = RISK_TEMPLATES["performance_degradation"]
            risks.append(RiskMitigation(**template))

        # Test coverage risks (always)
        template = RISK_TEMPLATES["test_coverage_gap"]
        risks.append(RiskMitigation(**template))

        # Dependency risks (for multiple technologies)
        if len(analysis.technology_stack) > 2:
            template = RISK_TEMPLATES["dependency_conflict"]
            risks.append(RiskMitigation(**template))

        return risks
