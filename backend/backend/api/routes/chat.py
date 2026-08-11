"""Chat routes — completion, streaming, cancel, regenerate, artifacts."""
import asyncio
import logging
import json
import os
import re
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from pydantic import BaseModel, Field, EmailStr, validator

from backend.database.session import get_db, AsyncSessionLocal
from backend.api.dependencies import require_current_user
from backend.models.ai_runtime import Artifact
from backend.models.conversation import Attachment
from backend.services.attachment_store import (
    save_attachment, decode_data_url, derive_file_type,
)
from storage.models import Message
from backend.schemas.ai_runtime_schemas import (
    ChatRequest, ChatCancelRequest, ChatRegenerateRequest,
    ArtifactResponse,
)
from backend.services.chat_service import chat_service
from backend.services.worker_runtime_service import worker_runtime_service
from conversation.engine import (
    ConversationEngine,
    INTENT_CHAT, INTENT_QUESTION, INTENT_TASK_REQUEST,
    INTENT_TASK_CONFIRM, INTENT_STATUS, INTENT_APPROVAL,
    LLMUnavailableError,
)
from discovery.states import is_terminal

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_current_user)])

# Per-conversation in-process locks serializing the discovery auto-continuation
# (find-pending → respond → clear-pending). Two concurrent /chat/execute calls
# on the same conversation must not both consume the same DiscoverySession and
# both spawn agents. Entries are removed once a lock is released and free.
_clarify_locks: dict[str, asyncio.Lock] = {}

# Matches an explicit workspace answer in a clarification reply: an absolute
# filesystem path (Windows drive letter or POSIX "/"-prefixed).
_WORKSPACE_PATH_RE = re.compile(
    r"((?:[A-Za-z]:[\\/][^\s\"'<>|?*]+)|(?:/[^\s\"'<>|?*]+))",
)

_CLARIFY_NUDGE_TEXT = (
    "I still need your answers to the questions above — "
    "e.g. what the project should do and which folder to use. "
    "Please answer and resend."
)


def _get_clarify_lock(conversation_id: str) -> asyncio.Lock:
    """Get (or create) the per-conversation auto-continuation lock."""
    lock = _clarify_locks.get(conversation_id)
    if lock is None:
        lock = asyncio.Lock()
        _clarify_locks[conversation_id] = lock
    return lock


def _release_clarify_lock(conversation_id: str, lock: asyncio.Lock) -> None:
    """Drop the lock entry once it is truly free (no waiter re-acquired it)."""
    if not lock.locked():
        _clarify_locks.pop(conversation_id, None)


def _nudge_questions(workspace_unresolved: bool) -> list[dict]:
    """Questions re-asked with a nudge when a clarification reply did not
    resolve the pending discovery session (never spawn on chit-chat)."""
    questions = []
    if workspace_unresolved:
        questions.append(_workspace_question())
    if not questions:
        questions.append({
            "id": "details",
            "question": "Please answer the questions above and resend your request.",
            "options": [],
        })
    return questions


def _build_clarify_questions(missing_fields: list[str], workspace_unresolved: bool) -> list[dict]:
    """Build structured clarification questions for the /chat/execute gate.

    Each question is ``{id, question, options}`` where options may be empty for
    open-ended answers. The workspace question is appended whenever no project
    repo_path was resolvable so files never land in an ambiguous location.
    """
    from shared.intake import missing_field_question

    questions: list[dict] = []
    for field in missing_fields:
        text = missing_field_question(field)
        if text:
            questions.append({"id": field, "question": text, "options": []})

    if workspace_unresolved:
        questions.append(_workspace_question())

    if not questions:
        questions.append({
            "id": "details",
            "question": "Could you share a few more details about the request?",
            "options": [],
        })
    return questions


def _workspace_question() -> dict:
    """The workspace-selection question appended whenever no project repo_path
    could be resolved (so files never land in an ambiguous location)."""
    return {
        "id": "workspace",
        "question": "Which workspace folder should I create the project in?",
        "options": [
            "Create a new project folder",
            "Select an existing folder",
            "Use a per-chat sandbox",
        ],
    }


def _format_discovery_questions(questions) -> list[dict]:
    """Map DiscoveryEngine ClarificationQuestions to the SSE contract shape:
    ``{"id": "<slug>", "question": "<text>", "options": ["<opt1>", ...]}``."""
    return [
        {"id": str(q.id), "question": q.question, "options": q.options or []}
        for q in questions
    ]


def _discovery_reason(discovery_result) -> str:
    """Friendly intro for the clarify event — prefer the discovery engine's own
    message (first line), fall back to a default."""
    if discovery_result is not None and discovery_result.message:
        text = discovery_result.message.strip()
        if text:
            first_line = text.splitlines()[0]
            if first_line and len(first_line) <= 120:
                return first_line
    return "I need a few details before I can start building."


def _discovery_enrich_prompt(prompt: str, discovery_result) -> str:
    """Append a compact Discovery Brief summary to the agent prompt so the
    agent works from the brief when discovery reached is_ready."""
    brief = getattr(discovery_result, "brief", None)
    if brief is None:
        return prompt
    parts = [prompt]
    goal = getattr(brief, "engineering_goal", "") or ""
    if goal:
        parts.append(f"\n\n[Discovery Brief]\nGoal: {goal}")
    funcs = getattr(brief, "functional_requirements", None) or []
    req_texts = []
    for r in funcs[:6]:
        if isinstance(r, dict):
            text = r.get("description") or r.get("id") or ""
        else:
            text = str(r)
        if text:
            req_texts.append(text)
    if req_texts:
        parts.append("Requirements:\n- " + "\n- ".join(req_texts))
    return "\n".join(parts)


def _finalize_clarify_message(assistant_msg, reason: str, questions: list[dict], user_content: str, discovery_session_id: str | None = None) -> None:
    """Set the assistant row to a completed clarify message (questions as
    content) and persist the discovery session id in meta so the next message
    can auto-continue the discovery session."""
    if assistant_msg is None:
        return
    lines = [reason, ""]
    for i, q in enumerate(questions, 1):
        lines.append(f"{i}. {q['question']}")
        for opt in q.get("options") or []:
            lines.append(f"   - {opt}")
    assistant_msg.content = "\n".join(lines)
    assistant_msg.status = "completed"
    assistant_msg.updated_at = datetime.now(timezone.utc)
    assistant_msg.token_count = len(assistant_msg.content) // 4 + len(user_content) // 4
    if discovery_session_id:
        meta = dict(assistant_msg.meta or {})
        meta["discovery_session_id"] = discovery_session_id
        assistant_msg.meta = meta


async def _fetch_prior_user_history(conversation_id: str, exclude_message_id: str | None = None, limit: int = 10) -> list[dict]:
    """Fetch prior user messages for a conversation as
    ``[{"role": "user", "content": ...}]`` (chronological order)."""
    query = select(Message).where(
        Message.conversation_id == conversation_id,
        Message.role == "user",
    )
    if exclude_message_id:
        query = query.where(Message.id != exclude_message_id)
    query = query.order_by(Message.created_at.desc()).limit(limit)
    async with AsyncSessionLocal() as hsession:
        res = await hsession.execute(query)
        rows = [str(m.content) for m in res.scalars().all() if m.content]
    return [{"role": "user", "content": c} for c in reversed(rows)]


