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
from discovery.intent import IntentResult

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
        intent: "IntentResult | None" = None,
    ) -> ClarificationResult:
        """Generate clarification questions based on readiness gaps.

        Args:
            readiness: Current readiness evaluation
            extraction: Current requirement extraction
            ambiguity: Current ambiguity report
            domain: Engineering domain
            round_number: Current clarification round
            intent: Classified intent/domain (if available) — used to ask
                intent-first questions (goal/audience/example) before technical
                readiness gaps.

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

        # Intent-first questions (round 0): before diving into technical gaps,
        # clarify the goal, audience, and a concrete success example. This keeps
        # discovery conversational and intent-driven instead of leading with a
        # technical checklist (e.g. asking about testing strategy for "make a website").
        if round_number == 0 and intent is not None:
            intent_first = cls._generate_intent_first_questions(intent, question_id)
            questions.extend(intent_first)
            question_id += len(intent_first)

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

    # ── LLM-generated discovery questions ─────────────────────────────
    # The user finds static/technical clarification checklists confusing
    # ("make a website" → questions about testing strategy). Ask the LLM to
    # generate conversational, intent-first questions, falling back to the
    # static generator if the LLM is unavailable or returns malformed output.

    _DISCOVERY_PROMPT = """You are an expert engineering discovery assistant.
A user wants to build something. Ask clarifying questions that understand WHAT
they want and WHY — not HOW to implement it.

Round focus: {round_guide}
Domain: {domain}

QUESTION QUALITY BAR (strict):
- NEVER ask vague open-ended questions like "What's in scope?" or "What are the acceptance criteria?"
- Instead, ask CONCRETE questions that offer 2-4 specific options the user can pick from.
- Prefer multiple-choice style: "What's the main purpose — (a) company profile, (b) online store, (c) portfolio, (d) blog?"
- Each question should be answerable in one short sentence.
- Ask 3-5 questions MAX. The first 1-2 MUST be intent-first (purpose, target users, or a concrete example/reference site).

GOOD EXAMPLES by domain:
- website/app: main purpose (offer options), target audience, pages needed (offer a list), any reference site they like, content readiness (has text/images vs needs placeholders)
- api/backend: who consumes it (offer options), core resources/entities, auth needed or not, expected scale (small/medium/large)
- bugfix: what should happen vs what actually happens, how to reproduce, where it happens (page/feature)
- docs: which part to document, target reader (user vs developer), format (README/guide/API ref)

Rules:
- NEVER ask about testing frameworks, CI/CD, or coverage unless the user mentioned testing
- Adapt to the domain: "{domain}"
- Match the user's language (if they write in Indonesian, respond in Indonesian; otherwise English)
- Be conversational, not interrogative
- If the request is already specific enough, ask fewer questions (even just 1-2).

User's request: "{content}"
{history_section}
{gaps_section}

