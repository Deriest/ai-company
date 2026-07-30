"""Engineering Discovery Engine — Core Orchestrator.

Main entry point for the Discovery Engine.
Orchestrates the discovery pipeline and integrates with ConversationEngine.
"""

import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from storage.models import (
    DiscoverySession, EngineeringBrief as EngineeringBriefModel,
    Conversation
)
from discovery.states import DiscoveryState, is_terminal
from discovery.config import discovery_config
from discovery.intent import IntentClassifier, IntentResult
from discovery.requirements import RequirementExtractor, ExtractionResult
from discovery.ambiguity import AmbiguityDetector, AmbiguityReport
from discovery.readiness import ReadinessEvaluator, ReadinessResult
from discovery.clarifier import ClarificationEngine, ClarificationResult
from discovery.brief import BriefGenerator, EngineeringBriefData

logger = logging.getLogger("aic.discovery")


class DiscoveryResult:
    """Result of a discovery operation."""

    def __init__(
        self,
        state: str,
        is_ready: bool = False,
        brief: EngineeringBriefData | None = None,
        clarification: ClarificationResult | None = None,
        message: str = "",
        metadata: dict | None = None,
    ):
        self.state = state
        self.is_ready = is_ready
        self.brief = brief
        self.clarification = clarification
        self.message = message
        self.metadata = metadata or {}