async def _run_discovery(conversation_id: str, corpus: str, history: list | None = None):
    """Run the real DiscoveryEngine pipeline in an isolated session.

    ``discover()`` commits internally, so it runs on its own session to avoid
    interfering with the streaming generator's message persistence.
    Returns a DiscoveryResult, or None when discovery is disabled / the
    conversation is gone / an exception occurred.
    """
    from storage.models import Conversation
    from discovery.engine import DiscoveryEngine
    try:
        async with AsyncSessionLocal() as dsession:
            conv = await dsession.get(Conversation, conversation_id)
            if conv is None:
                return None
            engine = DiscoveryEngine(dsession)
            return await engine.discover(conversation=conv, content=corpus, history=history)
    except Exception as e:
        logger.warning(f"Discovery pipeline failed (falling back to static clarify): {e}")
        return None


async def _respond_to_clarification(session_id: str, response: str, history: list | None = None):
    """Feed a user reply into a pending discovery session.

    Returns a DiscoveryResult, or None when the session is missing / terminal /
    an exception occurred.
    """
    from storage.models import DiscoverySession as DiscoverySessionModel
    from discovery.engine import DiscoveryEngine
    from discovery.states import is_terminal
    try:
        async with AsyncSessionLocal() as dsession:
            ds = await dsession.get(DiscoverySessionModel, session_id)
            if ds is None or is_terminal(ds.status):
                return None
            engine = DiscoveryEngine(dsession)
            return await engine.respond_to_clarification(session_id, response, history)
    except Exception as e:
        logger.warning(f"Discovery respond_to_clarification failed (falling through): {e}")
        return None


async def _find_pending_discovery_session(conversation_id: str) -> str | None:
    """Return the discovery_session_id of the most recent non-terminal discovery
    session waiting for a clarification response, if any.

    The marker lives in the latest assistant Message.meta["discovery_session_id"].
    """
    from storage.models import DiscoverySession as DiscoverySessionModel
    from discovery.states import is_terminal
    try:
        async with AsyncSessionLocal() as s:
            res = await s.execute(
                select(Message).where(
                    Message.conversation_id == conversation_id,
                    Message.role == "assistant",
                ).order_by(Message.created_at.desc()).limit(10)
            )
            for m in res.scalars().all():
                meta = m.meta or {}
                session_id = meta.get("discovery_session_id")
                if not session_id:
                    continue
                ds = await s.get(DiscoverySessionModel, session_id)
                # Skip sessions that are terminal OR already have a completed brief
                # (engineering_brief_complete is not in TERMINAL_STATES but should
                # not be treated as pending since the brief is already done).
                if ds is not None and not is_terminal(ds.status) and ds.status != "engineering_brief_complete":
                    return str(session_id)
        return None
    except Exception as e:
        logger.debug(f"Pending discovery lookup failed: {e}")
        return None


async def _clear_pending_discovery_meta(persist_session, conversation_id: str, session_id: str) -> None:
    """Remove the discovery_session_id marker from the assistant message that
    carried it so it cannot re-trigger the auto-continuation."""
    try:
        res = await persist_session.execute(
            select(Message).where(
                Message.conversation_id == conversation_id,
                Message.role == "assistant",
            ).order_by(Message.created_at.desc()).limit(10)
        )
        for m in res.scalars().all():
            meta = m.meta or {}
            if meta.get("discovery_session_id") == session_id:
                new_meta = dict(meta)
                new_meta.pop("discovery_session_id", None)
                m.meta = new_meta
                await persist_session.commit()
                return
    except Exception as e:
        logger.debug(f"Clear pending discovery meta failed: {e}")


async def _clarification_message_processed(session_id: str, message_id: str) -> bool:
    """True when this user message id already consumed the clarification.

    Idempotency guard for the auto-continuation: a retried /chat/execute with
    the same user message must not feed the same DiscoverySession twice.
    """
    if not session_id or not message_id:
        return False
    from storage.models import DiscoverySession as DiscoverySessionModel
    try:
        async with AsyncSessionLocal() as s:
            ds = await s.get(DiscoverySessionModel, session_id)
            if ds is None:
                return False
            ctx = ds.context or {}
            return message_id in (ctx.get("processed_message_ids") or [])
    except Exception as e:
        logger.debug(f"Clarification idempotency check failed: {e}")
        return False


async def _mark_clarification_processed(session_id: str, message_id: str) -> None:
    """Record that a user message consumed the clarification (idempotency)."""
    if not session_id or not message_id:
        return
    from storage.models import DiscoverySession as DiscoverySessionModel
    try:
        async with AsyncSessionLocal() as s:
            ds = await s.get(DiscoverySessionModel, session_id)
            if ds is None:
                return
            ctx = dict(ds.context or {})
            processed = list(ctx.get("processed_message_ids") or [])
            if message_id not in processed:
                processed.append(message_id)
            ctx["processed_message_ids"] = processed
            ds.context = ctx
            await s.commit()
    except Exception as e:
        logger.debug(f"Clarification idempotency mark failed: {e}")


async def _apply_workspace_answer(persist_session, conversation_id: str, reply: str) -> str | None:
    """Honor an explicit workspace answer in a clarification reply.

    Returns:
      - ``"sandbox"`` when the user chose the per-chat sandbox ("...sandbox...")
      - the absolute path when the reply pins a filesystem path (a Project row
        is created/reused and ``conversation.project_id`` is set)
      - ``None`` when the reply does not answer the workspace question — the
        caller keeps the clarify path instead of silently using the sandbox.
    """
    from storage.models import Conversation, Project

    lower = (reply or "").lower().strip()
    if "sandbox" in lower:
        return "sandbox"

    m = _WORKSPACE_PATH_RE.search(reply or "")
    if not m:
        return None
    path = m.group(1).strip().rstrip("/\\")
    if not path:
        return None
    # Defensive: only absolute paths are accepted (drive letter or /-prefixed).
    if not (re.match(r"^[A-Za-z]:[\\/]", path) or path.startswith("/")):
        return None

    try:
        os.makedirs(path, exist_ok=True)
    except OSError as e:
        logger.warning(f"Workspace answer path could not be created: {e}")
        return None

    base = os.path.basename(path) or "project"
    slug = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-") or "project"

    # Reuse an existing project pointing at the same folder, else create one
    # (slug collisions get a short unique suffix).
    project = (
        await persist_session.execute(select(Project).where(Project.repo_path == path))
    ).scalar_one_or_none()
    if project is None:
        clash = (
            await persist_session.execute(select(Project.id).where(Project.slug == slug))
        ).scalar_one_or_none()
        if clash:
            slug = f"{slug}-{uuid4().hex[:6]}"
        project = Project(
            name=base,
            slug=slug,
            description="Created from a chat workspace answer",
            repo_path=path,
            owner_id=None,
        )
        persist_session.add(project)
        await persist_session.flush()

    conv = await persist_session.get(Conversation, conversation_id)
    if conv is not None:
        conv.project_id = project.id
    await persist_session.commit()
    return str(path)