Respond ONLY as a JSON array:
[{{"id": "Q1", "question": "...", "category": "intent|scope|technical|acceptance", "priority": "high|medium"}}]"""

    @classmethod
    async def generate_questions_async(
        cls,
        readiness: ReadinessResult,
        extraction: ExtractionResult,
        ambiguity: AmbiguityReport,
        domain: str,
        round_number: int,
        user_content: str = "",
        history: list | None = None,
        intent: "IntentResult | None" = None,
    ) -> ClarificationResult:
        """LLM-generated contextual questions. Falls back to static on failure."""
        if round_number >= discovery_config.max_clarification_rounds:
            return ClarificationResult(
                questions=[], round_number=round_number,
                is_final=True, reason="Maximum rounds reached",
            )

        try:
            questions = await cls._generate_llm_questions(
                user_content, domain, round_number, history, intent, readiness, extraction
            )
            if questions:
                max_q = discovery_config.max_questions_per_round
                if len(questions) > max_q:
                    questions = cls._prioritize_questions(questions, max_q)
                is_final = (round_number + 1) >= discovery_config.max_clarification_rounds
                return ClarificationResult(
                    questions=questions, round_number=round_number, is_final=is_final,
                    reason="Generated by LLM",
                )
        except Exception as e:
            logger.warning(f"LLM question generation failed, using static fallback: {e}")

        return cls.generate_questions(readiness, extraction, ambiguity, domain, round_number)

    @classmethod
    async def _generate_llm_questions(
        cls,
        content: str,
        domain: str,
        round_number: int,
        history: list | None,
        intent: "IntentResult | None",
        readiness: ReadinessResult,
        extraction: ExtractionResult,
    ) -> list:
        from llm.provider import provider_manager, ModelTier

        provider = provider_manager.get_active_with_key()
        if not provider:
            raise RuntimeError("No LLM provider")

        gaps = []
        if readiness is not None:
            if readiness.missing_fields:
                gaps.append(f"Missing information about: {', '.join(readiness.missing_fields[:5])}")
            for dim in readiness.dimension_details:
                if dim.score < 0.6:
                    gaps.append(f"Weak area: {dim.name} (score {dim.score:.0%})")
        gaps_section = "\n".join(gaps) if gaps else "No specific gaps identified yet."

        history_section = ""
        if history:
            recent = history[-3:] if len(history) > 3 else history
            lines = [
                f"- {m.get('role', '?')}: {str(m.get('content', ''))[:200]}"
                for m in recent if isinstance(m, dict)
            ]
            history_section = "Recent conversation:\n" + "\n".join(lines)

        round_guide = (
            "First questions — focus on purpose, audience, and success criteria"
            if round_number == 0
            else "Follow-up — drill into gaps from previous answers"
        )
        prompt = cls._DISCOVERY_PROMPT.format(
            round_guide=round_guide,
            domain=domain or "general",
            content=str(content)[:1000],
            history_section=history_section,
            gaps_section=gaps_section,
        )

        result = await provider.chat(
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": str(content)[:500]},
            ],
            tier=ModelTier.SPRINTER,
            temperature=0.6,
            max_tokens=600,
            purpose="discovery_questions",
        )

        raw = (result.get("content", "") or "").strip()
        return cls._parse_llm_questions(raw)

    @classmethod
    def _parse_llm_questions(cls, raw: str) -> list:
        """Parse LLM JSON response into ClarificationQuestion objects."""
        import json
        import re
        
        try:
            if raw.startswith("```"):
                raw = re.sub(r"^```(?:json)?\s*", "", raw)
                raw = re.sub(r"\s*```$", "", raw)

            match = re.search(r"\[[\s\S]*\]", raw)
            if not match:
                return []  # No JSON array found

            items = json.loads(match.group())
            if not isinstance(items, list):
                return []  # Not a list

            questions = []
            for item in items[:7]:
                q_text = (item.get("question", "") or "").strip()
                if not q_text or len(q_text) < 10:
                    continue
                questions.append(ClarificationQuestion(
                    id=item.get("id", f"Q{len(questions) + 1}"),
                    category=item.get("category", "scope"),
                    question=q_text,
                    priority=item.get("priority", "medium"),
                    relates_to="llm_generated",
                ))
            
            return questions
        except (ValueError, TypeError, json.JSONDecodeError):
            return []  # Invalid JSON - fallback will use static questions

        if not questions:
            raise ValueError("No valid questions parsed from LLM response")
        return questions

    @classmethod
    def _generate_intent_first_questions(
        cls,
        intent: IntentResult,
        start_id: int,
    ) -> list[ClarificationQuestion]:
        """Generate intent-first clarifying questions (goal / audience / example).

        These run on the first discovery round so engagement starts with why and
        for-whom, before any technical readiness gaps. Questions are phrased in
        English by default.
        """
        domain = (intent.domain or "").lower()
        questions: list[ClarificationQuestion] = []
        cid = start_id

        # Goal / purpose — always the first question.
        questions.append(ClarificationQuestion(
            id=f"Q{cid}",
            category="intent",
            question="What is the main goal you want to achieve?",
            priority="high",
        ))
        cid += 1

        # Audience — relevant for most build/intent requests.
        questions.append(ClarificationQuestion(
            id=f"Q{cid}",
            category="intent",
            question="Who is the target audience or user of this?",
            priority="high",
        ))
        cid += 1

        # Concrete example succeeds for feature/website/refactor intents.
        if domain in ("feature", "ui", "frontend", "coding", "refactor", "architecture"):
            questions.append(ClarificationQuestion(
                id=f"Q{cid}",
                category="intent",
                question="Can you give a concrete example of the desired outcome?",
                priority="medium",
            ))
            cid += 1

        return questions

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