class DiscoveryEngine:
    """Engineering Discovery Engine — orchestrates the discovery pipeline.

    Transforms natural language engineering requests into structured
    Engineering Briefs before any planning or execution begins.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def discover(
        self,
        conversation: Conversation,
        content: str,
        history: list | None = None,
    ) -> DiscoveryResult:
        """Run the discovery pipeline on a user message.

        Args:
            conversation: Current conversation
            content: User message content
            history: Conversation history

        Returns:
            DiscoveryResult with state, brief, or clarification
        """
        if not discovery_config.enabled:
            return DiscoveryResult(
                state="disabled",
                message="Discovery is disabled",
            )

        # Create discovery session
        discovery_session = DiscoverySession(
            conversation_id=conversation.id,
            user_id=conversation.user_id,
            status=DiscoveryState.NEW_REQUEST.value,
        )
        self.session.add(discovery_session)
        await self.session.flush()

        # Run discovery pipeline
        result = await self._run_pipeline(
            discovery_session, content, history
        )

        await self.session.commit()
        return result

    async def respond_to_clarification(
        self,
        session_id: str,
        response: str,
        history: list | None = None,
    ) -> DiscoveryResult:
        """Process user's clarification response.

        Args:
            session_id: Discovery session ID
            response: User's clarification response
            history: Conversation history

        Returns:
            DiscoveryResult with updated state
        """
        # Load discovery session
        result = await self.session.execute(
            select(DiscoverySession).where(DiscoverySession.id == session_id)
        )
        discovery_session = result.scalar_one_or_none()

        if not discovery_session:
            return DiscoveryResult(
                state="error",
                message="Discovery session not found",
            )

        if is_terminal(discovery_session.status):
            return DiscoveryResult(
                state=discovery_session.status,
                message=f"Session already in terminal state: {discovery_session.status}",
            )

        # Update state to USER_RESPONSE
        discovery_session.status = DiscoveryState.USER_RESPONSE.value
        discovery_session.questions_answered += 1

        # Merge response into context
        ctx = discovery_session.context or {}
        if "clarification_responses" not in ctx:
            ctx["clarification_responses"] = []
        ctx["clarification_responses"].append({
            "round": discovery_session.round_number,
            "response": response,
        })
        discovery_session.context = ctx

        # Re-run pipeline with updated context
        content = ctx.get("original_content", "")
        if not content:
            content = response  # Fallback

        # Combine original content with clarification response
        combined_content = f"{content}\n\nClarification: {response}"

        result = await self._run_pipeline(
            discovery_session, combined_content, history
        )

        await self.session.commit()
        return result

    async def get_session(self, session_id: str) -> DiscoverySession | None:
        """Get a discovery session by ID."""
        result = await self.session.execute(
            select(DiscoverySession).where(DiscoverySession.id == session_id)
        )
        return result.scalar_one_or_none()

    async def get_brief(self, session_id: str) -> EngineeringBriefModel | None:
        """Get the latest Engineering Brief for a session."""
        result = await self.session.execute(
            select(EngineeringBriefModel)
            .where(EngineeringBriefModel.discovery_session_id == session_id)
            .order_by(EngineeringBriefModel.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _run_pipeline(
        self,
        discovery_session: DiscoverySession,
        content: str,
        history: list | None = None,
    ) -> DiscoveryResult:
        """Run the discovery pipeline.

        Pipeline: Intent → Requirements → Ambiguity → Readiness → Brief/Clarification
        """
        # Step 1: Intent Classification
        intent = IntentClassifier.classify(content, history)

        # If not a task request, skip discovery
        if intent.base_intent != "task_request":
            discovery_session.status = DiscoveryState.ABORTED.value
            return DiscoveryResult(
                state=DiscoveryState.ABORTED.value,
                message=f"Not a task request (intent: {intent.base_intent})",
            )

        # Step 2: Requirement Extraction
        extraction = RequirementExtractor.extract(content, history, intent.domain)

        # Step 3: Ambiguity Detection
        ambiguity = AmbiguityDetector.detect(content, history)

        # Step 4: Readiness Evaluation
        readiness = ReadinessEvaluator.evaluate(
            extraction, ambiguity, intent.domain, content
        )

        # Step 5: Update session context
        ctx = discovery_session.context or {}
        ctx["original_content"] = content
        ctx["intent"] = {
            "base_intent": intent.base_intent,
            "domain": intent.domain,
            "confidence": intent.confidence,
        }
        ctx["extraction"] = {
            "functional_count": len(extraction.functional),
            "non_functional_count": len(extraction.non_functional),
            "constraints_count": len(extraction.constraints),
            "covered_fields": extraction.covered_fields,
            "missing_fields": extraction.missing_fields,
        }
        ctx["ambiguity"] = {
            "score": ambiguity.overall_score,
            "count": len(ambiguity.ambiguities),
            "types": [a.type for a in ambiguity.ambiguities],
        }
        ctx["readiness"] = {
            "is_ready": readiness.is_ready,
            "score": readiness.overall_score,
            "dimensions": readiness.dimensions,
        }
        discovery_session.context = ctx

        # Step 6: Branch based on readiness
        if readiness.is_ready:
            return await self._handle_ready(
                discovery_session, intent, extraction, readiness, content
            )
        else:
            return await self._handle_not_ready(
                discovery_session, intent, extraction, readiness, ambiguity, content
            )

    async def _handle_ready(
        self,
        discovery_session: DiscoverySession,
        intent: IntentResult,
        extraction: ExtractionResult,
        readiness: ReadinessResult,
        content: str,
    ) -> DiscoveryResult:
        """Handle case when request is Engineering Ready."""
        # Update state
        discovery_session.status = DiscoveryState.ENGINEERING_BRIEF_COMPLETE.value

        # Generate Engineering Brief
        brief_data = BriefGenerator.assemble(
            intent, extraction, readiness, content,
            discovery_session.round_number
        )

        # Validate Brief
        validation = BriefGenerator.validate(brief_data)
        if not validation.is_valid:
            logger.warning(f"Brief validation failed: {validation.errors}")
            # Still proceed — validation errors are warnings at this stage

        # Persist Brief
        brief_model = EngineeringBriefModel(
            discovery_session_id=discovery_session.id,
            version=brief_data.version,
            engineering_goal=brief_data.engineering_goal,
            user_intent=brief_data.user_intent,
            request_category=brief_data.request_category,
            scope=brief_data.scope,
            functional_requirements=brief_data.functional_requirements,
            non_functional_requirements=brief_data.non_functional_requirements,
            constraints=brief_data.constraints,
            assumptions=brief_data.assumptions,
            dependencies=brief_data.dependencies,
            risks=brief_data.risks,
            acceptance_criteria=brief_data.acceptance_criteria,
            readiness_status=brief_data.readiness_status,
            readiness_score=brief_data.readiness_score,
            readiness_dimensions=brief_data.readiness_dimensions,
            outstanding_unknowns=brief_data.outstanding_unknowns,
            discovery_metadata=brief_data.discovery_metadata,
            status="ready",
        )
        self.session.add(brief_model)
        await self.session.flush()

        # Build response message
        message = self._build_ready_message(brief_data, intent)

        return DiscoveryResult(
            state=DiscoveryState.ENGINEERING_BRIEF_COMPLETE.value,
            is_ready=True,
            brief=brief_data,
            message=message,
            metadata={
                "session_id": discovery_session.id,
                "brief_id": brief_data.id,
                "domain": intent.domain,
                "readiness_score": readiness.overall_score,
            },
        )

    async def _handle_not_ready(
        self,
        discovery_session: DiscoverySession,
        intent: IntentResult,
        extraction: ExtractionResult,
        readiness: ReadinessResult,
        ambiguity: AmbiguityReport,
        content: str,
    ) -> DiscoveryResult:
        """Handle case when request is NOT Engineering Ready."""
        # Update state to CLARIFICATION
        discovery_session.status = DiscoveryState.CLARIFICATION.value
        discovery_session.round_number += 1

        # Generate clarification questions
        clarification = ClarificationEngine.generate_questions(
            readiness, extraction, ambiguity, intent.domain,
            discovery_session.round_number - 1
        )

        # Update session
        discovery_session.questions_asked += len(clarification.questions)

        # If final round or no questions, force-complete
        if clarification.is_final or not clarification.questions:
            return await self._force_complete(
                discovery_session, intent, extraction, readiness, content
            )

        # Format questions for user
        question_text = ClarificationEngine.format_questions_for_user(clarification)

        return DiscoveryResult(
            state=DiscoveryState.CLARIFICATION.value,
            is_ready=False,
            clarification=clarification,
            message=question_text,
            metadata={
                "session_id": discovery_session.id,
                "round": discovery_session.round_number,
                "questions_count": len(clarification.questions),
                "readiness_score": readiness.overall_score,
            },
        )

    async def _force_complete(
        self,
        discovery_session: DiscoverySession,
        intent: IntentResult,
        extraction: ExtractionResult,
        readiness: ReadinessResult,
        content: str,
    ) -> DiscoveryResult:
        """Force-complete discovery after max rounds.

        Generates Brief with outstanding_unknowns populated.
        """
        discovery_session.status = DiscoveryState.ENGINEERING_BRIEF_COMPLETE.value

        # Generate Brief with outstanding unknowns
        brief_data = BriefGenerator.assemble(
            intent, extraction, readiness, content,
            discovery_session.round_number
        )

        # Mark as force-completed
        brief_data.status = "ready"
        brief_data.discovery_metadata["force_completed"] = True
        brief_data.discovery_metadata["reason"] = "Max clarification rounds reached"

        # Persist Brief
        brief_model = EngineeringBriefModel(
            discovery_session_id=discovery_session.id,
            version=brief_data.version,
            engineering_goal=brief_data.engineering_goal,
            user_intent=brief_data.user_intent,
            request_category=brief_data.request_category,
            scope=brief_data.scope,
            functional_requirements=brief_data.functional_requirements,
            non_functional_requirements=brief_data.non_functional_requirements,
            constraints=brief_data.constraints,
            assumptions=brief_data.assumptions,
            dependencies=brief_data.dependencies,
            risks=brief_data.risks,
            acceptance_criteria=brief_data.acceptance_criteria,
            readiness_status="ready",
            readiness_score=readiness.overall_score,
            readiness_dimensions=readiness.dimensions,
            outstanding_unknowns=brief_data.outstanding_unknowns,
            discovery_metadata=brief_data.discovery_metadata,
            status="ready",
        )
        self.session.add(brief_model)
        await self.session.flush()

        unknowns_count = len(brief_data.outstanding_unknowns)
        message = (
            f"Discovery complete after {discovery_session.round_number} rounds.\n\n"
            f"Engineering Brief generated with {unknowns_count} outstanding unknown(s).\n"
            f"The Planning Engine will handle these during implementation.\n\n"
            f"Reply **yes / go ahead** to start planning."
        )

        return DiscoveryResult(
            state=DiscoveryState.ENGINEERING_BRIEF_COMPLETE.value,
            is_ready=True,
            brief=brief_data,
            message=message,
            metadata={
                "session_id": discovery_session.id,
                "brief_id": brief_data.id,
                "force_completed": True,
                "outstanding_unknowns": unknowns_count,
            },
        )

    def _build_ready_message(
        self,
        brief: EngineeringBriefData,
        intent: IntentResult,
    ) -> str:
        """Build user-facing message for ready state."""
        lines = [
            "**Engineering Discovery Complete**\n",
            f"- Domain: {intent.domain.title()}",
            f"- Goal: {brief.engineering_goal[:100]}",
            f"- Readiness: {brief.readiness_score:.0%}",
        ]

        if brief.functional_requirements:
            lines.append(f"- Requirements: {len(brief.functional_requirements)}")

        if brief.outstanding_unknowns:
            lines.append(f"- Outstanding unknowns: {len(brief.outstanding_unknowns)}")

        lines.append("\nReply **yes / go ahead** to start planning.")

        return "\n".join(lines)
