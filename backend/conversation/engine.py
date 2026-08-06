"""AIC Platform — Conversation Engine.

AI Operator behavior: the assistant is a capable project partner, not just a
task-creation bot. It:
- Has natural conversations
- Asks clarifying questions before creating tasks
- Maintains context across the conversation
- Handles status queries, approvals, and general Q&A
- Only dispatches to the task system when the user confirms

The engine does NOT execute tasks — that's the dispatcher's job.
"""
from datetime import datetime, timezone
import re
import json
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from storage.models import (
    Conversation, Message, Task, Project, TaskType, TaskStatus,
)
from backend.services.content_utils import content_to_text, truncate_content
from policy.engine import policy, Decision

logger = logging.getLogger("aic.conversation")

# BUG-07 FIX: Module-level set to hold background task references.
# The ConversationEngine instance is short-lived (created per request inside
# an `async with` block). If background tasks were stored on the instance,
# they'd be garbage-collected when the engine goes out of scope — causing
# asyncio.create_task coroutines to silently vanish. A module-level set
# keeps strong references alive for the process lifetime.
_global_background_tasks: set = set()


class LLMUnavailableError(Exception):
    """No LLM provider is configured or available."""
    pass


class LLMInferenceError(Exception):
    """LLM request failed (network, auth, timeout, etc)."""
    pass


# ── Intent Types ───────────────────────────────────────

INTENT_QUESTION = "question"
INTENT_TASK_REQUEST = "task_request"
INTENT_TASK_CONFIRM = "task_confirm"
INTENT_APPROVAL = "approval"
INTENT_STATUS = "status"
INTENT_CHAT = "chat"


# ── Task type detection patterns (fallback) ────────────

TASK_PATTERNS: list[tuple[str, str, re.Pattern]] = [
    # Bug-hunt (read-only audit) MUST be checked before the generic bugfix
    # pattern since it also contains the word "bug".
    (TaskType.BUGHUNT.value, "qa",
     re.compile(r"\b(cari\s+bug|bug\s+hunt|find\s+bugs?|audit\s+(kode|code|bug)|scan\s+(for\s+)?bugs?|carikan\s+bug|cari\s+masalah|bug\s+audit)\b", re.I)),
    (TaskType.BUGFIX.value, "backend",
     re.compile(r"\b(fix|bug|error|broken|crash|fail|issue|defect)\b", re.I)),
    (TaskType.BUGFIX.value, "frontend",
     re.compile(r"\b(ui\s*bug|css\s*fix|style\s*fix|layout\s*issue|rendering|display\s*bug)\b", re.I)),
    (TaskType.TEST.value, "qa",
     re.compile(r"\b(tests?|specs?|coverage|unit tests?|integration tests?|e2e)\b", re.I)),
    (TaskType.REFACTOR.value, "backend",
     re.compile(r"\b(refactor|clean|restructure|simplify|optimize)\b", re.I)),
    (TaskType.DOCS.value, "documentation",
     re.compile(r"\b(doc|documentation|readme|guide|tutorial|manual)\b", re.I)),
    (TaskType.INFRA.value, "devops",
     re.compile(r"\b(deploy|docker|ci.?cd|pipeline|infrastructure|server|host)\b", re.I)),
    (TaskType.RESEARCH.value, "research",
     re.compile(r"\b(research|investigate|analyze|explore|study)\b", re.I)),
    (TaskType.FEATURE.value, "frontend",
     re.compile(r"\b(ui|css|tailwind|react|vue|angular|component|layout|dashboard|page|form|button|modal|responsive|style|design)\b", re.I)),
    (TaskType.FEATURE.value, "database",
     re.compile(r"\b(database|sql|migration|schema|query|sqlite|postgres|mysql|orm)\b", re.I)),
    (TaskType.FEATURE.value, "backend",
     re.compile(r"\b(api|endpoint|route|auth|middleware|validation|handler|service|controller)\b", re.I)),
    (TaskType.FEATURE.value, "security",
     re.compile(r"\b(security|encrypt|hash|token|rbac|permission|sanitize|inject)\b", re.I)),
    (TaskType.FEATURE.value, "pm",
     re.compile(r"\b(plan|roadmap|strategy|architect|overview|review task)\b", re.I)),
    (TaskType.FEATURE.value, "coding",
     re.compile(r"\b(build|create|add|implement|develop|make)\b", re.I)),
]


# ── LLM System Prompts ─────────────────────────────────