# ---------------------------------------------------------------------------
# POST /chat  (non-streaming)
# ---------------------------------------------------------------------------

@router.post("/chat")
async def chat_endpoint(payload: ChatRequest, db: AsyncSession = Depends(get_db)):
    # resolve worker defaults if provided
    prov_id = payload.provider_id
    mod_id = payload.model_id
    temp = payload.temperature if payload.temperature is not None else 0.4
    top_p = payload.top_p if payload.top_p is not None else 1.0
    max_t = payload.max_tokens

    system_prompt = None
    if payload.worker_role:
        worker = await worker_runtime_service.get_worker(db, payload.worker_role)
        if worker:
            prov_id = prov_id or worker.provider_id
            mod_id = mod_id or worker.model_id
            temp = worker.temperature if payload.temperature is None else temp
            top_p = worker.top_p if payload.top_p is None else top_p
            max_t = worker.max_output_tokens if payload.max_tokens is None else max_t
            system_prompt = worker.system_prompt or None

    # start worker execution tracking
    exec_rec = await worker_runtime_service.start_execution(
        db, payload.worker_role or "thinker", payload.conversation_id, "", prov_id, mod_id
    )

    try:
        messages_list = [{"role": m.role, "content": m.content} for m in payload.messages]
        res = await chat_service.chat_completion(
            db, payload.conversation_id, messages_list, prov_id, mod_id, temp, top_p, max_t, system_prompt
        )
        await worker_runtime_service.finish_execution(db, exec_rec.id, "completed")
        return res
    except Exception as e:
        await worker_runtime_service.finish_execution(db, exec_rec.id, "error")
        # QA-249-R5/F13: map LLM failures to proper status codes instead of a
        # raw 500. Log the internal detail server-side only.
        logger.error(f"chat_completion failed: {e}")
        from llm.provider import LLMError
        if isinstance(e, LLMError):
            msg = str(e).lower()
            if "no llm provider" in msg or "no provider" in msg or "not configured" in msg:
                raise HTTPException(status_code=503, detail="LLM provider is not configured")
            if "timeout" in msg or "timed out" in msg:
                raise HTTPException(status_code=502, detail="LLM provider timed out")
            if "connection" in msg or "refused" in msg or "unreachable" in msg:
                raise HTTPException(status_code=502, detail="LLM provider is unreachable")
            raise HTTPException(status_code=502, detail="LLM provider error")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# POST /chat/execute  (execute task with full tool visibility)
# ---------------------------------------------------------------------------

