"""Engineering Discovery Engine — Readiness Evaluation.

5-axis weighted readiness scoring to determine if Planning can safely begin.
Domain-adaptive evaluation with mandatory field enforcement.
"""

import re
import logging
from dataclasses import dataclass, field
from discovery.config import discovery_config
from discovery.domains import DomainRegistry
from discovery.requirements import ExtractionResult
from discovery.ambiguity import AmbiguityReport

logger = logging.getLogger("aic.discovery.readiness")


@dataclass
class DimensionScore:
    """Score for a single readiness dimension."""

    name: str
    score: float  # 0.0 to 1.0
    weight: float  # 0.0 to 1.0
    reason: str = ""
    missing: list[str] = field(default_factory=list)


@dataclass
class ReadinessResult:
    """Result of Engineering Readiness evaluation."""

    is_ready: bool
    overall_score: float  # 0.0 to 1.0
    dimensions: dict[str, float]  # dimension_name → score
    dimension_details: list[DimensionScore] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    reason: str = ""


# Dimension weights (from SOT Section 12.1)
DIMENSION_WEIGHTS = {
    "intent_clarity": 0.30,
    "scope_definition": 0.25,
    "requirement_completeness": 0.25,
    "constraint_awareness": 0.10,
    "acceptance_criteria": 0.10,
}


