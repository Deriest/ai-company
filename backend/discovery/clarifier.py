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
                    dim, domain, extraction, ambiguity, question_id, intent
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

SUPERPOWERS-STYLE GUIDED DISCOVERY (TARGETING 80-85% CONFIDENCE):

GOAL: Build a crystal-clear requirements blueprint so we build EXACTLY what you need.

APPROACH:
1. START SMART (Round 1): Ask 3-5 focused questions covering all key dimensions
   • Purpose/goal (What business/personal problem are you solving?)
   • Target audience/users (Who will use this?)
   • Core pages/features (The absolute essentials: home page, contact form, etc.)
   • Design style preference (Minimalist/modern/playful/professional?)
   • Tech stack familiarity (Comfortable with modern frameworks vs plain HTML?)

2. DRILL DEEPER (Rounds 2-3): Follow up based on gaps in user's answers
   • If purpose vague → ask about success metrics/goals
   • If features unclear → ask about must-have pages/sections
   • If no tech prefs stated → suggest modern approach AND ask if they prefer alternatives
   • Always confirm critical decisions before proceeding

3. VALIDATE UNDERSTANDING: End with one summary question
   • "Just to confirm: you want a [X]-purpose website for [audience], focusing on [pages] with [style/design], correct?"

RULES FOR QUESTIONS:
• Each question MUST include 2-4 concrete multiple-choice options (like this example:)
  ❌ BAD: "What's the tech stack?" (too open-ended)
  ✅ GOOD: "Tech stack comfort level — (a) I know React/Next.js well, (b) Familiar with Vue/Nuxt, (c) Prefer plain HTML/CSS, (d) No preference, recommend what's best"
• Prioritize decision-making over information-gathering
• Don't ask about things the user just mentioned (active listening!)
• Keep each question answerable in ONE short sentence or option selection
• NEVER ask generic stuff like "What's in scope?" — always offer concrete examples

ROUND 1 EXAMPLE (website):
- Main purpose — (a) showcase company services/products, (b) sell products online, (c) build portfolio/showcase work, (d) share thoughts/blog, (e) recruit talent?
- Primary users — (a) potential customers seeking solutions, (b) job candidates, (c) media/partners, (d) general public browsing?
- Must-have sections/pages — (a) Home+About+Contact basic 3-pager, (b) Blog/Resources section, (c) Product/Services catalog, (d) Team member profiles?
- Design vibe — (a) Clean minimalist corporate, (b) Bold creative modern, (c) Warm friendly welcoming, (d) Professional trustworthy?
- Tech comfort — (a) React/Next.js familiar, (b) Vue/Nuxt comfortable, (c) Plain HTML/CSS okay, (d) Recommend modern stack?

Confidence checkpoints:
• <60% after Round 1 → Ask 2-3 more targeted follow-ups in Round 2
• 60-80% → One validation round (summarize understanding, ask "any additions?")  
• ≥80-85% → Perfect! Move to Engineering Brief generation

NEVER:
• Ask 10 generic open-ended questions upfront
• Skip critical decisions hoping user clarifies later
• Use technical jargon they might not understand

QUESTION QUALITY BAR (strict):
- NEVER ask vague open-ended questions like "What's in scope?" or "What are the acceptance criteria?"
- Instead, ask CONCRETE questions that offer 2-4 specific options the user can pick from.
- Prefer multiple-choice style: "What's the main purpose — (a) company profile, (b) online store, (c) portfolio, (d) blog?"
- Each question should be answerable in one short sentence.
- For website/app requests, ALWAYS include at least one question about **tech stack** if not explicitly stated by user:
  • Example: "Tech stack preference — (a) React/Next.js, (b) Vue/Nuxt, (c) plain HTML/CSS/JS, (d) no preference"
  • If user says "modern" or "fast", assume frameworks and still confirm which ones
  • Don't skip this step unless user explicitly says "just give me whatever works"
- First 1-2 questions MUST be intent-first (purpose, target users, or a concrete example/reference site)
- Follow-up questions should drill into identified gaps, not repeat earlier questions
- Tech-related follow-ups include: database needs (any? yes/no + which type?), hosting preference (cloud vs self-hosted), auth required (login/signup features)?