@router.post("/chat/execute")
async def chat_execute_endpoint(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    _auth: str = Depends(require_current_user),
):
    """Execute a task request with full pipeline visibility.
    
    Streams: intent detection, discovery, planning, task graph,
    worker execution (with real tools), verification.
    
    Use this for 'build' mode — user sees everything the AI company does.
    """
    from shared.intent_patterns import classify_intent
    from backend.services.agent_runner import AGENT_RUN_SEMAPHORE, AGENT_RUN_QUEUE_TIMEOUT, AgentRunner
    from storage.models import Conversation

    user_content = payload.messages[-1].content if payload.messages else ""
    
    # Sanitize user input to prevent XSS and ensure safe database storage
    from backend.middleware.input_sanitizer import sanitize_input
    sanitized_content = sanitize_input(user_content)
    
    intent = classify_intent(sanitized_content)
    logger.info(f"[EXECUTE] intent={intent} content={sanitized_content[:50]}")

    # Only task_request goes through full pipeline
    # QA-E2E FIX: multimodal requests (attachments present) must always go
    # through the agent_runner path — the legacy ChatService path drops
    # attachments, so a vision question would silently lose its image.
    has_attachments = bool(payload.attachments)

    # Discovery auto-continuation: if a previous assistant message left a
    # pending (non-terminal) discovery session awaiting clarification and the
    # user replied, this message MUST go through /chat/execute so the reply is
    # fed into respond_to_clarification — even if the reply is not itself
    # classified as a task_request.
    pending_discovery_session_id = None
    if not has_attachments:
        pending_discovery_session_id = await _find_pending_discovery_session(payload.conversation_id)

    if (intent not in (INTENT_TASK_REQUEST, INTENT_TASK_CONFIRM)
            and not has_attachments and not pending_discovery_session_id):
        # Not a task — fall back to regular chat
        return await chat_stream_endpoint(payload, db)

    # Get conversation for context
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Conversation).where(Conversation.id == payload.conversation_id)
        )
        conv = result.scalar_one_or_none()

    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # If the conversation has no project_id but the payload provides one, set it.
    # Defensive: only update if the project actually exists.
    if payload.project_id and not conv.project_id:
        try:
            async with AsyncSessionLocal() as session:
                from storage.models import Project
                proj_res = await session.execute(
                    select(Project).where(Project.id == payload.project_id)
                )
                project = proj_res.scalar_one_or_none()
                if project:
                    async with AsyncSessionLocal() as persist_session:
                        conv_row = await persist_session.get(Conversation, payload.conversation_id)
                        if conv_row is not None and not conv_row.project_id:
                            conv_row.project_id = project.id
                            await persist_session.commit()
        except Exception as e:
            logger.debug(f"Failed to link project_id to conversation: {e}")

    # Workflow-tags-to-worker-role mapping (only if payload.worker_role is default/empty).
    worker_type = payload.worker_role or "backend"
    audit_instruction_prefix = ""  # for bughunt tasks; defaults to empty string
    if not payload.worker_role:  # only map if caller didn't explicitly set a worker role
        first_tag = None
        if payload.tags and isinstance(payload.tags, list) and len(payload.tags) > 0:
            first_tag = payload.tags[0]
            workflow = first_tag.get("workflow", "")
            workflow_mapping = {
                "bughunt": ("qa", "Audit only — do NOT modify source code. Produce docs/BUG_REPORT.md with findings."),
                "test": ("qa", ""),
                "docs": ("documentation", ""),
                "bugfix": ("backend", ""),
                "refactor": ("backend", ""),
                "build": ("backend", ""),
                "feature": ("backend", ""),
                "infra": ("backend", ""),
                "research": ("backend", ""),
            }
            if workflow in workflow_mapping:
                mapped_role, audit_instruction_prefix = workflow_mapping[workflow]
                worker_type = mapped_role
    # Resolve workspace root with the shared resolver. Priority:
    #   1. payload.workspace
    #   2. conversation.project_id -> project.repo_path
    #   3. active local profile project -> project.repo_path
    #   4. per-conversation sandbox under DATA_DIR/workspaces (never process cwd)
    # ``workspace_resolved`` is False when only the sandbox fallback applied —
    # used by the clarify gate below to block agent runs that would write files
    # into an ambiguous location.
    async with AsyncSessionLocal() as session:
        from shared.workspace import resolve_conversation_workspace
        workspace, workspace_resolved = await resolve_conversation_workspace(
            session, payload.workspace, payload.conversation_id
        )
        # HYBRID (Option C): remember the last resolved workspace folder on the
        # local profile, so a later task_confirm with no pinned folder auto-
        # resolves to it (surfaced below for confirmation) instead of asking.
        if workspace_resolved and workspace and workspace != "sandbox":
            try:
                from backend.models.local_profile import LocalProfile
                prof = (await session.execute(
                    select(LocalProfile).limit(1)
                )).scalar_one_or_none()
                if prof is not None:
                    prof.last_used_repo_path = workspace
                    await session.commit()
            except Exception as e:
                logger.debug(f"Persist last_used_repo_path skipped: {e}")

    async def event_generator():
        # The workspace may be re-pinned by the auto-continuation when the user
        # answers the workspace question with a path — propagate to the agent.
        nonlocal workspace, workspace_resolved, audit_instruction_prefix
        persist_session = AsyncSessionLocal()
        user_msg = None
        assistant_msg = None
        chunks_since_commit = 0
        # The prompt the agent receives. Discovery enrichment (brief) is applied
        # to this variable; ``user_content`` stays the original user text.
        # For bughunt tasks, prepend an audit instruction so the LLM knows not
        # to write source code but instead produce a report.
        base_prompt = audit_instruction_prefix + ("\n\n" if audit_instruction_prefix else "") + user_content
        agent_prompt = base_prompt
        # FIX: cooperative cancellation — set when the client disconnects so
        # the AgentRunner loop (which receives this event) stops executing
        # tools instead of continuing in the background after "Stop".
        cancel_event = asyncio.Event()
        try:
            # Persist both records before execution starts. Command Center work
            # can run for a long time, so the conversation must survive a view
            # change, renderer restart, or interrupted agent run.
            now = datetime.now(timezone.utc)
            user_msg = Message(
                conversation_id=payload.conversation_id,
                role="user",
                content=user_content,
                created_at=now,
                updated_at=now,
                status="completed",
                token_count=len(user_content) // 4,
            )
            assistant_msg = Message(
                conversation_id=payload.conversation_id,
                role="assistant",
                content="",
                created_at=now + timedelta(milliseconds=1),
                updated_at=now,
                status="streaming",
                token_count=0,
            )
            persist_session.add_all([user_msg, assistant_msg])
            await persist_session.commit()

            # Persist attachment metadata AND binary so attachments survive
            # backup/restore. The renderer sends each file as a base64 data URL
            # ({name, mime_type, data_url}) inside payload.attachments; decode
            # it and store the bytes at DATA_DIR/attachments/<attachment_id>.
            # The metadata rows are linked to the user message (attachment-creation
            # path for the chat flow). Failures are logged and skipped — the chat
            # stream must never break because a file could not be written.
            if payload.attachments:
                for a in payload.attachments:
                    try:
                        if not isinstance(a, dict):
                            continue
                        data_url = a.get("data_url", "")
                        name = a.get("name") or "attachment"
                        mime = a.get("mime_type") or "application/octet-stream"
                        data = decode_data_url(data_url)
                        if data is None:
                            logger.warning(f"Skipping attachment {name!r}: no decodable data_url")
                            continue
                        att = Attachment(
                            message_id=user_msg.id,
                            file_name=name,
                            file_type=derive_file_type(mime, name),
                            mime_type=mime,
                            file_size=len(data),
                        )
                        persist_session.add(att)
                        await persist_session.flush()
                        save_attachment(att.id, data)
                    except Exception as e:
                        logger.warning(f"Failed to persist attachment binary: {e}")
                await persist_session.commit()

            # Step 1: Acknowledge intent
            try:
                yield f"data: {json.dumps({'type': 'intent', 'intent': intent, 'content': user_content})}\n\n"
            except Exception as e:
                logger.error(f"Intent stage error: {e}")
                yield f"data: {json.dumps({'type': 'error', 'stage': 'intent', 'error': f'Intent detection failed: {str(e)[:200]}'})}\n\n"
                return

            # Step 1.4: Discovery auto-continuation.
            #
            # If a previous assistant message left a pending discovery session
            # awaiting clarification, this message is a reply to it. Feed the
            # reply into the real DiscoveryEngine (respond_to_clarification) so
            # the request can progress instead of starting a fresh gate.
            #
            # Race guard: the find → respond → clear sequence runs under a
            # per-conversation in-process lock so two concurrent /chat/execute
            # calls cannot both consume the same DiscoverySession and both
            # spawn agents. Idempotency is enforced by recording the consuming
            # user message id in discovery_session.context["processed_message_ids"].
            # Defensive: any failure falls through to the normal gate.
            discovery_resolved = False
            if not has_attachments:
                clarify_lock = _get_clarify_lock(payload.conversation_id)
                await clarify_lock.acquire()
                try:
                    # Re-find under the lock — a concurrent request may have
                    # already consumed/cleared the pending marker.
                    current_pending = await _find_pending_discovery_session(payload.conversation_id)
                    if current_pending:
                        if not await _clarification_message_processed(
                            current_pending, user_msg.id if user_msg else ""
                        ):
                            # Honor an explicit workspace answer in the reply
                            # (absolute path or "use a per-chat sandbox").
                            workspace_answer = await _apply_workspace_answer(
                                persist_session, payload.conversation_id, user_content
                            )
                            if workspace_answer == "sandbox":
                                workspace_resolved = True
                            elif workspace_answer:
                                workspace = workspace_answer
                                workspace_resolved = True

                            history = await _fetch_prior_user_history(
                                payload.conversation_id,
                                exclude_message_id=user_msg.id if user_msg else None,
                            )
                            auto_result = await _respond_to_clarification(
                                session_id=current_pending,
                                response=user_content,
                                history=history,
                            )
                            await _mark_clarification_processed(
                                current_pending, user_msg.id if user_msg else ""
                            )

                            if auto_result is not None and auto_result.is_ready:
                                if not workspace_resolved:
                                    # Ready but the user never answered the
                                    # workspace question — keep the clarify path
                                    # (workspace only) instead of silently
                                    # writing files into the sandbox.
                                    questions = [_workspace_question()]
                                    reason = (
                                        "The request is ready to build. "
                                        "Which workspace folder should I create the project in?"
                                    )
                                    yield f"data: {json.dumps({'type': 'clarify', 'data': {'reason': reason, 'questions': questions}})}\n\n"
                                    _finalize_clarify_message(
                                        assistant_msg, reason, questions, user_content,
                                        discovery_session_id=current_pending,
                                    )
                                    await persist_session.commit()
                                    return
                                # Discovery completed — proceed to the agent
                                # with the enriched content and clear the
                                # pending marker.
                                agent_prompt = _discovery_enrich_prompt(user_content, auto_result)
                                discovery_resolved = True
                                await _clear_pending_discovery_meta(
                                    persist_session, payload.conversation_id, current_pending
                                )
                            elif (auto_result is not None and auto_result.clarification
                                    and auto_result.clarification.questions):
                                questions = _format_discovery_questions(auto_result.clarification.questions)
                                if not workspace_resolved:
                                    questions.append(_workspace_question())
                                reason = _discovery_reason(auto_result)
                                yield f"data: {json.dumps({'type': 'clarify', 'data': {'reason': reason, 'questions': questions}})}\n\n"
                                _finalize_clarify_message(
                                    assistant_msg, reason, questions, user_content,
                                    discovery_session_id=auto_result.metadata.get("session_id") or current_pending,
                                )
                                await persist_session.commit()
                                return
                            elif auto_result is not None and is_terminal(auto_result.state):
                                # The reply was classified non-task by discovery
                                # (e.g. "hi"/"ok") and it aborted the session —
                                # never spawn an agent on chit-chat. Nudge.
                                # CRITICAL FIX: DO NOT persist discovery_session_id here because
                                # the session is already terminated/aborted. Re-attaching would
                                # cause an infinite loop where ANY message keeps triggering discovery.
                                reason = _CLARIFY_NUDGE_TEXT
                                questions = _nudge_questions(not workspace_resolved)
                                yield f"data: {json.dumps({'type': 'clarify', 'data': {'reason': reason, 'questions': questions}})}\n\n"
                                _finalize_clarify_message(assistant_msg, reason, questions, user_content, discovery_session_id=None)
                                await persist_session.commit()
                                return
                            elif auto_result is None and intent not in (INTENT_TASK_REQUEST, INTENT_TASK_CONFIRM):
                                # Session gone/terminal or respond errored and
                                # the reply is not a fresh task request — treat
                                # it as an unanswered clarification: nudge, and
                                # never spawn the agent on the reply.
                                # CRITICAL FIX: If auto_result is None, the pending session
                                # is gone/errored — DO NOT re-attach marker. Only attach if
                                # we actually have a valid active session below.
                                reason = _CLARIFY_NUDGE_TEXT
                                questions = _nudge_questions(not workspace_resolved)
                                yield f"data: {json.dumps({'type': 'clarify', 'data': {'reason': reason, 'questions': questions}})}\n\n"
                                _finalize_clarify_message(assistant_msg, reason, questions, user_content, discovery_session_id=None)
                                await persist_session.commit()
                                return
                            # else: task_request with a consumed/errored session
                            # → fall through to the normal gate.
                finally:
                    clarify_lock.release()
                    _release_clarify_lock(payload.conversation_id, clarify_lock)

            # Routing sent us to /chat/execute because a pending discovery
            # session existed, but by the time we looked it was gone (consumed
            # by a concurrent request or it became terminal). If the reply is
            # not itself a fresh task request, never spawn the agent on it.
            if (pending_discovery_session_id and not has_attachments
                    and not discovery_resolved
                    and intent not in (INTENT_TASK_REQUEST, INTENT_TASK_CONFIRM)):
                reason = _CLARIFY_NUDGE_TEXT
                questions = _nudge_questions(not workspace_resolved)
                yield f"data: {json.dumps({'type': 'clarify', 'data': {'reason': reason, 'questions': questions}})}\n\n"
                _finalize_clarify_message(assistant_msg, reason, questions, user_content)
                await persist_session.commit()
                return

            # Step 1.5: Discovery / clarify gate.
            #
            # A vague task_request (or one with no workspace selected) must not
            # silently spawn an agent that writes files into an arbitrary
            # location. When the gate trips we run the REAL DiscoveryEngine — if
            # it produces clarification questions we emit a structured `clarify`
            # SSE event, finalize the assistant message, and return WITHOUT
            # spawning the agent. If discovery decides the request is ready, we
            # proceed to Step 2 with a brief-enriched prompt.
            #
            # SKIPPED entirely for:
            #  - multimodal requests (attachments present) — the attachment
            #    persistence path must never be blocked (test_attachment_store)
            #  - messages already resolved by the auto-continuation above
            #
            # INTENT_TASK_CONFIRM is included: a bare "yes / go ahead" with no
            # pending discovery session and no workspace must NOT run the agent
            # — it trips the gate and asks for workspace/details instead.
            if (not discovery_resolved
                    and intent in (INTENT_TASK_REQUEST, INTENT_TASK_CONFIRM)
                    and not has_attachments):
                from shared.intake import evaluate_intake_completeness

                # Corpus = current message + recent user history (mirrors
                # ConversationEngine._handle_task_request corpus accumulation).
                corpus_parts = [user_content]
                history = await _fetch_prior_user_history(
                    payload.conversation_id, exclude_message_id=user_msg.id if user_msg else None
                )
                for hmsg in history:
                    if hmsg.get("content"):
                        corpus_parts.append(str(hmsg["content"]))
                corpus = " ".join(corpus_parts)

                is_complete, missing_fields = evaluate_intake_completeness(corpus)

                # task_request gates on intake completeness + workspace;
                # task_confirm (no pending session) gates on workspace only —
                # the user already discussed the request, but the files still
                # need a home.
                gate_trips = (not workspace_resolved) or (
                    intent == INTENT_TASK_REQUEST and not is_complete
                )

                if gate_trips:
                    if intent == INTENT_TASK_REQUEST:
                        # Run the real DiscoveryEngine pipeline (rule-based, no LLM).
                        discovery_result = await _run_discovery(
                            conversation_id=payload.conversation_id,
                            corpus=corpus,
                            history=history,
                        )

                        if discovery_result is not None and discovery_result.is_ready:
                            # Request is now fully understood — proceed to Step 2
                            # with a brief-enriched prompt.
                            agent_prompt = _discovery_enrich_prompt(user_content, discovery_result)
                        else:
                            # Not ready → clarify with the DiscoveryEngine's questions.
                            if (discovery_result is not None and discovery_result.clarification
                                    and discovery_result.clarification.questions):
                                questions = _format_discovery_questions(discovery_result.clarification.questions)
                                reason = _discovery_reason(discovery_result)
                                discovery_session_id = discovery_result.metadata.get("session_id")
                            else:
                                # Discovery disabled / errored / produced no questions →
                                # static fallback (never crash the stream).
                                questions = _build_clarify_questions(
                                    missing_fields=missing_fields,
                                    workspace_unresolved=not workspace_resolved,
                                )
                                reason = (
                                    "I need a few details before I can start building. "
                                    "Please answer the questions below (and pick a workspace), then resend your request."
                                )
                                discovery_session_id = None

                            if not workspace_resolved:
                                questions.append(_workspace_question())

                            yield f"data: {json.dumps({'type': 'clarify', 'data': {'reason': reason, 'questions': questions}})}\n\n"

                            # Finalize the assistant row so it is never left in
                            # "streaming" after the generator returns, and persist
                            # the discovery session id so the next message can
                            # auto-continue the session.
                            _finalize_clarify_message(
                                assistant_msg, reason, questions, user_content,
                                discovery_session_id=discovery_session_id,
                            )
                            await persist_session.commit()
                            return
                    elif not workspace_resolved:
                        # INTENT_TASK_CONFIRM with no pending discovery session:
                        # "yes / go ahead" but no folder pinned. Ask for
                        # workspace/details instead of running the agent on a
                        # bare confirmation.
                        questions = _build_clarify_questions(
                            missing_fields=missing_fields,
                            workspace_unresolved=True,
                        )
                        reason = (
                            "You confirmed the task — but I still need a few details "
                            "(including the workspace folder) before I can start building."
                        )
                        yield f"data: {json.dumps({'type': 'clarify', 'data': {'reason': reason, 'questions': questions}})}\n\n"
                        _finalize_clarify_message(assistant_msg, reason, questions, user_content)
                        await persist_session.commit()
                        return
                    # else: workspace resolved + user confirmed → proceed to Step 2

            # Step 2: Start agent with real tool execution
            try:
                yield f"data: {json.dumps({'type': 'status', 'status': 'executing', 'worker': worker_type})}\n\n"
                # FIX: Broadcast worker.started event for Office Floor real-time updates
                try:
                    from backend.routes.websocket import broadcast_worker_event
                    await broadcast_worker_event(
                        f"worker.{worker_type}.started",
                        f"worker-{worker_type}",
                        {
                            "title": user_content[:100],  # First 100 chars as preview
                            "phase": "implementation",
                        }
                    )
                except Exception as e:
                    logger.debug(f"Chat agent started broadcast failed: {e}")

                # QA-FIX: image attachments require the vision tier — a
                # non-vision tier with an image silently fails upstream.
                model_tier = payload.model_tier or "crafter"
                if payload.attachments and any(
                    str(a.get("mime_type", "")).lower().startswith("image/")
                    for a in payload.attachments
                ):
                    model_tier = "vision"

                runner = AgentRunner(workspace_root=workspace)
                final_content = ""

                # HYBRID (Option C): always surface which folder the agent will
                # work in, so the user can confirm/correct before files are
                # written — even when the folder was auto-resolved from the
                # conversation project or the remembered last_used_repo_path.
                if workspace_resolved and workspace:
                    yield f"data: {json.dumps({'type': 'workspace', 'path': workspace, 'resolved': True})}\n\n"

                # QA-R5 FIX: cap concurrent agent runs. Every run holds a DB
                # session, an open LLM stream, and possibly subprocesses, so
                # unbounded parallelism (N open chats → N agent runs) is a
                # resource-exhaustion risk. The shared semaphore (also used by
                # /agent/run) is awaited — excess runs queue instead of
                # overloading the box. The non-agent chat paths never touch it.
                # Round-6 FIX: emit a "queued" status before waiting so the UI
                # shows the run is queued instead of silently hanging, and bound
                # the wait with a generous timeout (clean error on timeout).
                # BUG-FIX: only emit "queued" when the slot is NOT immediately
                # available — don't show a false queue when there is no
                # contention (the common single-user case).
                semaphore_acquired = False
                try:
                    if AGENT_RUN_SEMAPHORE.locked():
                        yield f"data: {json.dumps({'type': 'status', 'status': 'queued', 'worker': worker_type})}\n\n"
                    await asyncio.wait_for(AGENT_RUN_SEMAPHORE.acquire(), timeout=AGENT_RUN_QUEUE_TIMEOUT)
                    semaphore_acquired = True
                except asyncio.TimeoutError:
                    assistant_msg.status = "error"
                    assistant_msg.updated_at = datetime.now(timezone.utc)
                    await persist_session.commit()
                    yield f"data: {json.dumps({'type': 'error', 'stage': 'agent_execution', 'error': 'Agent queue is full. Try again in a moment.'})}\n\n"
                    return
                try:
                    async for event in runner.run_agent(
                        worker_type=worker_type,
                        prompt=agent_prompt,
                        model_tier=model_tier,
                        max_iterations=10,
                        attachments=payload.attachments,
                        db=db,
                        cancel_event=cancel_event,
                    ):
                        if event["type"] == "content":
                            chunk = event.get("content", "")
                            final_content += chunk
                            assistant_msg.content = final_content
                            assistant_msg.updated_at = datetime.now(timezone.utc)
                            assistant_msg.token_count = len(final_content) // 4 + len(user_content) // 4
                            chunks_since_commit += 1
                            # Bound database traffic while ensuring partial output
                            # is durable during long-running agent executions.
                            if chunks_since_commit >= 10:
                                await persist_session.commit()
                                chunks_since_commit = 0
                            yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
                        elif event["type"] == "tool_start":
                            yield f"data: {json.dumps({'type': 'tool_start', 'tool': event['tool'], 'args': event.get('args', {}), 'call_id': event.get('call_id', '')})}\n\n"
                        elif event["type"] == "tool_result":
                            args = event.get('args', {})
                            label_path = args.get('path', args.get('command', ''))
                            label = f"{event['tool']}: {label_path}"
                            yield f"data: {json.dumps({'type': 'tool_result', 'tool_call': {'id': event.get('call_id', ''), 'type': event['tool'], 'label': label, 'status': 'completed' if event.get('success') else 'error', 'output': event.get('output', ''), 'error': event.get('error'), 'args': args, 'duration_ms': 0, 'timestamp': ''}})}\n\n"
                        elif event["type"] == "overflow_warning":
                            # Forward the agent_runner context-overflow warning so
                            # the frontend can surface it (renderer has a
                            # "overflow_warning" case).
                            yield f"data: {json.dumps({'type': 'overflow_warning', 'estimated': event.get('estimated'), 'budget': event.get('budget')})}\n\n"
                        elif event["type"] == "error":
                            assistant_msg.status = "error"
                            assistant_msg.updated_at = datetime.now(timezone.utc)
                            await persist_session.commit()
                            yield f"data: {json.dumps({'type': 'error', 'stage': 'agent_execution', 'error': event.get('error', 'Unknown error')})}\n\n"
                            return
                        elif event["type"] == "done":
                            # FIX: Broadcast worker.completed event for Office Floor real-time updates
                            try:
                                from backend.routes.websocket import broadcast_worker_event
                                await broadcast_worker_event(
                                    f"worker.{worker_type}.completed",
                                    f"worker-{worker_type}",
                                    {
                                        "title": user_content[:100] if isinstance(user_content, str) else "Task completed",
                                        "phase": "complete",
                                        "iterations": event.get('iterations', 0),
                                    }
                                )
                            except Exception as e:
                                logger.debug(f"Chat agent completed broadcast failed: {e}")
                            
                            yield f"data: {json.dumps({'type': 'status', 'status': 'completed', 'iterations': event.get('iterations', 0)})}\n\n"
                            deliverables = event.get("deliverables")
                            if deliverables:
                                yield f"data: {json.dumps({'type': 'deliverables', 'deliverables': deliverables})}\n\n"
                        elif event["type"] == "cancelled":
                            # FIX: AgentRunner stopped cooperatively after the user
                            # hit Stop — persist a cancelled status instead of
                            # leaving the row in "streaming".
                            assistant_msg.status = "cancelled"
                            assistant_msg.updated_at = datetime.now(timezone.utc)
                            await persist_session.commit()
                            yield f"data: {json.dumps({'type': 'cancelled', 'reason': event.get('reason', 'User cancelled')})}\n\n"
                            return
                finally:
                    if semaphore_acquired:
                        AGENT_RUN_SEMAPHORE.release()
            except LLMUnavailableError:
                assistant_msg.status = "error"
                assistant_msg.updated_at = datetime.now(timezone.utc)
                await persist_session.commit()
                yield f"data: {json.dumps({'type': 'error', 'stage': 'llm_call', 'error': 'No AI provider configured. Add a provider in Settings.'})}\n\n"
                return
            except PermissionError as e:
                assistant_msg.status = "error"
                assistant_msg.updated_at = datetime.now(timezone.utc)
                await persist_session.commit()
                yield f"data: {json.dumps({'type': 'error', 'stage': 'permission', 'error': f'Permission denied: {e}'})}\n\n"
                return
            except Exception as e:
                logger.error(f"Agent execution stage error: {e}")
                assistant_msg.status = "error"
                assistant_msg.updated_at = datetime.now(timezone.utc)
                await persist_session.commit()
                yield f"data: {json.dumps({'type': 'error', 'stage': 'agent_execution', 'error': f'Execution failed: {str(e)[:200]}'})}\n\n"
                return

            # Step 3: Finalize the records created before execution.
            assistant_msg.content = final_content
            assistant_msg.updated_at = datetime.now(timezone.utc)
            assistant_msg.status = "completed"
            assistant_msg.token_count = len(final_content) // 4 + len(user_content) // 4
            await persist_session.commit()

            # FIX: index the persisted messages so /conversations/search finds
            # /chat/execute content (the REST routes index; this path did not).
            try:
                from backend.services.search_service import index_message_fts
                if user_msg is not None:
                    await index_message_fts(persist_session, user_msg.id, payload.conversation_id, user_content)
                if assistant_msg is not None and final_content:
                    await index_message_fts(persist_session, assistant_msg.id, payload.conversation_id, final_content)
            except Exception as fts_err:
                logger.warning(f"FTS indexing failed (non-critical): {fts_err}")

            yield f"data: {json.dumps({'type': 'done', 'intent': intent})}\n\n"

        except LLMUnavailableError:
            if assistant_msg is not None:
                assistant_msg.status = "error"
                assistant_msg.updated_at = datetime.now(timezone.utc)
                await persist_session.commit()
            yield f"data: {json.dumps({'type': 'error', 'stage': 'pipeline', 'error': 'No AI provider configured. Add a provider in Settings.'})}\n\n"
        except PermissionError as e:
            if assistant_msg is not None:
                assistant_msg.status = "error"
                assistant_msg.updated_at = datetime.now(timezone.utc)
                await persist_session.commit()
            yield f"data: {json.dumps({'type': 'error', 'stage': 'pipeline', 'error': f'Permission denied: {e}'})}\n\n"
        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            if assistant_msg is not None:
                assistant_msg.status = "error"
                assistant_msg.updated_at = datetime.now(timezone.utc)
                await persist_session.commit()
            yield f"data: {json.dumps({'type': 'error', 'stage': 'pipeline', 'error': f'Execution failed: {str(e)[:200]}'})}\n\n"
        except GeneratorExit:
            # H4: client disconnected mid-stream. Persist a cancelled status so
            # the assistant row is never left stuck in "streaming" forever, then
            # let the generator close cleanly.
            cancel_event.set()
            try:
                if assistant_msg is not None:
                    assistant_msg.status = "cancelled"
                    assistant_msg.updated_at = datetime.now(timezone.utc)
                    await persist_session.commit()
            except Exception as log_err:
                logger.warning(f"Failed to persist cancelled status on disconnect: {log_err}")
            raise
        finally:
            # FIX: signal the AgentRunner to stop at its next checkpoint on any
            # exit path (normal completion, error, or disconnect) so the agent
            # loop never keeps running in the background after the stream ends.
            cancel_event.set()
            await persist_session.close()

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# POST /chat/stream  (streaming with intent detection)
# ---------------------------------------------------------------------------