class ReadinessEvaluator:
    """Evaluates Engineering Readiness across 5 dimensions."""

    @classmethod
    def evaluate(
        cls,
        extraction: ExtractionResult,
        ambiguity: AmbiguityReport,
        domain: str,
        content: str,
    ) -> ReadinessResult:
        """Evaluate Engineering Readiness.

        Args:
            extraction: Result of requirement extraction
            ambiguity: Result of ambiguity detection
            domain: Engineering domain
            content: Original user message

        Returns:
            ReadinessResult with is_ready, score, and dimensions
        """
        # Calculate each dimension
        dimensions = []
        missing_fields = []

        # 1. Intent Clarity (30%)
        intent_score = cls._score_intent_clarity(content, domain, ambiguity)
        dimensions.append(DimensionScore(
            name="intent_clarity",
            score=intent_score,
            weight=DIMENSION_WEIGHTS["intent_clarity"],
            reason="Intent clarity based on domain classification and ambiguity",
        ))

        # 2. Scope Definition (25%)
        scope_score, scope_missing = cls._score_scope_definition(extraction, content)
        dimensions.append(DimensionScore(
            name="scope_definition",
            score=scope_score,
            weight=DIMENSION_WEIGHTS["scope_definition"],
            reason="Scope definition based on requirement specificity",
            missing=scope_missing,
        ))
        missing_fields.extend(scope_missing)

        # 3. Requirement Completeness (25%)
        req_score, req_missing = cls._score_requirement_completeness(extraction, domain)
        dimensions.append(DimensionScore(
            name="requirement_completeness",
            score=req_score,
            weight=DIMENSION_WEIGHTS["requirement_completeness"],
            reason="Requirement completeness based on domain mandatory fields",
            missing=req_missing,
        ))
        missing_fields.extend(req_missing)

        # 4. Constraint Awareness (10%)
        constraint_score = cls._score_constraint_awareness(extraction, content)
        dimensions.append(DimensionScore(
            name="constraint_awareness",
            score=constraint_score,
            weight=DIMENSION_WEIGHTS["constraint_awareness"],
            reason="Constraint awareness based on detected constraints",
        ))

        # 5. Acceptance Criteria (10%)
        acceptance_score = cls._score_acceptance_criteria(extraction, content)
        dimensions.append(DimensionScore(
            name="acceptance_criteria",
            score=acceptance_score,
            weight=DIMENSION_WEIGHTS["acceptance_criteria"],
            reason="Acceptance criteria based on detected success conditions",
        ))

        # Calculate weighted overall score
        overall_score = sum(d.score * d.weight for d in dimensions)

        # Apply readiness threshold
        threshold = discovery_config.readiness_threshold
        dimension_floor = discovery_config.dimension_floor

        # Check dimension floor — no dimension below floor
        min_dimension = min(d.score for d in dimensions)
        dimension_floor_met = min_dimension >= dimension_floor

        # Ready if overall score meets threshold AND all dimensions above floor
        is_ready = overall_score >= threshold and dimension_floor_met

        # Generate reason
        if is_ready:
            reason = f"Engineering Ready (score: {overall_score:.2f} >= {threshold})"
        elif not dimension_floor_met:
            low_dims = [d.name for d in dimensions if d.score < dimension_floor]
            reason = f"Not ready — dimension floor not met for: {', '.join(low_dims)}"
        else:
            reason = f"Not ready — score {overall_score:.2f} < {threshold}"

        return ReadinessResult(
            is_ready=is_ready,
            overall_score=overall_score,
            dimensions={d.name: d.score for d in dimensions},
            dimension_details=dimensions,
            missing_fields=missing_fields,
            reason=reason,
        )

    @classmethod
    def _score_intent_clarity(
        cls,
        content: str,
        domain: str,
        ambiguity: AmbiguityReport,
    ) -> float:
        """Score intent clarity (30% weight).

        High score when:
        - Domain is clearly classified (not 'chat')
        - Low ambiguity
        - Sufficient message length
        """
        score = 0.5  # Base score

        # Domain classification bonus
        if domain and domain != "chat":
            score += 0.3

        # Ambiguity penalty
        ambiguity_penalty = ambiguity.overall_score * 0.3
        score -= ambiguity_penalty

        # Length bonus (longer messages tend to be clearer)
        words = content.split()
        if len(words) >= 10:
            score += 0.1
        if len(words) >= 20:
            score += 0.1

        return max(0.0, min(1.0, score))

    @classmethod
    def _score_scope_definition(
        cls,
        extraction: ExtractionResult,
        content: str,
    ) -> tuple[float, list[str]]:
        """Score scope definition (25% weight).

        Returns (score, missing_fields).
        """
        missing = []
        score = 0.3  # Base score

        # Check for scope-related keywords
        scope_keywords = [
            r"\b(specific|particular|only|just|limited|bounded)\b",
            r"\b(all|every|entire|complete|full)\b",
            r"\b(exclude|include|out of scope|in scope)\b",
        ]

        for pattern in scope_keywords:
            if re.search(pattern, content, re.I):
                score += 0.2
                break

        # Check for functional requirements (scope indicators)
        if extraction.functional:
            score += 0.2

        # Check for constraints (scope boundaries)
        if extraction.constraints:
            score += 0.1

        # Short messages may have unclear scope
        words = content.split()
        if len(words) < 5:
            missing.append("scope — message too short to determine scope")
            score -= 0.2

        return max(0.0, min(1.0, score)), missing

    @classmethod
    def _score_requirement_completeness(
        cls,
        extraction: ExtractionResult,
        domain: str,
    ) -> tuple[float, list[str]]:
        """Score requirement completeness (25% weight).

        Returns (score, missing_fields).
        """
        domain_obj = DomainRegistry.get(domain)
        if not domain_obj:
            return 0.5, []

        mandatory_fields = [f for f in domain_obj.mandatory_fields if f.required]
        if not mandatory_fields:
            return 1.0, []

        # Count covered mandatory fields
        covered = len(extraction.covered_fields)
        total = len(mandatory_fields)

        if total == 0:
            return 1.0, []

        # Calculate coverage ratio — more lenient
        coverage_ratio = covered / total

        # Base score from coverage — give credit for partial coverage
        score = 0.4 + (coverage_ratio * 0.6)  # At least 0.4 for any request

        # Small penalty for missing critical fields
        missing = extraction.missing_fields
        if missing:
            score -= 0.05 * min(len(missing), 3)  # Smaller penalty

        return max(0.4, min(1.0, score)), missing

    @classmethod
    def _score_constraint_awareness(
        cls,
        extraction: ExtractionResult,
        content: str,
    ) -> float:
        """Score constraint awareness (10% weight).

        High score when constraints are explicitly stated or can be inferred.
        """
        score = 0.5  # Base score (assume reasonable defaults)

        # Explicit constraints
        if extraction.constraints:
            score += 0.3

        # Dependencies indicate constraint awareness
        if extraction.dependencies:
            score += 0.1

        # Assumptions indicate thinking about context
        if extraction.assumptions:
            score += 0.1

        return max(0.0, min(1.0, score))

    @classmethod
    def _score_acceptance_criteria(
        cls,
        extraction: ExtractionResult,
        content: str,
    ) -> float:
        """Score acceptance criteria (10% weight).

        High score when success conditions are defined.
        """
        score = 0.5  # Higher base score

        # Explicit acceptance criteria
        if extraction.acceptance_criteria:
            score += 0.3

        # Check for success-related keywords
        success_patterns = [
            r"\b(should|must|will|shall)\b",
            r"\b(done|complete|finished|ready)\b",
            r"\b(test|verify|validate|check)\b",
            r"\b(work|function|operate)\b",
        ]

        for pattern in success_patterns:
            if re.search(pattern, content, re.I):
                score += 0.1
                break

        return max(0.4, min(1.0, score))