GOOD EXAMPLES by domain:
- website/app: main purpose (offer options + "other"), target audience, pages needed (offer checklist), reference sites they like, content readiness (has text/images vs needs placeholders), design preferences (minimalist/modern/bold?), tech stack familiarity (offer options + "recommend best")
  Example: "Tech comfort level — (a) I know React/Next.js well, (b) Familiar with Vue/Nuxt, (c) Prefer plain HTML/CSS, (d) Recommend what's best → OR specify your own preference"
- api/backend: who consumes it (web/mobile/third-party), core resources/entities, auth needed or not, expected scale (small/medium/large), deployment environment (cloud/self-hosted)
- bugfix: what should happen vs what actually happens, how to reproduce, where it happens (page/feature), recent changes before it broke, workaround exists?
- docs: which part to document, target reader (end-users/developers/integrators), format preference (step-by-step tutorial/reference-guide/API-ref), existing materials available

Rules:
- NEVER ask about testing frameworks, CI/CD, or coverage unless the user mentioned testing
- Track your own confidence and stop asking when you have it (aim for ≥80%)
- Adapt to the domain: "{domain}"
- Match the user's language (if they write in Indonesian, respond in Indonesian; otherwise English)
- Be conversational, not interrogative
- Avoid repetitive questions — each new question must address a NEW gap

User's request: "{content}"
{history_section}
{gaps_section}

Confidence assessment guide:
- HIGH (80%+): Purpose clear, audience understood, key deliverables known, tech stack implied
- MEDIUM (50-79%): Some assumptions made about scope/pages/features
- LOW (<50%): Major gaps in purpose, audience, or success criteria

