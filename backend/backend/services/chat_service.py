import time
import json
import logging
import httpx
from typing import AsyncGenerator, Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.models.schema import Provider, ProviderModel
from storage.models import Message
from backend.models.ai_runtime import GenerationLog, ToolCall, ToolResult
from backend.services.crypto import decrypt as decrypt_api_key
from backend.services.tool_dispatcher import tool_dispatcher
from backend.services.artifact_service import artifact_service

logger = logging.getLogger(__name__)


async def build_chat_context(
    db: AsyncSession,
    conversation_id: str,
    query: str,
    token_budget: int = 4000,
) -> str:
    """Build context for chat using the context pipeline.

    Args:
        db: Database session
        conversation_id: Conversation ID
        query: User query
        token_budget: Token budget for context

    Returns:
        Formatted context string
    """
    try:
        from context.builder import create_builder

        builder = create_builder(
            db,
            conversation_id=conversation_id,
            token_budget=token_budget,
        )

        assembly = await builder.build(query, max_tokens=token_budget)
        context = builder.format_for_prompt(assembly)

        if context:
            logger.info(
                f"Chat context built: {assembly.total_tokens} tokens, "
                f"sources: {assembly.sources_used}"
            )

        return context
    except Exception as e:
        logger.warning(f"Failed to build chat context: {e}")
        return ""