@router.post("/chat/stream")
async def chat_stream_endpoint(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    _auth: str = Depends(require_current_user),
):
    # WP-01: Intent detection (via shared patterns — single source of truth)
    from shared.intent_patterns import classify_intent
    user_content = payload.messages[-1].content if payload.messages else ""
    intent = classify_intent(user_content)
    logger.info(f"[INTENT] detected={intent} content={user_content[:50]}")

    # WP-02: Route based on intent
    if intent in (INTENT_TASK_REQUEST, INTENT_TASK_CONFIRM, INTENT_STATUS, INTENT_APPROVAL):
        # Non-streaming intents - use ConversationEngine (single call)
        from storage.models import Conversation

        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(Conversation).where(Conversation.id == payload.conversation_id)
                )
                conv = result.scalar_one_or_none()
                if conv:
                    engine = ConversationEngine(session)
                    # FIX: call process_message exactly once and reuse the result
                    response = await engine.process_message(conv, user_content)
                    await session.commit()

                    # Pipeline is launched by ConversationEngine._launch_pipeline()
                    # No need for duplicate dispatch here

                    # Return as SSE
                    async def event_generator():
                        content = response.content
                        metadata = response.meta if hasattr(response, 'meta') else {}
                        chunk_size = 20
                        for i in range(0, len(content), chunk_size):
                            chunk = content[i:i + chunk_size]
                            yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
                        yield f"data: {json.dumps({'type': 'done', 'intent': intent, 'metadata': metadata})}\n\n"

                    return StreamingResponse(event_generator(), media_type="text/event-stream")
                else:
                    # Conversation not found - fallback to ChatService
                    logger.warning(f"Conversation {payload.conversation_id} not found, falling back to ChatService")
                    intent = INTENT_CHAT
        except Exception as e:
            # ConversationEngine failed - fallback to ChatService
            logger.error(f"ConversationEngine failed: {e}, falling back to ChatService")
            intent = INTENT_CHAT

    # Default: streaming chat via ChatService
    prov_id = payload.provider_id
    mod_id = payload.model_id
    temp = payload.temperature or 0.4
    top_p = payload.top_p or 1.0
    max_t = payload.max_tokens

    system_prompt = None
    if payload.worker_role:
        worker = await worker_runtime_service.get_worker(db, payload.worker_role)
        if worker:
            prov_id = prov_id or worker.provider_id
            mod_id = mod_id or worker.model_id
            temp = worker.temperature if payload.temperature is None else temp
            top_p = worker.top_p if payload.top_p is None else top_p
            max_t = worker.max_output_tokens if payload.max_tokens is None else max_t
            system_prompt = worker.system_prompt or None

    messages_list = [{"role": m.role, "content": m.content} for m in payload.messages]

    # Use tool-aware streaming if worker_role is set (enables tool execution)
    use_tools = payload.worker_role is not None and payload.worker_role != "thinker"

    if use_tools:
        from backend.services.tool_chat_service import ToolAwareChatService

        # M7 FIX: resolve the workspace from the conversation's project via the
        # shared policy (never process cwd). Falls back to the per-conversation
        # sandbox when no project repo_path is pinned.
        from shared.workspace import resolve_conversation_workspace
        async with AsyncSessionLocal() as ws_session:
            workspace_root, _ws_resolved = await resolve_conversation_workspace(
                ws_session, None, payload.conversation_id
            )
        # S1 FIX: do NOT pass the client-supplied worker_role into the chat
        # tool path — it is untrusted and previously granted shell/write_file
        # for coder roles. The chat tool path always uses the safe read-only
        # default allowlist (see _chat_permission_checker).
        tool_service = ToolAwareChatService(
            workspace_root=workspace_root,
        )

        async def tool_event_generator():
            # S3 FIX: collect streamed content so the assistant reply is
            # persisted. Previously only the user message was committed here,
            # so the assistant's tool-chat answer vanished on reload.
            collected_content = ""
            try:
                # Persist user message
                from datetime import datetime, timezone
                from storage.models import Message
                user_content = messages_list[-1].get("content", "") if messages_list else ""
                if user_content:
                    user_msg = Message(
                        conversation_id=payload.conversation_id,
                        role="user",
                        content=user_content,
                        status="completed",
                        created_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc),
                        token_count=len(user_content) // 4,  # estimate ~4 chars/token
                    )
                    db.add(user_msg)
                    await db.commit()

                async for sse_event in tool_service.stream_with_tools(
                    messages=messages_list,
                    system_prompt=system_prompt,
                    temperature=temp,
                    max_tokens=max_t,
                ):
                    # Collect content chunks for persistence
                    try:
                        if sse_event.startswith("data: "):
                            data = json.loads(sse_event[6:].strip())
                            if data.get("type") == "chunk" and data.get("content"):
                                collected_content += data["content"]
                    except (json.JSONDecodeError, AttributeError):
                        pass
                    yield sse_event

                # S3 FIX: persist the assistant message after stream completes
                if collected_content:
                    from datetime import datetime, timezone
                    from storage.models import Message as _Msg
                    asst_msg = _Msg(
                        conversation_id=payload.conversation_id,
                        role="assistant",
                        content=collected_content,
                        status="completed",
                        created_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc),
                        token_count=len(collected_content) // 4,
                    )
                    db.add(asst_msg)
                    await db.commit()
            except Exception as e:
                # Round-6 FIX: log the raw error server-side, return a fixed
                # friendly message to the client.
                logger.error(f"Tool chat stream failed: {e}")
                yield f"data: {json.dumps({'type': 'error', 'error': 'Chat failed. Please try again.'})}\n\n"

        return StreamingResponse(tool_event_generator(), media_type="text/event-stream")

    async def event_generator():
        # BUG-11 FIX: Persist user + assistant messages for plain chat path.
        # chat_service.chat_stream already persists internally, but we collect
        # the streamed content here as a safety net to guarantee persistence
        # even if the internal commit fails or the session lifecycle is off.
        # NOTE: Vision/multimodal requests are handled by POST /chat/execute,
        # which passes payload.model_tier ("vision") into AgentRunner and maps
        # it to ModelTier.VISION (agent_runner.py). This legacy ChatService
        # path stays provider_id/model_id based and does not support vision.
        collected_content = ""
        stream_message_id = None
        try:
            async for chunk in chat_service.chat_stream(
                db, payload.conversation_id, messages_list, prov_id, mod_id, temp, top_p, max_t, system_prompt
            ):
                # Extract content from SSE chunks for persistence
                try:
                    if chunk.startswith("data: "):
                        data = json.loads(chunk[6:].strip())
                        if data.get("type") == "start" and data.get("message_id"):
                            stream_message_id = data["message_id"]
                        elif data.get("type") == "chunk" and data.get("content"):
                            collected_content += data["content"]
                except (json.JSONDecodeError, AttributeError):
                    pass
                yield chunk
        except Exception as e:
            # Round-6 FIX: log the raw error server-side, return a fixed
            # friendly message to the client.
            logger.error(f"Chat stream failed: {e}")
            yield f"data: {json.dumps({'type': 'error', 'error': 'Chat failed. Please try again.'})}\n\n"

        # BUG-11 FIX: If chat_service.chat_stream didn't persist (e.g. session
        # lifecycle issue), ensure messages are saved with a dedicated session.
        # Gate on the `start` event: chat_stream persists the user + assistant
        # messages itself once it reaches `start` (a rewrite pass may change the
        # persisted content, so a content-based dedup check would double-persist).
        if collected_content and not stream_message_id:
            try:
                from backend.database.session import AsyncSessionLocal
                from datetime import datetime, timezone
                async with AsyncSessionLocal() as persist_session:
                    now = datetime.now(timezone.utc)
                    # Check if user message already persisted (avoid double-persist)
                    existing = await persist_session.execute(
                        select(Message).where(
                            Message.conversation_id == payload.conversation_id,
                            Message.role == "user",
                            Message.content == user_content,
                        ).order_by(Message.created_at.desc()).limit(1)
                    )
                    if not existing.scalar_one_or_none():
                        user_msg = Message(
                            conversation_id=payload.conversation_id,
                            role="user",
                            content=user_content,
                            status="completed",
                            created_at=now,
                            updated_at=now,
                        )
                        persist_session.add(user_msg)

                    # Check if assistant message already persisted
                    existing_asst = await persist_session.execute(
                        select(Message).where(
                            Message.conversation_id == payload.conversation_id,
                            Message.role == "assistant",
                            Message.content == collected_content,
                        ).order_by(Message.created_at.desc()).limit(1)
                    )
                    if not existing_asst.scalar_one_or_none():
                        asst_msg = Message(
                            conversation_id=payload.conversation_id,
                            role="assistant",
                            content=collected_content,
                            status="completed",
                            created_at=now,
                            updated_at=now,
                        )
                        persist_session.add(asst_msg)

                    await persist_session.commit()
            except Exception as persist_err:
                logger.warning(f"BUG-11 persistence safety net error: {persist_err}")

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# POST /chat/cancel
# ---------------------------------------------------------------------------

