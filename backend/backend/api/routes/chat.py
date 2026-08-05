"""Chat routes — completion, streaming, cancel, regenerate, artifacts."""
import asyncio
import logging
import json
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List

from backend.database.session import get_db, AsyncSessionLocal
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
from backend.routes.conversations import _dispatch_created_task

logger = logging.getLogger(__name__)

router = APIRouter()


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
        questions.append({
            "id": "workspace",
            "question": "Which workspace folder should I create the project in?",
            "options": [
                "Create a new project folder",
                "Select an existing folder",
                "Use a per-chat sandbox",
            ],
        })

    if not questions:
        questions.append({
            "id": "details",
            "question": "Could you share a few more details about the request?",
            "options": [],
        })
    return questions


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
async def chat_execute_endpoint(payload: ChatRequest, db: AsyncSession = Depends(get_db)):
    """Execute a task request with full pipeline visibility.
    
    Streams: intent detection, discovery, planning, task graph,
    worker execution (with real tools), verification.
    
    Use this for 'build' mode — user sees everything the AI company does.
    """
    from shared.intent_patterns import classify_intent
    from backend.services.agent_runner import AGENT_RUN_SEMAPHORE, AGENT_RUN_QUEUE_TIMEOUT, AgentRunner
    from storage.models import Conversation

    user_content = payload.messages[-1].content if payload.messages else ""
    intent = classify_intent(user_content)
    logger.info(f"[EXECUTE] intent={intent} content={user_content[:50]}")

    # Only task_request goes through full pipeline
    # QA-E2E FIX: multimodal requests (attachments present) must always go
    # through the agent_runner path — the legacy ChatService path drops
    # attachments, so a vision question would silently lose its image.
    has_attachments = bool(payload.attachments)
    if intent not in (INTENT_TASK_REQUEST, INTENT_TASK_CONFIRM) and not has_attachments:
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

    worker_type = payload.worker_role or "backend"
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

    async def event_generator():
        persist_session = AsyncSessionLocal()
        user_msg = None
        assistant_msg = None
        chunks_since_commit = 0
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

            # Step 1.5: Discovery / clarify gate.
            #
            # A vague task_request (or one with no workspace selected) must not
            # silently spawn an agent that writes files into an arbitrary
            # location. When the gate trips we emit a structured `clarify` SSE
            # event, finalize the assistant message with the questions, and
            # return WITHOUT spawning the agent.
            #
            # SKIPPED entirely for:
            #  - multimodal requests (attachments present) — the attachment
            #    persistence path must never be blocked (test_attachment_store)
            #  - non task_request intents (task_confirm / chat-with-attachment)
            if intent == INTENT_TASK_REQUEST and not has_attachments:
                from shared.intake import evaluate_intake_completeness

                # Corpus = current message + recent user history (mirrors
                # ConversationEngine._handle_task_request corpus accumulation).
                corpus_parts = [user_content]
                try:
                    hist_res = await persist_session.execute(
                        select(Message).where(
                            Message.conversation_id == payload.conversation_id,
                            Message.role == "user",
                        ).order_by(Message.created_at.desc()).limit(10)
                    )
                    for hmsg in hist_res.scalars().all():
                        if hmsg.content:
                            corpus_parts.append(str(hmsg.content))
                except Exception as hist_err:
                    logger.debug(f"Clarify gate history fetch skipped: {hist_err}")
                corpus = " ".join(corpus_parts)

                is_complete, missing_fields = evaluate_intake_completeness(corpus)

                if (not workspace_resolved) or (not is_complete):
                    questions = _build_clarify_questions(
                        missing_fields=missing_fields,
                        workspace_unresolved=not workspace_resolved,
                    )
                    reason = (
                        "I need a few details before I can start building. "
                        "Please answer the questions below (and pick a workspace), then resend your request."
                    )
                    yield f"data: {json.dumps({'type': 'clarify', 'data': {'reason': reason, 'questions': questions}})}\n\n"

                    # Finalize the assistant row so it is never left in
                    # "streaming" after the generator returns.
                    if assistant_msg is not None:
                        lines = [reason, ""]
                        for i, q in enumerate(questions, 1):
                            lines.append(f"{i}. {q['question']}")
                            for opt in q.get("options") or []:
                                lines.append(f"   - {opt}")
                        assistant_msg.content = "\n".join(lines)
                        assistant_msg.status = "completed"
                        assistant_msg.updated_at = datetime.now(timezone.utc)
                        assistant_msg.token_count = len(assistant_msg.content) // 4 + len(user_content) // 4
                    await persist_session.commit()
                    return

            # Step 2: Start agent with real tool execution
            try:
                yield f"data: {json.dumps({'type': 'status', 'status': 'executing', 'worker': worker_type})}\n\n"

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

                # QA-R5 FIX: cap concurrent agent runs. Every run holds a DB
                # session, an open LLM stream, and possibly subprocesses, so
                # unbounded parallelism (N open chats → N agent runs) is a
                # resource-exhaustion risk. The shared semaphore (also used by
                # /agent/run) is awaited — excess runs queue instead of
                # overloading the box. The non-agent chat paths never touch it.
                # Round-6 FIX: emit a "queued" status before waiting so the UI
                # shows the run is queued instead of silently hanging, and bound
                # the wait with a generous timeout (clean error on timeout).
                semaphore_acquired = False
                try:
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
                        prompt=user_content,
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
async def chat_stream_endpoint(payload: ChatRequest, db: AsyncSession = Depends(get_db)):
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
        import os

        # Determine workspace root from conversation context
        workspace_root = os.getcwd()
        # QA-E2E FIX: pass the worker_type so the chat tool path uses the
        # worker's real permission set (write_file/shell for dev roles) instead
        # of falling back to the read-only default. Permission gating is still
        # enforced via check_permission inside ToolExecutor.
        tool_service = ToolAwareChatService(
            workspace_root=workspace_root,
            worker_type=payload.worker_role,
        )

        async def tool_event_generator():
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
                    yield sse_event
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
