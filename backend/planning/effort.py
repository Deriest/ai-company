"""Planning Engine — Effort Estimation.

Estimates effort for requirements based on complexity analysis.
"""

import logging
from planning.analyzer import BriefAnalysis
from planning.models import EffortEstimate

logger = logging.getLogger("aic.planning.effort")


# Complexity to hours mapping
COMPLEXITY_HOURS = {
    "low": (1, 4),        # 1-4 hours
    "medium": (4, 16),    # 4-16 hours
    "high": (16, 40),     # 16-40 hours
    "very_high": (40, 80), # 40-80 hours
}


class EffortEstimator:
    """Estimates effort for requirements."""

    @classmethod
    def estimate_effort(
        cls,
        analysis: BriefAnalysis,
        brief_data: dict,
    ) -> list[EffortEstimate]:
        """Estimate effort for each requirement.

        Args:
            analysis: Brief analysis result
            brief_data: Original brief data

        Returns:
            List of effort estimates
        """
        estimates = []

        # Get requirements
        requirements = brief_data.get("functional_requirements", [])

        for i, req in enumerate(requirements, 1):
            if not isinstance(req, dict) or not req.get("description"):
                continue

            req_id = req.get("id", f"REQ-{i:03d}")
            description = req["description"]

            # Estimate complexity for this requirement
            complexity = cls._estimate_requirement_complexity(description, analysis)

            # Calculate hours
            hours_range = COMPLEXITY_HOURS.get(complexity, (4, 16))
            estimated_hours = (hours_range[0] + hours_range[1]) / 2

            # Calculate confidence
            confidence = cls._calculate_confidence(complexity, analysis)

            estimates.append(EffortEstimate(
                requirement_id=req_id,
                complexity=complexity,
                estimated_hours=estimated_hours,
                confidence=confidence,
            ))

        return estimates

    @classmethod
    def _estimate_requirement_complexity(
        cls,
        description: str,
        analysis: BriefAnalysis,
    ) -> str:
        """Estimate complexity for a single requirement."""
        lower = description.lower()

        # Check for complexity indicators
        if any(word in lower for word in ["simple", "small", "minor", "fix", "patch"]):
            return "low"

        if any(word in lower for word in ["complex", "significant", "major", "refactor", "migrate"]):
            return "high"

        if any(word in lower for word in ["architecture", "system", "platform", "from scratch"]):
            return "very_high"

        # Default based on overall analysis
        return analysis.complexity

    @classmethod
    def _calculate_confidence(
        cls,
        complexity: str,
        analysis: BriefAnalysis,
    ) -> float:
        """Calculate confidence in the estimate."""
        base_confidence = {
            "low": 0.8,
            "medium": 0.7,
            "high": 0.6,
            "very_high": 0.5,
        }.get(complexity, 0.6)

        # Adjust based on technology stack familiarity
        if len(analysis.technology_stack) > 3:
            base_confidence -= 0.1

        # Adjust based on scope
        if analysis.scope_size in ("large", "very_large"):
            base_confidence -= 0.1

        return max(0.3, min(1.0, base_confidence))

    @classmethod
    def estimate_total_duration(cls, estimates: list[EffortEstimate]) -> str:
        """Estimate total duration from effort estimates."""
        if not estimates:
            return "Unknown"

        total_hours = sum(e.estimated_hours for e in estimates)

        if total_hours <= 4:
            return "Less than half a day"
        elif total_hours <= 8:
            return "About 1 day"
        elif total_hours <= 16:
            return "1-2 days"
        elif total_hours <= 40:
            return "3-5 days"
        elif total_hours <= 80:
            return "1-2 weeks"
        else:
            return "2+ weeks"