SYSTEM_PROMPT = """You are Hermes, the primary AI partner inside AIC ADE (Agentic Development Environment).

You are a capable engineering partner — not a task-creation bot and not a generic chatbot.

You can:
- Have natural conversations about software, architecture, and product
- Help plan, design, and reason before any implementation
- Create engineering tasks only when the user clearly wants work done
- Answer technical questions
- Check status of ongoing work
- Handle approvals and reviews

Personality:
- Conversational, precise, calm
- Ask clarifying questions when ambiguous
- Concise but thorough — no padding
- Suggest improvements and flag risks
- When you don't know, say so

WRITING STANDARD (anti-slop — STRICT):
- NEVER use: delve, crucial, pivotal, comprehensive, seamless, groundbreaking, "It's important to note", "I'd be happy to", "Let's dive in", "In conclusion", "at the end of the day", "game-changer", "In today's fast-paced world".
- NEVER use these AI greetings/responses: "How can I help you today?", "Great question!", "I'd be happy to help", "Let me know if you need anything else", "Feel free to ask", "Don't hesitate to reach out".
- NEVER open with generic AI greetings: "How can I help you today?", "Hi! How can I", "What can I do for you?", "Is there anything else I can help with?" — respond directly and specifically instead.
- NEVER: em-dash overuse, forced rule-of-three, synonym swapping, "-ing" openers, Title Case headings, emoji in headings.
- AVOID: "not only... but also", rhetorical questions immediately answered, mic-drop closings, ad-copy language.
- MUST: vary sentence length, use specifics (numbers/names/context), state opinions clearly, prefer simple words ("is" not "serves as"), active voice.
- FOR GREETINGS: respond naturally like a human colleague. "Halo" → "Halo!" or "Hai!" — not a formal offer of help. Keep it brief and specific. Never offer generic help.
- Sound like a knowledgeable human, not a polite LLM.

Conversation-first rules:
- Question, brainstorm, and discussion messages should NOT create tasks
- Only create tasks for clear engineering requests when requirements are enough
- Prefer proposing a plan and waiting for confirmation unless the user says "build now", "create the task", or similar force language
- If the request is vague, ask 1–3 clarifying questions

Task tag (when ready and confirmed):
TASK_CONFIRM: <title> | <type> | <worker_type>
Types: feature, bugfix, refactor, docs, test, infra, research
Workers: pm, architect, research, designer, backend, frontend, qa, coding, database, security, documentation, deployment, devops, performance, debugger

Keep responses focused. You're a working partner inside a professional desktop ADE."""

INTENT_SYSTEM_PROMPT = """Classify the user message into exactly ONE intent:
- task_request: User wants work done (build, create, fix, deploy, test, etc.)
- task_confirm: User is confirming/approving a previously discussed task
- status: User wants progress/status update
- approval: User wants to approve or reject something
- question: User is asking a question
- chat: General conversation, greetings, or unclear

Respond with ONLY the intent name, nothing else."""


def _llm_meta(result: dict, provider: str = "") -> dict:
    """Extract LLM metadata from provider.chat() result."""
    usage = result.get("usage", {})
    if not provider:
        from llm.provider import provider_manager as _pm
        provider = _pm._active or ""
    return {
        "model": result.get("model", ""),
        "provider": provider,
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
    }


