"""Chat routes — completion, streaming, cancel, regenerate, artifacts."""
import logging
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List

from backend.database.session import get_db, AsyncSessionLocal
from backend.models.ai_runtime import Artifact
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


# ---------------------------------------------------------------------------
# POST /chat  (non-streaming)
# ---------------------------------------------------------------------------

@router.post("/chat")
async def chat_endpoint(payload: ChatRequest, db: AsyncSession = Depends(get_db)):
    # resolve worker defaults if provided
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
        raise HTTPException(status_code=500, detail=str(e))


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
    from backend.services.agent_runner import AgentRunner
    from storage.models import Conversation

    user_content = payload.messages[-1].content if payload.messages else ""
    intent = classify_intent(user_content)
    logger.info(f"[EXECUTE] intent={intent} content={user_content[:50]}")

    # Only task_request goes through full pipeline
    if intent not in (INTENT_TASK_REQUEST, INTENT_TASK_CONFIRM):
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
    workspace = "."  # TODO: get from project context

    async def event_generator():
        try:
            # Step 1: Acknowledge intent
            try:
                yield f"data: {json.dumps({'type': 'intent', 'intent': intent, 'content': user_content})}\n\n"
            except Exception as e:
                logger.error(f"Intent stage error: {e}")
                yield f"data: {json.dumps({'type': 'error', 'stage': 'intent', 'error': f'Intent detection failed: {str(e)[:200]}'})}\n\n"
                return

            # Step 2: Start agent with real tool execution
            try:
                yield f"data: {json.dumps({'type': 'status', 'status': 'executing', 'worker': worker_type})}\n\n"

                runner = AgentRunner(workspace_root=workspace)
                final_content = ""

                async for event in runner.run_agent(
                    worker_type=worker_type,
                    prompt=user_content,
                    model_tier="crafter",
                    max_iterations=10,
                ):
                    if event["type"] == "content":
                        chunk = event.get("content", "")
                        final_content += chunk
                        yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
                    elif event["type"] == "tool_start":
                        yield f"data: {json.dumps({'type': 'tool_start', 'tool': event['tool'], 'args': event.get('args', {}), 'call_id': event.get('call_id', '')})}\n\n"
                    elif event["type"] == "tool_result":
                        args = event.get('args', {})
                        label_path = args.get('path', args.get('command', ''))
                        label = f"{event['tool']}: {label_path}"
                        yield f"data: {json.dumps({'type': 'tool_result', 'tool_call': {'id': event.get('call_id', ''), 'type': event['tool'], 'label': label, 'status': 'completed' if event.get('success') else 'error', 'output': event.get('output', ''), 'error': event.get('error'), 'args': args, 'duration_ms': 0, 'timestamp': ''}})}\n\n"
                    elif event["type"] == "error":
                        yield f"data: {json.dumps({'type': 'error', 'stage': 'agent_execution', 'error': event.get('error', 'Unknown error')})}\n\n"
                        return
                    elif event["type"] == "done":
                        yield f"data: {json.dumps({'type': 'status', 'status': 'completed', 'iterations': event.get('iterations', 0)})}\n\n"
                        deliverables = event.get("deliverables")
                        if deliverables:
                            yield f"data: {json.dumps({'type': 'deliverables', 'deliverables': deliverables})}\n\n"
            except LLMUnavailableError:
                yield f"data: {json.dumps({'type': 'error', 'stage': 'llm_call', 'error': 'No AI provider configured. Add a provider in Settings.'})}\n\n"
                return
            except PermissionError as e:
                yield f"data: {json.dumps({'type': 'error', 'stage': 'permission', 'error': f'Permission denied: {e}'})}\n\n"
                return
            except Exception as e:
                logger.error(f"Agent execution stage error: {e}")
                yield f"data: {json.dumps({'type': 'error', 'stage': 'agent_execution', 'error': f'Execution failed: {str(e)[:200]}'})}\n\n"
                return

            # Step 3: Store messages in conversation
            try:
                async with AsyncSessionLocal() as session:
                    from datetime import datetime, timezone
                    now = datetime.now(timezone.utc)
                    # Persist user message
                    user_msg = Message(
                        conversation_id=payload.conversation_id,
                        role="user",
                        content=user_content,
                        created_at=now,
                        updated_at=now,
                        status="completed",
                    )
                    session.add(user_msg)
                    # Persist assistant response
                    msg = Message(
                        conversation_id=payload.conversation_id,
                        role="assistant",
                        content=final_content,
                        created_at=now,
                        updated_at=now,
                    )
                    session.add(msg)
                    await session.commit()
            except Exception as e:
                logger.error(f"Storage stage error: {e}")
                yield f"data: {json.dumps({'type': 'error', 'stage': 'storage', 'error': f'Failed to save response: {str(e)[:200]}'})}\n\n"
                return

            yield f"data: {json.dumps({'type': 'done', 'intent': intent})}\n\n"

        except LLMUnavailableError:
            yield f"data: {json.dumps({'type': 'error', 'stage': 'pipeline', 'error': 'No AI provider configured. Add a provider in Settings.'})}\n\n"
        except PermissionError as e:
            yield f"data: {json.dumps({'type': 'error', 'stage': 'pipeline', 'error': f'Permission denied: {e}'})}\n\n"
        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'stage': 'pipeline', 'error': f'Execution failed: {str(e)[:200]}'})}\n\n"

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
        tool_service = ToolAwareChatService(workspace_root=workspace_root)

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
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

        return StreamingResponse(tool_event_generator(), media_type="text/event-stream")

    async def event_generator():
        # BUG-11 FIX: Persist user + assistant messages for plain chat path.
        # chat_service.chat_stream already persists internally, but we collect
        # the streamed content here as a safety net to guarantee persistence
        # even if the internal commit fails or the session lifecycle is off.
        collected_content = ""
        try:
            async for chunk in chat_service.chat_stream(
                db, payload.conversation_id, messages_list, prov_id, mod_id, temp, top_p, max_t, system_prompt
            ):
                # Extract content from SSE chunks for persistence
                try:
                    if chunk.startswith("data: "):
                        data = json.loads(chunk[6:].strip())
                        if data.get("type") == "chunk" and data.get("content"):
                            collected_content += data["content"]
                except (json.JSONDecodeError, AttributeError):
                    pass
                yield chunk
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

        # BUG-11 FIX: If chat_service.chat_stream didn't persist (e.g. session
        # lifecycle issue), ensure messages are saved with a dedicated session.
        if collected_content:
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