class ChatService:
    @staticmethod
    async def _get_provider_config(db: AsyncSession, provider_id: str | None) -> tuple[str, str] | None:
        if not provider_id:
            # Auto-detect: find first enabled provider
            res = await db.execute(select(Provider).where(Provider.enabled == True).limit(1))
            p = res.scalars().first()
            if p:
                provider_id = p.id
        else:
            res = await db.execute(select(Provider).where(Provider.id == provider_id))
            p = res.scalars().first()
            if not p or not p.enabled:
                p = None
        
        if p and p.enabled:
            base_url = p.base_url.rstrip("/")
            if not base_url.endswith("/v1"):
                base_url += "/v1"
            api_key = decrypt_api_key(p.api_key)
            return base_url, api_key
        
        # Fallback: try .env file via backend config
        from backend.config import settings
        base_url = settings.AIC_LLM_BASE_URL or ""
        api_key = settings.AIC_LLM_API_KEY or ""
        if base_url and api_key:
            base_url = base_url.rstrip("/")
            if not base_url.endswith("/v1"):
                base_url += "/v1"
            return base_url, api_key
        
        return None

    @staticmethod
    def _build_tools_schema() -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read contents of a file inside the workspace",
                    "parameters": {
                        "type": "object",
                        "properties": {"path": {"type": "string", "description": "Relative path in workspace"}},
                        "required": ["path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Write text content to a file inside the workspace",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Relative path in workspace"},
                            "content": {"type": "string", "description": "Text content to write"}
                        },
                        "required": ["path", "content"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_directory",
                    "description": "List files and folders in a workspace directory",
                    "parameters": {
                        "type": "object",
                        "properties": {"path": {"type": "string", "description": "Relative path in workspace", "default": "."}}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_workspace",
                    "description": "Search for a keyword across all files in the workspace",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string", "description": "Text to search for"}},
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "current_time",
                    "description": "Get current UTC date and time",
                    "parameters": {"type": "object", "properties": {}}
                }
            }
        ]

    @classmethod
    async def chat_completion(
        cls,
        db: AsyncSession,
        conversation_id: str,
        messages: List[Dict[str, Any]],
        provider_id: str | None,
        model_id: str | None,
        temperature: float = 0.4,
        top_p: float = 1.0,
        max_tokens: int | None = None,
        system_prompt: str | None = None
    ) -> Dict[str, Any]:
        start_time = time.time()
        config = await cls._get_provider_config(db, provider_id)
        
        # Graceful fallback when no provider is connected (desktop-first behavior)
        if not config or not model_id:
            content = "No AI provider configured. Please add a provider in Settings > Providers to start chatting."
            
            # create assistant message
            msg = Message(
                conversation_id=conversation_id,
                role="assistant",
                content=content,
                model_id=model_id,
                provider_id=provider_id,
                status="completed"
            )
            db.add(msg)
            await db.commit()
            await db.refresh(msg)
            
            # extract artifacts
            await artifact_service.extract_and_store(db, conversation_id, msg.id, content)
            
            # log generation
            log = GenerationLog(
                conversation_id=conversation_id,
                message_id=msg.id,
                provider_id=provider_id,
                model_id=model_id,
                latency_ms=int((time.time() - start_time) * 1000),
                status="completed",
                finish_reason="stop"
            )
            db.add(log)
            await db.commit()
            
            latency_ms = int((time.time() - start_time) * 1000)
            logger.info(json.dumps({
                "event": "chat_completion",
                "provider": provider_id,
                "model": model_id or "disconnected",
                "latency_ms": latency_ms,
                "token_count": 0,
                "status": "no_provider",
            }))
            return {"id": msg.id, "role": "assistant", "content": content, "status": "completed"}

        base_url, api_key = config
        url = f"{base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload: Dict[str, Any] = {
            "model": model_id,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "tools": cls._build_tools_schema()
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                # Inject system prompt from worker if not already present
                has_system = any(m.get("role") == "system" for m in messages)
                if system_prompt and not has_system:
                    messages = [{"role": "system", "content": system_prompt}] + messages
                    payload["messages"] = messages
                
                res = await client.post(url, headers=headers, json=payload)
                res.raise_for_status()
                data = res.json()
                
                choice = data.get("choices", [{}])[0]
                msg_data = choice.get("message", {})
                content = msg_data.get("content", "") or ""
                tool_calls = msg_data.get("tool_calls", [])
                finish_reason = choice.get("finish_reason", "stop")
                
                # handle tool calls if present
                if tool_calls:
                    for tc in tool_calls:
                        fn = tc.get("function", {})
                        t_name = fn.get("name")
                        try:
                            t_args = json.loads(fn.get("arguments", "{}"))
                        except Exception:
                            t_args = {}
                        
                        exec_res = await tool_dispatcher.execute(t_name, t_args)
                        content += f"\n\n[Tool Executed: {t_name}] -> {json.dumps(exec_res.get('result') or exec_res.get('error'))}"

                msg = Message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=content,
                    model_id=model_id,
                    provider_id=provider_id,
                    status="completed"
                )
                db.add(msg)
                await db.commit()
                await db.refresh(msg)
                
                await artifact_service.extract_and_store(db, conversation_id, msg.id, content)
                
                usage = data.get("usage", {})
                log = GenerationLog(
                    conversation_id=conversation_id,
                    message_id=msg.id,
                    provider_id=provider_id,
                    model_id=model_id,
                    latency_ms=int((time.time() - start_time) * 1000),
                    prompt_tokens=usage.get("prompt_tokens"),
                    completion_tokens=usage.get("completion_tokens"),
                    total_tokens=usage.get("total_tokens"),
                    status="completed",
                    finish_reason=finish_reason
                )
                db.add(log)
                await db.commit()
                
                # C7: Calculate cost based on token usage
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
                cost = (prompt_tokens * 0.000003 + completion_tokens * 0.000015)

                latency_ms = int((time.time() - start_time) * 1000)
                logger.info(json.dumps({
                    "event": "chat_completion",
                    "provider": provider_id,
                    "model": model_id,
                    "latency_ms": latency_ms,
                    "token_count": usage.get("total_tokens", 0),
                    "cost": round(cost, 6),
                    "status": "completed",
                }))
                return {"id": msg.id, "role": "assistant", "content": content, "status": "completed", "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, "total_tokens": usage.get("total_tokens", 0), "cost": round(cost, 6)}}
            except Exception as e:
                latency_ms = int((time.time() - start_time) * 1000)
                logger.error(json.dumps({
                    "event": "chat_completion_error",
                    "provider": provider_id,
                    "model": model_id,
                    "latency_ms": latency_ms,
                    "error": str(e),
                }))
                log = GenerationLog(
                    conversation_id=conversation_id,
                    provider_id=provider_id,
                    model_id=model_id,
                    latency_ms=int((time.time() - start_time) * 1000),
                    status="error",
                    error_message=str(e)
                )
                db.add(log)
                await db.commit()
                raise e

    @classmethod
    async def chat_stream(
        cls,
        db: AsyncSession,
        conversation_id: str,
        messages: List[Dict[str, Any]],
        provider_id: str | None,
        model_id: str | None,
        temperature: float = 0.4,
        top_p: float = 1.0,
        max_tokens: int | None = None,
        system_prompt: str | None = None
    ) -> AsyncGenerator[str, None]:
        start_time = time.time()
        config = await cls._get_provider_config(db, provider_id)
        
        # create initial streaming message in DB
        msg = Message(
            conversation_id=conversation_id,
            role="assistant",
            content="",
            model_id=model_id,
            provider_id=provider_id,
            status="streaming"
        )
        db.add(msg)
        await db.commit()
        await db.refresh(msg)
        
        yield f"data: {json.dumps({'type': 'start', 'message_id': msg.id})}\n\n"

        if not config:
            error_msg = "No AI provider configured. Please add a provider in Settings > Providers to start chatting."
            msg.content = error_msg
            yield f"data: {json.dumps({'type': 'chunk', 'content': error_msg})}\n\n"
            
            msg.status = "completed"
            await db.commit()
            await artifact_service.extract_and_store(db, conversation_id, msg.id, msg.content)
            yield f"data: {json.dumps({'type': 'done', 'message_id': msg.id})}\n\n"
            return

        # Auto-detect model if not provided
        if not model_id:
            if provider_id:
                res = await db.execute(
                    select(ProviderModel.model_id).where(ProviderModel.provider_id == provider_id).limit(1)
                )
                row = res.scalars().first()
                model_id = row
            if not model_id:
                # Fallback: try .env via backend config
                from backend.config import settings
                model_id = settings.AIC_MODEL_CRAFTER or settings.AIC_MODEL_SPRINTER or "gpt-4o"

        base_url, api_key = config
        url = f"{base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        
        # WP-01: Build context before LLM call
        user_query = messages[-1].get("content", "") if messages else ""
        context_str = ""
        try:
            context_str = await build_chat_context(db, conversation_id, user_query)
            if context_str:
                logger.info(f"Context injected: {len(context_str)} chars")
        except Exception as ctx_err:
            logger.warning(f"Context build failed (proceeding without): {ctx_err}")
        
        # Inject context into messages if available
        if context_str:
            context_msg = {"role": "system", "content": f"Relevant context:\n{context_str}"}
            messages = [context_msg] + messages
        
        payload: Dict[str, Any] = {
            "model": model_id,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "stream": True
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        try:
            has_system = any(m.get("role") == "system" for m in messages)
            if system_prompt and not has_system:
                messages = [{"role": "system", "content": system_prompt}] + messages
                payload["messages"] = messages
            
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream("POST", url, headers=headers, json=payload) as res:
                    res.raise_for_status()
                    async for line in res.aiter_lines():
                        if line.startswith("data: "):
                            data_str = line[6:].strip()
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk_json = json.loads(data_str)
                                delta = chunk_json.get("choices", [{}])[0].get("delta", {})
                                chunk_content = delta.get("content", "")
                                if chunk_content:
                                    msg.content += chunk_content
                                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk_content})}\n\n"
                            except Exception:
                                pass

            msg.status = "completed"
            await db.commit()
            await artifact_service.extract_and_store(db, conversation_id, msg.id, msg.content)
            
            # C7: Estimate cost for streaming (based on content length)
            estimated_completion_tokens = len(msg.content) // 4
            estimated_prompt_tokens = sum(len(m.get("content", "")) // 4 for m in messages)
            cost = (estimated_prompt_tokens * 0.000003 + estimated_completion_tokens * 0.000015)

            # WP-02: Auto-store conversation in memory
            try:
                from backend.services.memory_service import memory_service
                await memory_service.store(
                    db,
                    scope="conversation",
                    key=f"conv:{conversation_id}:last",
                    value={
                        "user_message": user_query,
                        "assistant_response": msg.content[:500],
                        "model": model_id,
                        "provider": provider_id,
                    },
                    scope_id=conversation_id,
                    category="context",
                    importance=0.6,
                )
            except Exception as mem_err:
                logger.warning(f"Memory store failed (non-critical): {mem_err}")
            
            yield f"data: {json.dumps({'type': 'cost', 'cost': round(cost, 6), 'estimated_tokens': estimated_completion_tokens})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'message_id': msg.id})}\n\n"

        except Exception as e:
            msg.status = "error"
            await db.commit()
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

chat_service = ChatService()