Respond ONLY as a JSON array. Every question MUST include an "options" array
with 2-4 concrete choices the user can pick from (the UI renders them as
clickable choices, plus a free-text "specify your own" field):
[{{"id": "Q1", "question": "...", "options": ["choice A", "choice B", "choice C"], "category": "intent|scope|technical|acceptance|followup", "priority": "high|medium|low"}}]"""

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
            raise RuntimeError(
                "No LLM provider configured with usable API key — discovery questions require an active AI provider. "
                "Please configure your LLM provider in Settings → Providers first."
            )

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
                
                # Parse multi-choice options if present
                options = []
                if "options" in item and isinstance(item["options"], list):
                    options = [str(o).strip() for o in item["options"] if o]
                
                questions.append(ClarificationQuestion(
                    id=item.get("id", f"Q{len(questions) + 1}"),
                    category=item.get("category", "scope"),
                    question=q_text,
                    options=options,
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
            options=[
                "Solve a specific problem I'm having",
                "Build a new capability from scratch",
                "Improve or extend something existing",
                "Automate something manual",
            ],
        ))
        cid += 1

        # Audience — relevant for most build/intent requests.
        questions.append(ClarificationQuestion(
            id=f"Q{cid}",
            category="intent",
            question="Who is the target audience or user of this?",
            priority="high",
            options=[
                "Just me / my team",
                "End users of a product",
                "Other developers (API/tools)",
                "Internal stakeholders",
            ],
        ))
        cid += 1

        # Concrete example succeeds for feature/website/refactor intents.
        if domain in ("feature", "ui", "frontend", "coding", "refactor", "architecture"):
            questions.append(ClarificationQuestion(
                id=f"Q{cid}",
                category="intent",
                question="Can you give a concrete example of the desired outcome?",
                priority="medium",
                options=[
                    "Yes — I'll describe the end result",
                    "I have a reference/example to point at",
                    "No example yet — describe options first",
                ],
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
        intent: "IntentResult | None" = None,
    ) -> list[ClarificationQuestion]:
        """Generate context-aware questions for a low-scoring dimension.

        BUG-3 FIX: questions now use the classified domain/intent and include
        concrete multiple-choice options instead of a single generic prompt
        (e.g. the old scope question was always "What should be included or
        excluded?" regardless of task type). Every question carries an
        options array so the UI renders clickable, context-rich choices.
        """
        questions = []

        # Prefer the classified intent domain; fall back to the passed domain.
        domain_text = ((intent.domain if intent else None) or domain or "").lower()

        if dimension.name == "intent_clarity":
            # Personalize based on classified goal/intent when available
            goal_hint = ""
            if domain_text in ("bugfix",):
                goal_hint = "For fixing this bug:"
            elif domain_text in ("docs", "documentation"):
                goal_hint = "For creating documentation:"
            elif domain_text in ("test", "testing"):
                goal_hint = "For adding tests:"
            
            questions.append(ClarificationQuestion(
                id=f"Q{start_id}",
                category="intent",
                question=(
                    f"{goal_hint} To make sure we build exactly what you need, "
                    f"what outcome would make this a success?"
                ),
                priority="high",
                relates_to="intent_clarity",
                options=[
                    "Build something new from scratch",
                    "Fix a bug or broken behaviour",
                    "Add a feature to existing code",
                    "Improve/refactor what's already there",
                    "Not sure yet — help me decide",
                ],
            ))

        elif dimension.name == "scope_definition":
            # Context-aware scope options per domain instead of the generic
            # "what should be included/excluded" question.
            if domain_text in ("frontend", "ui", "website", "coding", "feature"):
                questions.append(ClarificationQuestion(
                    id=f"Q{start_id}",
                    category="scope",
                    question="Which parts of this are must-haves for the first version?",
                    priority="high",
                    relates_to="scope_definition",
                    options=[
                        "Core UI/page with basic layout",
                        "Core UI + user interactions (forms, buttons, state)",
                        "Core UI + data fetching/backend hookup",
                        "Everything above plus polished styling",
                        "Just a minimal proof-of-concept",
                    ],
                ))
            elif domain_text in ("backend", "api", "database"):
                questions.append(ClarificationQuestion(
                    id=f"Q{start_id}",
                    category="scope",
                    question="Which API/data capabilities are in scope for this change?",
                    priority="high",
                    relates_to="scope_definition",
                    options=[
                        "CRUD endpoints for the main resource",
                        "CRUD + validation and error handling",
                        "CRUD + authentication/permissions",
                        "Full feature incl. pagination/filtering",
                        "Just the single endpoint I described",
                    ],
                ))
            elif domain_text in ("bugfix",):
                questions.append(ClarificationQuestion(
                    id=f"Q{start_id}",
                    category="scope",
                    question="How far should the fix go?",
                    priority="high",
                    relates_to="scope_definition",
                    options=[
                        "Minimal fix for the reported symptom only",
                        "Fix the root cause",
                        "Fix root cause + add a regression test",
                        "Fix + clean up related code",
                    ],
                ))
            elif domain_text in ("test", "testing"):
                questions.append(ClarificationQuestion(
                    id=f"Q{start_id}",
                    category="scope",
                    question="What scope of testing do you need?",
                    priority="high",
                    relates_to="scope_definition",
                    options=[
                        "Unit tests for core logic",
                        "Integration tests for the flow I described",
                        "End-to-end test of the user journey",
                        "Both unit + integration",
                        "Just enough to cover the happy path",
                    ],
                ))
            elif domain_text in ("docs", "documentation"):
                questions.append(ClarificationQuestion(
                    id=f"Q{start_id}",
                    category="scope",
                    question="What should the documentation cover?",
                    priority="high",
                    relates_to="scope_definition",
                    options=[
                        "Quick-start / getting started",
                        "Full feature reference",
                        "API reference for developers",
                        "Troubleshooting / FAQ",
                        "Just the part I mentioned",
                    ],
                ))
            else:
                questions.append(ClarificationQuestion(
                    id=f"Q{start_id}",
                    category="scope",
                    question="For this request, what's in scope and what can we skip for now?",
                    priority="high",
                    relates_to="scope_definition",
                    options=[
                        "Everything I described",
                        "The core part only — extras later",
                        "Core + error handling",
                        "A minimal working version",
                        "I'll describe the exact scope",
                    ],
                ))

        elif dimension.name == "requirement_completeness":
            if dimension.missing:
                missing_str = ", ".join(dimension.missing[:3])
                questions.append(ClarificationQuestion(
                    id=f"Q{start_id}",
                    category="technical",
                    question=f"I need a bit more detail on: {missing_str}. Which applies?",
                    priority="high",
                    relates_to="requirement_completeness",
                    options=[
                        "I'll provide specifics now",
                        "Use sensible defaults for these",
                        "These aren't needed — skip them",
                        "Recommend the best approach for these",
                    ],
                ))

        elif dimension.name == "constraint_awareness":
            questions.append(ClarificationQuestion(
                id=f"Q{start_id}",
                category="constraint",
                question=f"Any constraints I should respect for this {domain_text or 'change'}?",
                priority="medium",
                relates_to="constraint_awareness",
                options=[
                    "Must match existing code style/patterns",
                    "Must work with the current stack",
                    "There's a deadline — keep it lean",
                    "No special constraints",
                    "I have specific constraints to share",
                ],
            ))

        elif dimension.name == "acceptance_criteria":
            questions.append(ClarificationQuestion(
                id=f"Q{start_id}",
                category="acceptance",
                question="How will we know this is done and working correctly?",
                priority="medium",
                relates_to="acceptance_criteria",
                options=[
                    "The behaviour I described works",
                    "Works + no regressions",
                    "Works + tests pass",
                    "Works + reviewed/polished",
                    "I'll define acceptance criteria myself",
                ],
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
        """Generate a question for a detected ambiguity.

        BUG-3 FIX: include context-rich options derived from the detected
        ambiguity type so the question is actionable instead of a bare
        suggestion string with nothing to pick from.
        """
        if not ambiguity.suggestion:
            return None

        # Options keyed by ambiguity type — concrete, pickable clarifications.
        options_by_type = {
            "lexical": [
                "I mean the UI element / component",
                "I mean the backend service / API",
                "I mean the database / stored data",
                "I'll name the exact element",
            ],
            "referential": [
                "It refers to the feature I described",
                "It refers to the existing code/system",
                "It refers to a new thing we're adding",
                "I'll specify exactly what it refers to",
            ],
            "scope": [
                "Only the part I explicitly described",
                "That feature plus its direct dependencies",
                "The full flow end-to-end",
                "I'll define the boundaries myself",
            ],
            "technical": [
                "Use the standard/default configuration",
                "Optimize for speed/performance",
                "Optimize for simplicity/maintainability",
                "I have specific technical requirements",
            ],
            "missing_context": [
                "Use the current project context",
                "It's a greenfield — no existing context",
                "I'll provide the missing context",
                "Make a reasonable assumption and note it",
            ],
            "conflicting": [
                "The first requirement wins",
                "The second requirement wins",
                "Balance both — explain the trade-off",
                "I'll resolve the conflict myself",
            ],
            "temporal": [
                "As soon as possible — no hard deadline",
                "There's a specific deadline (I'll share it)",
                "It's an ongoing/iterative task",
                "Timing doesn't matter for this",
            ],
        }
        options = options_by_type.get(
            ambiguity.type,
            [
                "Yes — I'll clarify this now",
                "Use your best judgement here",
                "This part isn't important yet",
            ],
        )

        return ClarificationQuestion(
            id=f"Q{question_id}",
            category="scope",
            question=f"{ambiguity.suggestion} — which of these fits?",
            priority="medium",
            relates_to=f"ambiguity_{ambiguity.type}",
            options=options,
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
                # Multiple choice with custom answer allowed
                lines.append(f"\n{q.question}")
                for i, opt in enumerate(q.options, 1):
                    lines.append(f"  {i}. {opt}")
                # Always allow custom answers so users aren't boxed in
                lines.append("  (or type your own answer)")
            else:
                # Open-ended
                lines.append(f"\n- {q.question}")

        if result.is_final:
            lines.append("\n(This is the last round of questions)")

        return "\n".join(lines)
