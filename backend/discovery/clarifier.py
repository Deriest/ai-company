"""Engineering Discovery Engine — Clarification Engine.

Generates targeted clarification questions and manages discovery rounds.
Follows the Question Policy from the SOT.
"""

import logging
from dataclasses import dataclass, field
from discovery.config import discovery_config
from discovery.readiness import ReadinessResult, DimensionScore
from discovery.requirements import ExtractionResult
from discovery.ambiguity import AmbiguityReport, Ambiguity

logger = logging.getLogger("aic.discovery.clarifier")


@dataclass
class ClarificationQuestion:
    """A structured clarification question."""

    id: str
    category: str  # scope, priority, technical, design, constraint, dependency, acceptance, risk
    question: str
    options: list[str] = field(default_factory=list)  # For multiple choice
    priority: str = "medium"  # high, medium, low
    relates_to: str = ""  # Dimension or field this addresses


@dataclass
class ClarificationResult:
    """Result of clarification generation."""

    questions: list[ClarificationQuestion] = field(default_factory=list)
    round_number: int = 0
    is_final: bool = False  # True if max rounds reached
    reason: str = ""


class ClarificationEngine:
    """Generates targeted clarification questions based on readiness gaps."""

    @classmethod
    def generate_questions(
        cls,
        readiness: ReadinessResult,
        extraction: ExtractionResult,
        ambiguity: AmbiguityReport,
        domain: str,
        round_number: int,
    ) -> ClarificationResult:
        """Generate clarification questions based on readiness gaps.

        Args:
            readiness: Current readiness evaluation
            extraction: Current requirement extraction
            ambiguity: Current ambiguity report
            domain: Engineering domain
            round_number: Current clarification round

        Returns:
            ClarificationResult with questions and metadata
        """
        # Check round limit
        if round_number >= discovery_config.max_clarification_rounds:
            return ClarificationResult(
                questions=[],
                round_number=round_number,
                is_final=True,
                reason=f"Maximum rounds ({discovery_config.max_clarification_rounds}) reached",
            )

        questions: list[ClarificationQuestion] = []
        question_id = 1

        # Generate questions for each low-scoring dimension
        for dim in readiness.dimension_details:
            if dim.score < discovery_config.dimension_floor:
                dim_questions = cls._generate_dimension_questions(
                    dim, domain, extraction, ambiguity, question_id
                )
                questions.extend(dim_questions)
                question_id += len(dim_questions)

        # Generate questions for missing fields
        for missing_field in readiness.missing_fields[:5]:  # Limit to 5 missing fields
            field_question = cls._generate_field_question(missing_field, domain, question_id)
            if field_question:
                questions.append(field_question)
                question_id += 1

        # Generate questions for high ambiguity
        if ambiguity.overall_score > 0.5:
            for amb in ambiguity.ambiguities[:3]:  # Limit to 3 ambiguity questions
                amb_question = cls._generate_ambiguity_question(amb, question_id)
                if amb_question:
                    questions.append(amb_question)
                    question_id += 1

        # Limit questions per round
        max_questions = discovery_config.max_questions_per_round
        if len(questions) > max_questions:
            # Prioritize: high > medium > low
            questions = cls._prioritize_questions(questions, max_questions)

        # Check if this is the final round
        is_final = (round_number + 1) >= discovery_config.max_clarification_rounds

        reason = ""
        if is_final:
            reason = "Final round — will force-complete after this"
        elif not questions:
            reason = "No clarification needed"

        return ClarificationResult(
            questions=questions,
            round_number=round_number,
            is_final=is_final,
            reason=reason,
        )

    @classmethod
    def _generate_dimension_questions(
        cls,
        dimension: DimensionScore,
        domain: str,
        extraction: ExtractionResult,
        ambiguity: AmbiguityReport,
        start_id: int,
    ) -> list[ClarificationQuestion]:
        """Generate questions for a low-scoring dimension."""
        questions = []

        if dimension.name == "intent_clarity":
            questions.append(ClarificationQuestion(
                id=f"Q{start_id}",
                category="scope",
                question="Could you describe what you're trying to achieve in one sentence?",
                priority="high",
                relates_to="intent_clarity",
            ))

        elif dimension.name == "scope_definition":
            questions.append(ClarificationQuestion(
                id=f"Q{start_id}",
                category="scope",
                question="What should be included in this change, and what should be explicitly excluded?",
                priority="high",
                relates_to="scope_definition",
            ))

        elif dimension.name == "requirement_completeness":
            if dimension.missing:
                missing_str = ", ".join(dimension.missing[:3])
                questions.append(ClarificationQuestion(
                    id=f"Q{start_id}",
                    category="technical",
                    question=f"I need more information about: {missing_str}. Can you provide details?",
                    priority="high",
                    relates_to="requirement_completeness",
                ))

        elif dimension.name == "constraint_awareness":
            questions.append(ClarificationQuestion(
                id=f"Q{start_id}",
                category="constraint",
                question="Are there any technical constraints, dependencies, or limitations I should be aware of?",
                priority="medium",
                relates_to="constraint_awareness",
            ))

        elif dimension.name == "acceptance_criteria":
            questions.append(ClarificationQuestion(
                id=f"Q{start_id}",
                category="acceptance",
                question="How will we know this is done? What should work correctly?",
                priority="medium",
                relates_to="acceptance_criteria",
            ))

        return questions

    @classmethod
    def _generate_field_question(
        cls,
        missing_field: str,
        domain: str,
        question_id: int,
    ) -> ClarificationQuestion | None:
        """Generate a question for a missing domain field."""
        # Map field names to conversational questions
        field_questions = {
            "component": "Which component or screen should this apply to?",
            "visual_behaviour": "What should the user see or experience?",
            "interaction": "How should the user interact with this?",
            "responsive": "Should this work on mobile, tablet, or desktop?",
            "design_system": "Is there a design system or style guide to follow?",
            "endpoint": "What API endpoint or route should this use?",
            "schema": "What should the request/response data look like?",
            "auth": "What authentication or permissions are needed?",
            "error_handling": "How should errors be handled?",
            "rate_limiting": "Are there rate limiting requirements?",
            "reproduction": "What are the steps to reproduce the issue?",
            "expected_behaviour": "What should happen vs what actually happens?",
            "affected_component": "Which part of the system is affected?",
            "severity": "How critical is this issue?",
            "regression_risk": "Could this change break other functionality?",
            "user_story": "Who is the user and what do they want to achieve?",
            "scope": "What's in scope and what's out of scope?",
            "acceptance": "What are the acceptance criteria?",
            "target_module": "Which module or file needs refactoring?",
            "structure": "What's the current structure vs desired structure?",
            "behaviour_preservation": "Should existing behaviour be preserved?",
            "test_coverage": "What test coverage is needed?",
            "doc_type": "What type of document (README, API docs, guide)?",
            "audience": "Who is the target audience?",
            "test_type": "What type of tests (unit, integration, e2e)?",
            "coverage": "What coverage percentage is targeted?",
            "framework": "Which test framework to use?",
            "environment": "Which environment (dev, staging, prod)?",
            "service_type": "What type of service or infrastructure?",
            "scaling": "What are the scaling requirements?",
            "current_arch": "What's the current architecture?",
            "proposed_arch": "What's the proposed architecture?",
            "migration": "What's the migration strategy?",
            "impact": "What's the impact analysis?",
            "threat_model": "What's the threat model?",
            "vulnerability": "What vulnerability needs addressing?",
            "mitigation": "What mitigation approach is preferred?",
            "current_metric": "What's the current performance metric?",
            "target_metric": "What's the target performance metric?",
            "bottleneck": "Where is the bottleneck?",
            "change_type": "What type of schema change?",
            "migration_strategy": "What migration strategy to use?",
            "data_integrity": "What data integrity constraints?",
            "model_provider": "Which AI model or provider?",
            "prompt_design": "What prompt or context design?",
            "fallback": "What fallback behaviour?",
            "token_budget": "What token or cost budget?",
            "automation_type": "What type of automation?",
            "trigger": "What triggers the automation?",
            "question": "What's the research question?",
            "output": "What's the expected output?",
        }

        question_text = field_questions.get(
            missing_field,
            f"Can you provide more details about {missing_field}?"
        )

        return ClarificationQuestion(
            id=f"Q{question_id}",
            category="technical",
            question=question_text,
            priority="high",
            relates_to=missing_field,
        )

    @classmethod
    def _generate_ambiguity_question(
        cls,
        ambiguity: Ambiguity,
        question_id: int,
    ) -> ClarificationQuestion | None:
        """Generate a question for a detected ambiguity."""
        if not ambiguity.suggestion:
            return None

        return ClarificationQuestion(
            id=f"Q{question_id}",
            category="scope",
            question=ambiguity.suggestion,
            priority="medium",
            relates_to=f"ambiguity_{ambiguity.type}",
        )

    @classmethod
    def _prioritize_questions(
        cls,
        questions: list[ClarificationQuestion],
        max_count: int,
    ) -> list[ClarificationQuestion]:
        """Prioritize questions and limit to max_count."""
        priority_order = {"high": 0, "medium": 1, "low": 2}
        sorted_questions = sorted(
            questions,
            key=lambda q: priority_order.get(q.priority, 1)
        )
        return sorted_questions[:max_count]

    @classmethod
    def format_questions_for_user(cls, result: ClarificationResult) -> str:
        """Format clarification questions for user display.

        Returns a conversational, non-interrogative question format.
        """
        if not result.questions:
            return ""

        lines = []

        if result.round_number == 0:
            lines.append("I have a few questions to ensure we get this right:")
        else:
            lines.append("A few more clarifications:")

        for q in result.questions:
            if q.options:
                # Multiple choice
                lines.append(f"\n{q.question}")
                for i, opt in enumerate(q.options, 1):
                    lines.append(f"  {i}. {opt}")
            else:
                # Open-ended
                lines.append(f"\n- {q.question}")

        if result.is_final:
            lines.append("\n(This is the last round of questions)")

        return "\n".join(lines)
