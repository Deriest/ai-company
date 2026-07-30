"""Planning Engine — Plan Validation.

Validates Engineering Plans for completeness and feasibility.
"""

import logging
from planning.models import EngineeringPlan, PlanValidation
from planning.config import planning_config

logger = logging.getLogger("aic.planning.validator")


class PlanValidator:
    """Validates Engineering Plans."""

    @classmethod
    def validate(cls, plan: EngineeringPlan) -> PlanValidation:
        """Validate an Engineering Plan.

        Args:
            plan: Plan to validate

        Returns:
            PlanValidation with is_valid, errors, warnings
        """
        errors = []
        warnings = []

        # Required fields
        if not plan.engineering_goal:
            errors.append("engineering_goal is required")
        if not plan.technical_approach:
            errors.append("technical_approach is required")
        if not plan.implementation_strategy:
            errors.append("implementation_strategy is required")

        # Implementation strategy
        valid_strategies = ["sequential", "parallel", "hybrid", "incremental"]
        if plan.implementation_strategy not in valid_strategies:
            errors.append(f"Invalid implementation_strategy: {plan.implementation_strategy}")

        # Architecture decisions
        if not plan.architecture_decisions:
            warnings.append("No architecture decisions made")
        elif len(plan.architecture_decisions) > planning_config.max_architecture_decisions:
            warnings.append(f"Too many architecture decisions ({len(plan.architecture_decisions)})")

        # Risk mitigations
        if planning_config.require_risk_mitigation and not plan.risk_mitigations:
            errors.append("risk_mitigations is required")

        # Confidence score
        if plan.confidence_score < planning_config.min_confidence_score:
            warnings.append(f"Low confidence score: {plan.confidence_score:.2f}")

        # Effort estimates
        if not plan.effort_estimates:
            warnings.append("No effort estimates")

        # Acceptance criteria
        if not plan.acceptance_criteria:
            warnings.append("No acceptance criteria defined")

        return PlanValidation(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    @classmethod
    def calculate_confidence(cls, plan: EngineeringPlan) -> float:
        """Calculate confidence score for a plan.

        Returns:
            Confidence score from 0.0 to 1.0
        """
        scores = []

        # Architecture decisions confidence
        if plan.architecture_decisions:
            decision_scores = {
                "low": 0.9,
                "medium": 0.7,
                "high": 0.5,
            }
            avg_decision_risk = sum(
                decision_scores.get(d.risk_level, 0.7)
                for d in plan.architecture_decisions
            ) / len(plan.architecture_decisions)
            scores.append(avg_decision_risk)
        else:
            scores.append(0.5)

        # Risk mitigation confidence
        if plan.risk_mitigations:
            risk_scores = {
                "low": 0.9,
                "medium": 0.7,
                "high": 0.5,
            }
            avg_risk = sum(
                risk_scores.get(r.likelihood, 0.7)
                for r in plan.risk_mitigations
            ) / len(plan.risk_mitigations)
            scores.append(avg_risk)
        else:
            scores.append(0.5)

        # Effort estimate confidence
        if plan.effort_estimates:
            avg_effort_confidence = sum(
                e.confidence for e in plan.effort_estimates
            ) / len(plan.effort_estimates)
            scores.append(avg_effort_confidence)
        else:
            scores.append(0.5)

        # Acceptance criteria confidence
        if plan.acceptance_criteria:
            scores.append(0.8)
        else:
            scores.append(0.5)

        return sum(scores) / len(scores) if scores else 0.5