class ConversationEngine:
    """AI Operator — manages conversations, clarifies intent, creates tasks when ready.

    Uses LLM when a provider is configured, falls back to regex.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self._llm_info: dict = {}  # accumulated from LLM calls
        self._background_tasks: set = set()  # hold references to prevent GC

    async def process_message(
        self,
        conversation: Conversation,
        content: str,
    ) -> Message:
        """Process a user message and generate a response."""
        # Save user message
        user_msg = Message(
            conversation_id=conversation.id,
            role="user",
            content=content,
            intent=None,
        )
        self.session.add(user_msg)
        await self.session.flush()

        # Get conversation history for context
        history = await self._get_conversation_history(conversation, limit=10)

        # Detect intent — LLM or regex
        intent = await self._detect_intent_llm(content, history)

        # Generate response based on intent
        response_content, metadata = await self._handle_intent(
            conversation, content, intent, history
        )

        # Merge LLM call metadata
        metadata.update(self._llm_info)
        # Inject timestamp
        metadata["timestamp"] = datetime.now(timezone.utc).isoformat()

        # Save assistant response
        assistant_msg = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=response_content,
            intent=intent,
            meta=metadata,
        )
        self.session.add(assistant_msg)

        # Update conversation context
        conv_context = conversation.context or {}
        conv_context["last_intent"] = intent
        conv_context["last_message"] = truncate_content(content, 200)
        conv_context["message_count"] = conv_context.get("message_count", 0) + 1
        conversation.context = conv_context

        # Auto-title on first message
        if conv_context["message_count"] == 1 and conversation.title == "New Conversation":
            conversation.title = self._extract_title(content) or "Chat"

        await self.session.flush()

        # Record audit trail + events (fire-and-forget)
        try:
            await self._record_audit(intent, content, metadata, conversation)
        except Exception:
            pass  # non-critical

        return assistant_msg

    async def _detect_intent_llm(self, content: str, history: list) -> str:
        """Detect intent — regex-first (skip LLM for intent classification).

        Reasoning models dump thinking into content, making LLM intent detection unreliable.
        Regex is fast, deterministic, and works for all models.
        """
        return self._detect_intent(content)

    def _detect_intent(self, content: str) -> str:
        """Delegate to shared intent patterns — single source of truth."""
        from shared.intent_patterns import classify_intent
        return classify_intent(content)

    async def _handle_intent(
        self,
        conversation: Conversation,
        content: str,
        intent: str,
        history: list,
    ) -> tuple[str, dict]:
        """Handle detected intent and return (response_text, metadata)."""
        if intent == INTENT_TASK_REQUEST:
            return await self._handle_task_request(conversation, content, history)
        elif intent == INTENT_TASK_CONFIRM:
            return await self._handle_task_confirm(conversation, content, history)
        elif intent == INTENT_STATUS:
            return await self._handle_status(conversation)
        elif intent == INTENT_APPROVAL:
            return await self._handle_approval(conversation, content)
        elif intent == INTENT_QUESTION:
            return await self._handle_question_llm(conversation, content, history)
        else:
            return await self._handle_chat_llm(conversation, content, history)

    def _evaluate_intake_completeness(self, text_corpus: str) -> tuple[bool, list[str]]:
        """Evaluate requirement completeness against mandatory intake checklist.

        Returns (is_complete, missing_fields). Delegates to the shared helper
        (backend/shared/intake.py) — single source of truth used by the
        /chat/execute clarify gate as well.
        """
        from shared.intake import evaluate_intake_completeness
        return evaluate_intake_completeness(text_corpus)

    def _user_forces_task_creation(self, text: str) -> bool:
        """True when user explicitly wants engineering to start now."""
        from shared.intake import user_forces_task_creation
        return user_forces_task_creation(text)

    async def _handle_task_request(
        self,
        conversation: Conversation,
        content: str,
        history: list,
    ) -> tuple[str, dict]:
        """Handle engineering requests with conversation-first discipline.

        Flow:
        1. Accumulate conversation corpus.
        2. If intake incomplete → discovery questions (no task).
        3. If complete but not forced → propose plan + store pending_task (await confirm).
        4. If complete and forced / already confirmed → create task.
        """
        # Aggregate conversation text corpus
        corpus_parts = [content_to_text(content)]
        for m in history:
            if isinstance(m, dict) and m.get("content"):
                corpus_parts.append(content_to_text(m["content"]))
            elif hasattr(m, "content") and m.content:
                corpus_parts.append(content_to_text(m.content))
        full_corpus = " ".join(corpus_parts)

        is_complete, missing_fields = self._evaluate_intake_completeness(full_corpus)

        # Discovery Loop: incomplete requirements → conversational clarification
        if not is_complete:
            return await self._handle_chat_llm(conversation, content, history)

        # Classify the task (LLM JSON or regex fallback)
        task_type, worker, title, approval_required = await self._classify_task_llm(content)
        if not title:
            title = self._extract_title(content)

        force = self._user_forces_task_creation(full_corpus)

        # Conversation-first: propose + wait for confirm unless user forces execution
        if not force:
            conv_ctx = conversation.context or {}
            conv_ctx["pending_task"] = {
                "title": title,
                "description": content,
                "type": task_type,
                "worker": worker,
            }
            conversation.context = conv_ctx

            worker_name = {
                "pm": "PM", "architect": "Architect", "research": "Researcher",
                "designer": "Designer", "backend": "Backend Engineer",
                "frontend": "Frontend Engineer", "qa": "QA Engineer",
                "coding": "Full-Stack Developer", "database": "Database Engineer",
            }.get(worker, worker.title())

            missing_note = ""
            if missing_fields:
                missing_note = f"\n(Optional gaps still open: {', '.join(missing_fields[:4])})"

            return (
                f"I can start engineering on **{title}**.\n\n"
                f"- Type: `{task_type}`\n"
                f"- Lead worker: **{worker_name}**\n"
                f"- Approval: {'likely required' if approval_required else 'not required for this class of work'}"
                f"{missing_note}\n\n"
                f"Reply **yes / go ahead / create the task** to start, or tell me what to change."
            ), {
                "pending_task": True,
                "proposed_title": title,
                "task_type": task_type,
                "worker": worker,
            }

        # Forced execution path
        task, task_code = await self._create_task(
            conversation, content, title, task_type, worker
        )
        if not task:
            return "Unable to create task — no project linked.", {}

        metadata = {
            "task_id": task.id,
            "task_code": task_code,
            "task_type": task_type,
            "worker": worker,
        }

        # Launch engineering pipeline in background
        await self._launch_pipeline(task)

        worker_name = {
            "pm": "PM", "architect": "Architect", "research": "Researcher",
            "designer": "Designer", "backend": "Backend Engineer",
            "frontend": "Frontend Engineer", "qa": "QA Engineer",
            "coding": "Full-Stack Developer", "database": "Database Engineer",
        }.get(worker, worker.title())

        return (
            f"Task **{task_code}** created: \"{title}\"\n\n"
            f"Assigned to **{worker_name}**. Pipeline: "
            f"investigate → planning → implementation → verification → closeout. "
            f"I'll keep you updated as work progresses."
        ), metadata

    async def _handle_task_confirm(
        self,
        conversation: Conversation,
        content: str,
        history: list,
    ) -> tuple[str, dict]:
        """Handle user confirmation of a previously discussed task.

        Looks at the conversation context for a pending task proposal.
        """
        conv_ctx = conversation.context or {}
        pending = conv_ctx.get("pending_task")

        if pending:
            # User is confirming a pending task from earlier in conversation
            task, task_code = await self._create_task(
                conversation,
                pending.get("description", content),
                pending.get("title", self._extract_title(content)),
                pending.get("type", "feature"),
                pending.get("worker", "coding"),
            )
            if task:
                # Clear pending
                conv_ctx.pop("pending_task", None)
                conversation.context = conv_ctx
                # Launch engineering pipeline in background
                await self._launch_pipeline(task)
                return (
                    f"Done! Created {task_code}: {task.title}\n"
                    f"Type: {task.type} | Worker: {task.worker_type}\n"
                    f"Status: Engineering pipeline started"
                ), {"task_id": task.id, "task_code": task_code}

        # No pending task — treat as a new task request
        return await self._handle_task_request(conversation, content, history)

    async def _launch_pipeline(self, task: Task) -> None:
        """Launch the engineering pipeline as a background task.

        The MasterOrchestrator chains: Discovery → Planning → TaskGraph → Dispatch.
        Events are published to EventBus + WebSocket for real-time frontend updates.
        """
        import asyncio
        from backend.services.master_orchestrator import run_engineering_pipeline

        # BUG-07 FIX: Commit the task BEFORE scheduling the background coroutine.
        # The background task opens an independent session that must be able to
        # see the task row. Without this commit, the row is only flushed (visible
        # inside the current transaction) and the background session can't find it.
        try:
            await self.session.commit()
        except Exception as e:
            logger.warning(f"Pre-pipeline commit failed: {e}")

        task_id = task.id  # capture for closure

        async def _run():
            try:
                from storage.database import async_session as _async_session
                logger.info(f"Pipeline background started for task {task_id}")
                async with _async_session() as bg_session:
                    # Re-fetch the task in the background session
                    from sqlalchemy import select as _select
                    res = await bg_session.execute(
                        _select(Task).where(Task.id == task_id)
                    )
                    bg_task = res.scalar_one_or_none()
                    if bg_task:
                        logger.info(f"Pipeline background: task {task_id} found, starting pipeline...")
                        result = await run_engineering_pipeline(bg_session, bg_task)
                        await bg_session.commit()
                        # Append a user-facing summary message to the conversation
                        try:
                            conv_id = getattr(task, 'context', {}).get('conversation_id')
                            if conv_id:
                                from storage.models import Conversation
                                conv_res = await bg_session.execute(
                                    select(Conversation).where(Conversation.id == conv_id)
                                )
                                conv = conv_res.scalar_one_or_none()
                                if conv:
                                    # Build dispatcher's report to user
                                    if result.success:
                                        msg_lines = [
                                            "**Dispatcher Report — Pipeline Complete**",
                                            f"- Outcome: success",
                                        ]
                                        # List artifacts from PRD and any deliverables
                                        if result.brief_id or result.graph_id:
                                            msg_lines.append("- Artifacts produced: docs/PRD.md + per-task deliverables")
                                        msg_lines.append("\nNext step: review docs/PRD.md and generated files.")
                                    else:
                                        error_stage = result.error.split(":")[0] if result.error else "unknown"
                                        msg_lines = [
                                            "**Dispatcher Report — Pipeline Failed**",
                                            f"- Outcome: failed at stage `{error_stage}`",
                                            f"- Error: {result.error[:200]}",
                                        ]
                                    summary_msg = "\n".join(msg_lines)
                                    from storage.models import Message
                                    assistant_msg = Message(
                                        conversation_id=conv_id,
                                        role="assistant",
                                        content=summary_msg,
                                        intent="dispatcher_report",
                                        meta={"pipeline": {"stage": result.stage}},
                                    )
                                    bg_session.add(assistant_msg)
                                    await bg_session.commit()  # Commit message so it survives session rollback
                                    logger.info(f"Pipeline summary message written to conv {conv_id}")
                        except Exception as e:
                            # Non-critical: don't crash pipeline reporting
                            logger.warning(f"Failed to append pipeline summary message: {e}")
                        logger.info(
                            f"Pipeline finished for task {task_id}: "
                            f"success={result.success} stage={result.stage}"
                        )
                    else:
                        logger.error(f"Pipeline background: task {task_id} NOT FOUND in DB")
            except Exception as e:
                logger.error(f"Pipeline background failed for task {task_id}: {e}", exc_info=True)

        # Fire-and-forget: schedule in background, don't block the response
        # BUG-07 FIX: Store in module-level set to prevent GC when engine is destroyed
        task_ref = asyncio.create_task(_run())
        _global_background_tasks.add(task_ref)
        task_ref.add_done_callback(_global_background_tasks.discard)

    async def _create_task(
        self,
        conversation: Conversation,
        description: str,
        title: str,
        task_type: str,
        worker: str,
    ) -> tuple[Task | None, str]:
        """Create a task linked to the conversation's project."""
        project_id = await self._get_or_create_project(conversation)
        if not project_id:
            return None, ""

        from workflow.triage import perform_smart_triage, ExecutionLevel
        triage_res = perform_smart_triage(f"{title} {description}", task_type=task_type, worker_hint=worker)

        # M6 FIX: triage_res.level is an ExecutionLevel enum — comparing it to a
        # plain string was always True, so QUICK tasks incorrectly required
        # approval. Compare against the enum member.
        approval_required = task_type not in ("test", "docs", "bughunt") and triage_res.level != ExecutionLevel.QUICK
        task = Task(
            project_id=project_id,
            title=title,
            description=description,
            type=task_type,
            status=TaskStatus.CREATED.value,
            worker_type=worker,
            approval_required=approval_required,
            progress=0,
            context={
                "source": "chat",
                "conversation_id": conversation.id,
                "triage": triage_res.to_dict(),
                "execution_level": triage_res.level.value,
                "phase_semantics": {},
            },
        )
        self.session.add(task)
        await self.session.flush()
        task_code = f"TASK-{task.id[:8].upper()}"

        return task, task_code

    async def _get_or_create_project(self, conversation: Conversation) -> str | None:
        """Get project ID from conversation context, or find/create a default."""
        project_id = conversation.context.get("project_id") if conversation.context else None
        if project_id:
            return project_id

        user_id = conversation.user_id
        if user_id:
            result = await self.session.execute(
                select(Project).where(Project.owner_id == user_id).limit(1)
            )
            project = result.scalar_one_or_none()
            if project:
                project_id = project.id
            else:
                project = Project(
                    name="Chat Project",
                    slug="chat-project",
                    description="Auto-created from chat",
                    owner_id=user_id,
                )
                self.session.add(project)
                await self.session.flush()
                project_id = project.id
        else:
            # Local-first mode: no user_id, create/find a default project
            result = await self.session.execute(
                select(Project).where(Project.slug == "default-chat-project").limit(1)
            )
            project = result.scalar_one_or_none()
            if project:
                project_id = project.id
            else:
                project = Project(
                    name="Default Chat Project",
                    slug="default-chat-project",
                    description="Auto-created for local-first mode",
                    owner_id=None,
                )
                self.session.add(project)
                await self.session.flush()
                project_id = project.id

        if conversation.context is None:
            conversation.context = {}
        conversation.context["project_id"] = project_id

        return project_id

    async def _classify_task_llm(self, content: str) -> tuple[str, str, str, bool]:
        """Classify task — regex-first for deterministic worker routing.

        LLM task classification is unreliable with reasoning models (thinking dumps).
        Regex patterns are fast, deterministic, and correctly route to workers.
        """
        task_type, worker = self._classify_task(content)
        title = self._extract_title(content)
        approval_required = task_type not in ("test", "docs", "bughunt")
        return task_type, worker, title, approval_required

    async def _handle_status(self, conversation: Conversation) -> tuple[str, dict]:
        """Get project/task status."""
        project_id = (conversation.context or {}).get("project_id")

        if not project_id:
            return "No active project in this conversation. Create a task first to start tracking.", {}

        result = await self.session.execute(
            select(Task).where(
                Task.project_id == project_id,
                Task.status.in_([
                    TaskStatus.CREATED.value,
                    TaskStatus.INVESTIGATE.value,
                    TaskStatus.PLANNING.value,
                    TaskStatus.IMPLEMENTATION.value,
                    TaskStatus.VERIFICATION.value,
                    TaskStatus.CLOSEOUT.value,
                ]),
            )
        )
        tasks = result.scalars().all()

        if not tasks:
            return "No active tasks in this project.", {"active_count": 0}

        lines = [f"**Active Tasks: {len(tasks)}**\n"]
        for t in tasks:
            code = f"TASK-{t.id[:8].upper()}"
            bar = "█" * (t.progress // 10) + "░" * (10 - t.progress // 10)
            lines.append(f"- **{code}** — {t.title}")
            lines.append(f"  Status: {t.status} | [{bar}] {t.progress}%")
            if t.assigned_worker_id:
                lines.append(f"  Worker: {t.worker_type or 'assigned'}")
            lines.append("")

        return "\n".join(lines), {"active_count": len(tasks)}

    async def _handle_approval(
        self,
        conversation: Conversation,
        content: str,
    ) -> tuple[str, dict]:
        """Handle approval/rejection."""
        lower = content.lower()
        is_approve = "approve" in lower or "accept" in lower

        return (
            f"{'Approval' if is_approve else 'Rejection'} recorded. "
            f"Use the Approval Center to manage pending approvals.",
            {"action": "approve" if is_approve else "reject"},
        )

    async def _handle_question_llm(
        self,
        conversation: Conversation,
        content: str,
        history: list,
    ) -> tuple[str, dict]:
        """Handle questions using LLM with full conversation context."""
        from llm.provider import provider_manager, ModelTier

        # P1 #6: get_active() may return a provider with an empty api_key →
        # "Illegal header value b'Bearer '". Use get_active_with_key().
        provider = provider_manager.get_active_with_key()
        if not provider:
            raise LLMUnavailableError("No AI provider configured. Add a provider in Settings to start chatting.")

        context_str = self._build_context_string(conversation, history)

        try:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT + "\n\n" + context_str},
                *[{"role": m.role, "content": m.content} for m in history[-5:]],
                {"role": "user", "content": content},
            ]
            
            # QA-249-R5 FIX: Use proper context policy, not hardcoded 1500
            from backend.services.context_builder import get_context_policy
            policy = get_context_policy("crafter")
            max_tokens = policy.max_tokens if policy.max_tokens > 0 else 60000
            
            messages = await self._apply_token_budget(messages, max_tokens=max_tokens)
            
            # QA-249-R6: History already flattened by provider.chat() internally
            result = await provider.chat(
                messages=messages,
                tier=ModelTier.CRAFTER,
                temperature=0.5,
                max_tokens=1500,
                purpose="conversation",
            )
            content = result["content"]

            # FITUR 2 Lapis 3: Taste checker — flag AI-isms + REWRITE PASS if high findings
            try:
                from backend.services.taste_checker import has_ai_slop, scan_summary, REWRITE_PROMPT
                if has_ai_slop(content, threshold=1):
                    taste_meta = scan_summary(content)
                    logger.info(f"Chat taste checker: {taste_meta['total_findings']} findings (high={taste_meta['high']})")
                    self._llm_info["taste_findings"] = taste_meta

                    # REWRITE PASS: If high findings, use LLM to rewrite
                    if taste_meta["high"] > 0:
                        try:
                            rewrite_result = await provider.chat(
                                messages=[
                                    {"role": "system", "content": "You are a text editor. Rewrite the given text to remove AI patterns. Keep the meaning and tone. Do NOT add explanations, just output the rewritten text."},
                                    {"role": "user", "content": REWRITE_PROMPT + content},
                                ],
                                tier=ModelTier.SPRINTER,
                                temperature=0.3,
                                max_tokens=len(content) + 200,
                                purpose="taste_rewrite",
                            )
                            rewritten = rewrite_result.get("content", "").strip()
                            # Only use rewrite if it's not empty and doesn't introduce new issues
                            if rewritten and len(rewritten) > 10:
                                # Verify the rewrite is cleaner
                                from backend.services.taste_checker import has_ai_slop as check_again
                                if not check_again(rewritten, threshold=1):
                                    logger.info("Taste rewrite successful — cleaner output")
                                    content = rewritten
                                else:
                                    logger.info("Taste rewrite still has AI-isms — using original")
                        except Exception as rewrite_err:
                            logger.debug(f"Taste rewrite failed (non-critical): {rewrite_err}")
            except Exception as taste_err:
                logger.debug(f"Taste checker exception (non-critical): {taste_err}")

            return content, _llm_meta(result)
        except Exception as e:
            logger.warning(f"LLM question handling failed: {e}")
            raise LLMInferenceError(f"LLM request failed: {e}") from e

    def _handle_question_fallback(self, content: str) -> tuple[str, dict]:
        """Regex fallback for questions — only used when no LLM is available."""
        raise LLMUnavailableError(
            "No AI provider configured. Please add a provider in Settings → AI Providers to enable Hermes."
        )

    async def _handle_chat_llm(
        self,
        conversation: Conversation,
        content: str,
        history: list,
    ) -> tuple[str, dict]:
        """Handle general chat using LLM with conversation context and memory."""
        from llm.provider import provider_manager, ModelTier

        # P1 #6: use get_active_with_key() so a provider with an empty api_key
        # is never selected (otherwise "Illegal header value b'Bearer '").
        provider = provider_manager.get_active_with_key()
        if not provider:
            raise LLMUnavailableError("No AI provider configured. Add a provider in Settings to start chatting.")

        # Retrieve conversation memories
        from backend.services.memory_service import memory_service
        memories = await memory_service.retrieve(
            self.session,
            scope="conversation",
            scope_id=str(conversation.id),
            min_importance=0.3,
            limit=10
        )
        
        # Retrieve relevant documents via RAG
        from backend.services.rag_service import rag_service
        rag_context = await rag_service.build_context(
            self.session,
            query=content,
            top_k=3,
            max_tokens=1500
        )
        
        # Build context with memories and RAG
        context_str = self._build_context_string(conversation, history)
        
        if memories:
            memory_lines = [f"- {m.key}: {m.value.get('content', m.value) if isinstance(m.value, dict) else m.value}" 
                          for m in memories]
            memory_context = "\n\nRelevant memories:\n" + "\n".join(memory_lines)
            context_str += memory_context
        
        if rag_context and rag_context.get("chunksUsed", 0) > 0:
            rag_text = f"\n\nRelevant knowledge from documents:\n{rag_context['context']}"
            if rag_context.get("citations"):
                citations_text = ", ".join([f"[{c['index']}] {c['documentTitle']}" for c in rag_context["citations"]])
                rag_text += f"\n\nSources: {citations_text}"
            context_str += rag_text

        try:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT + "\n\n" + context_str},
                *[{"role": m.role, "content": m.content} for m in history[-5:]],
                {"role": "user", "content": content},
            ]
            
            # QA-249-R5 FIX: Use proper context policy, not hardcoded 1500
            from backend.services.context_builder import get_context_policy
            policy = get_context_policy("crafter")
            max_tokens = policy.max_tokens if policy.max_tokens > 0 else 60000
            
            messages = await self._apply_token_budget(messages, max_tokens=max_tokens)
            
            # QA-249-R6: History already flattened by provider.chat() internally
            result = await provider.chat(
                messages=messages,
                tier=ModelTier.CRAFTER,
                temperature=0.7,
                max_tokens=1500,
                purpose="conversation",
            )
            content = result["content"]

            # FITUR 2 Lapis 3: Taste checker — flag AI-isms + REWRITE PASS if high findings
            try:
                from backend.services.taste_checker import has_ai_slop, scan_summary, REWRITE_PROMPT
                if has_ai_slop(content, threshold=1):
                    taste_meta = scan_summary(content)
                    logger.info(f"Chat taste checker: {taste_meta['total_findings']} findings (high={taste_meta['high']})")
                    self._llm_info["taste_findings"] = taste_meta

                    # REWRITE PASS: If high findings, use LLM to rewrite
                    if taste_meta["high"] > 0:
                        try:
                            rewrite_result = await provider.chat(
                                messages=[
                                    {"role": "system", "content": "You are a text editor. Rewrite the given text to remove AI patterns. Keep the meaning and tone. Do NOT add explanations, just output the rewritten text."},
                                    {"role": "user", "content": REWRITE_PROMPT + content},
                                ],
                                tier=ModelTier.SPRINTER,
                                temperature=0.3,
                                max_tokens=len(content) + 200,
                                purpose="taste_rewrite",
                            )
                            rewritten = rewrite_result.get("content", "").strip()
                            # Only use rewrite if it's not empty and doesn't introduce new issues
                            if rewritten and len(rewritten) > 10:
                                # Verify the rewrite is cleaner
                                from backend.services.taste_checker import has_ai_slop as check_again
                                if not check_again(rewritten, threshold=1):
                                    logger.info("Taste rewrite successful — cleaner output")
                                    content = rewritten
                                else:
                                    logger.info("Taste rewrite still has AI-isms — using original")
                        except Exception as rewrite_err:
                            logger.debug(f"Taste rewrite failed (non-critical): {rewrite_err}")
            except Exception as taste_err:
                logger.debug(f"Taste checker exception (non-critical): {taste_err}")

            return content, _llm_meta(result)
        except Exception as e:
            logger.warning(f"LLM chat failed: {e}")
            raise LLMInferenceError(f"LLM request failed: {e}") from e

    async def _get_conversation_history(self, conversation: Conversation, limit: int = 10) -> list:
        """Get recent messages for context."""
        result = await self.session.execute(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        messages = list(reversed(result.scalars().all()))
        return messages

    def _build_context_string(self, conversation: Conversation, history: list) -> str:
        """Build context string for LLM prompts."""
        parts = []
        ctx = conversation.context or {}
        if ctx.get("project_id"):
            parts.append(f"Project ID: {ctx['project_id']}")
        if ctx.get("last_intent"):
            parts.append(f"Last intent: {ctx['last_intent']}")
        if ctx.get("pending_task"):
            p = ctx["pending_task"]
            parts.append(f"Pending task proposal: {p.get('title', 'unknown')} ({p.get('type', '?')})")
        if history:
            parts.append(f"Conversation has {len(history)} messages")
        return "\n".join(parts) if parts else "No prior context."
    
    async def _apply_token_budget(self, messages: list, max_tokens: int = 2000) -> list:
        """Apply token budget to prevent context overflow (R4 FIX)."""
        from backend.services.context_overflow import estimate_tokens
        
        estimated = estimate_tokens(messages)
        if estimated <= max_tokens:
            return messages
        
        logger.warning(f"Message history exceeds budget: {estimated} > {max_tokens}, truncating...")
        
        # Keep system messages, drop oldest user/assistant messages
        system_messages = [m for m in messages if m.get("role") == "system"]
        other_messages = [m for m in messages if m.get("role") != "system"]
        
        # Truncate from the beginning (oldest messages)
        while estimate_tokens(system_messages + other_messages) > max_tokens and len(other_messages) > 1:
            other_messages.pop(0)
        
        result = system_messages + other_messages
        new_estimated = estimate_tokens(result)
        logger.info(f"Truncated to {len(result)} messages, estimated {new_estimated} tokens")
        
        return result

    def _classify_task(self, content: str) -> tuple[str, str]:
        """Regex fallback for task classification."""
        for task_type, worker, pattern in TASK_PATTERNS:
            if pattern.search(content):
                return task_type, worker
        return TaskType.FEATURE.value, "coding"

    def _extract_title(self, content: str) -> str:
        """Extract a reasonable title from user content."""
        title = content.strip()
        if not title:
            return ""
        # Remove common prefixes
        title = re.sub(r"^(please|can you|could you|I want to|I need to|help me)\s+", "", title, flags=re.I)
        # Capitalize first letter
        if title:
            title = title[0].upper() + title[1:]
        # Truncate
        if len(title) > 80:
            title = title[:77] + "..."
        return title

    async def _record_audit(
        self,
        intent: str,
        content: str,
        metadata: dict,
        conversation,
    ) -> None:
        """Record audit trail and events using a separate session (non-blocking)."""
        import asyncio
        from storage.database import async_session as _async_session
        from storage.models import AuditLog, Event as EventModel, Metric

        async def _do_record():
            try:
                async with _async_session() as s:
                    if metadata.get("task_id"):
                        s.add(AuditLog(
                            actor=f"user:{(conversation.context or {}).get('user_id', 'anonymous')}",
                            action="task.create",
                            resource_type="task",
                            resource_id=metadata["task_id"],
                            result="success",
                            details={"title": truncate_content(content, 200), "worker": metadata.get("worker"),
                                      "type": metadata.get("task_type"), "task_code": metadata.get("task_code")},
                        ))

                    s.add(EventModel(
                        type="conversation.message",
                        data={"intent": intent, "content_preview": content[:100],
                              "conversation_id": conversation.id, "task_id": metadata.get("task_id"),
                              "model": metadata.get("model", ""), "actor": "user"},
                        severity="info",
                        trace_id=metadata.get("trace_id"),
                    ))

                    total_tokens = metadata.get("total_tokens", 0)
                    if total_tokens > 0:
                        s.add(Metric(
                            name="llm.tokens.used",
                            value=float(total_tokens),
                            unit="tokens",
                            labels={"provider": metadata.get("provider", ""),
                                    "model": metadata.get("model", ""),
                                    "purpose": intent},
                        ))
                    await s.commit()
            except Exception as e:
                logger.debug(f"Failed to record audit: {e}")

        # Fire-and-forget: schedule in background, don't block the response
        # BUG-07 FIX: Store in module-level set to prevent GC when engine is destroyed
        task_ref = asyncio.create_task(_do_record())
        _global_background_tasks.add(task_ref)
        task_ref.add_done_callback(_global_background_tasks.discard)