@router.post("/chat/cancel")
async def chat_cancel_endpoint(payload: ChatCancelRequest, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Message).where(Message.id == payload.message_id))
    msg = res.scalars().first()
    if msg and msg.status == "streaming":
        msg.status = "cancelled"
        await db.commit()
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# POST /chat/regenerate
# ---------------------------------------------------------------------------

@router.post("/chat/regenerate")
async def chat_regenerate_endpoint(payload: ChatRegenerateRequest, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Message).where(Message.conversation_id == payload.conversation_id).order_by(Message.created_at))
    msgs = res.scalars().all()

    msg_history = []
    for m in msgs:
        if m.id == payload.message_id:
            break
        msg_history.append({"role": m.role, "content": m.content})

    if not msg_history:
        raise HTTPException(status_code=400, detail="Cannot regenerate without prior context")

    # execute completion
    return await chat_service.chat_completion(db, payload.conversation_id, msg_history, None, None)


# ---------------------------------------------------------------------------
# GET /artifacts/{conversation_id}
# ---------------------------------------------------------------------------

@router.get("/artifacts/{conversation_id}", response_model=List[ArtifactResponse])
async def list_artifacts(conversation_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Artifact).where(Artifact.conversation_id == conversation_id).order_by(Artifact.created_at))
    return res.scalars().all()

# ─────────────────────────────────────────────────────────────────────────────
# Discovery Enhancement — LLM-generated contextual questions
# ─────────────────────────────────────────────────────────────────────────────


