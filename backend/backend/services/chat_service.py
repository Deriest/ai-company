import time
import json
import logging
import httpx
from typing import AsyncGenerator, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.models.schema import Provider, ProviderModel
from storage.models import Message
from backend.models.ai_runtime import GenerationLog
from backend.services.crypto import decrypt as decrypt_api_key
from backend.services.tool_dispatcher import tool_dispatcher
from backend.services.content_utils import content_to_text
from backend.services.artifact_service import artifact_service

logger = logging.getLogger(__name__)


# PERF-FIX: fully static tool schema — built once at module import instead of
# re-constructing the dict chain on every chat_completion call.
_TOOLS_SCHEMA: list[dict] = [
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


def _invalidate_context_cache(conversation_id: str) -> None:
    """Drop cached context assembly for a conversation (new message = stale context)."""
    try:
        from context.cache import get_context_cache
        get_context_cache().invalidate_conversation(conversation_id)
    except Exception:
        pass


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
        def _usable_key(provider: Provider | None) -> str:
            """QA-2440: Return the decrypted API key only if the provider is usable."""
            if not provider or not provider.enabled:
                return ""
            if not (provider.api_key or "").strip():
                return ""
            return (decrypt_api_key(provider.api_key) or "").strip()

        p = None
        api_key = ""
        if provider_id:
            res = await db.execute(select(Provider).where(Provider.id == provider_id))
            candidate = res.scalars().first()
            api_key = _usable_key(candidate)
            if api_key:
                p = candidate

        if p is None:
            # QA-2440 FIX: Auto-detect must skip stale providers with empty or
            # undecryptable keys. Previously this grabbed the FIRST enabled row
            # with no ordering — stale rows (empty api_key) won the pick,
            # decrypt() returned "", and httpx raised
            # "Illegal header value b'Bearer '". Prefer connected providers,
            # then most recently refreshed.
            res = await db.execute(
                select(Provider)
                .where(Provider.enabled == True)
                .order_by(
                    (Provider.status == "connected").desc(),
                    Provider.last_refresh_at.desc(),
                )
            )
            for candidate in res.scalars().all():
                api_key = _usable_key(candidate)
                if api_key:
                    p = candidate
                    break

        if p is not None:
            base_url = p.base_url.rstrip("/")
            if not base_url.endswith("/v1"):
                base_url += "/v1"
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
        """Return the static tool schema (module-level constant — no per-call rebuild)."""
        return _TOOLS_SCHEMA

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
        
        # Persist user message
        user_content = content_to_text(messages[-1].get("content", "")) if messages else ""
        if user_content:
            user_msg = Message(
                conversation_id=conversation_id,
                role="user",
                content=user_content,
                status="completed",
            )
            db.add(user_msg)
            await db.commit()
            # New message → cached context assembly for this conversation is stale.
            _invalidate_context_cache(conversation_id)

        # BUG-FIX: model auto-selection — same chain as chat_stream()
        # (env → provider_models → worker_runtime). chat_completion() is called
        # with (None, None) by POST /chat/regenerate, which previously
        # short-circuited to "No AI provider configured" even when an enabled
        # provider existed.
        if not model_id:
            from backend.config import settings
            env_model = (
                settings.AIC_MODEL_CRAFTER
                or settings.AIC_MODEL_THINKER
                or settings.AIC_MODEL_SPRINTER
            )
            if env_model:
                model_id = env_model
                # Prefer the env provider's base_url/api_key — an env model
                # must not be sent to an auto-detected DB provider's endpoint.
                env_base_url = settings.AIC_LLM_BASE_URL or ""
                env_api_key = settings.AIC_LLM_API_KEY or ""
                if env_base_url and env_api_key:
                    env_base_url = env_base_url.rstrip("/")
                    if not env_base_url.endswith("/v1"):
                        env_base_url += "/v1"
                    config = (env_base_url, env_api_key)
            else:
                # Auto-detect provider if none given
                if not provider_id:
                    prov_res = await db.execute(select(Provider).where(Provider.enabled == True).limit(1))
                    auto_prov = prov_res.scalars().first()
                    if auto_prov:
                        provider_id = auto_prov.id

                if provider_id:
                    # Try to find a valid model from the provider's model list
                    res = await db.execute(
                        select(ProviderModel.model_id).where(ProviderModel.provider_id == provider_id)
                    )
                    all_models = res.scalars().all()
                    if all_models:
                        excluded_prefixes = ("combo/", "IAMHC/")
                        excluded_substrings = ("free", "big-pickle", "deepseek", "r1")
                        valid_models = [
                            m for m in all_models
                            if not m.startswith(excluded_prefixes)
                            and not any(s in m.lower() for s in excluded_substrings)
                        ]
                        if not valid_models:
                            valid_models = [m for m in all_models if not m.startswith("combo/")]
                        if valid_models:
                            model_id = valid_models[0]

            if not model_id:
                from backend.models.schema import WorkerRuntime
                wr_result = await db.execute(
                    select(WorkerRuntime).where(WorkerRuntime.is_enabled == True).limit(1)
                )
                worker_runtime = wr_result.scalars().first()
                if worker_runtime and worker_runtime.model_id:
                    model_id = worker_runtime.model_id
                    if not provider_id and worker_runtime.provider_id:
                        provider_id = worker_runtime.provider_id

            # Re-fetch config with the (possibly auto-detected) provider.
            if provider_id:
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

        # BUG-02 FIX: Use provider.chat() instead of direct httpx to handle SSE
        from llm.provider import provider_manager, LLMProvider, ProviderConfig, ModelTier

        # PERF-FIX: reuse the cached provider_manager instance (one httpx client
        # per provider) instead of building a new LLMProvider per request. Fall
        # back to a per-request provider only when the requested model_id or
        # endpoint isn't served by the active provider (explicit worker override).
        def _urls_match(a: str, b: str) -> bool:
            def _norm(u: str) -> str:
                u = (u or "").strip().rstrip("/")
                if u.endswith("/v1"):
                    u = u[:-3]
                return u
            return _norm(a) == _norm(b)

        provider = provider_manager.get_active_with_key()
        _owns_provider = False
        if (
            provider is None
            or not _urls_match(provider.config.base_url, base_url)
            or provider.config.get_model(ModelTier.CRAFTER) != model_id
        ):
            provider_config = ProviderConfig(
                name="chat_service_provider",
                base_url=base_url,
                api_key=api_key,
                models={"crafter": model_id, "thinker": model_id, "sprinter": model_id}
            )
            provider = LLMProvider(provider_config)
            _owns_provider = True
        
        try:
            # Inject system prompt from worker if not already present
            has_system = any(m.get("role") == "system" for m in messages)
            if system_prompt and not has_system:
                messages = [{"role": "system", "content": system_prompt}] + messages
                payload["messages"] = messages
            
            # QA-249-R6: History already flattened by provider.chat() internally
            # Use provider.chat() which handles SSE properly
            result = await provider.chat(
                messages=messages,
                tier=ModelTier.CRAFTER,
                temperature=temperature,
                max_tokens=max_tokens,
                purpose="chat_completion"
            )
            
            content = result.get("content", "")
            data = result.get("raw", {})
            
            choice = data.get("choices", [{}])[0]
            msg_data = choice.get("message", {})
            content = msg_data.get("content", "") or content  # Use result content as fallback
            tool_calls = msg_data.get("tool_calls", [])
            finish_reason = choice.get("finish_reason", "stop")
            
            # FITUR 2: Taste checker — scan for AI-isms and rewrite if needed
            try:
                from backend.services.taste_checker import has_ai_slop, scan_summary, REWRITE_PROMPT
                if has_ai_slop(content, threshold=1):
                    taste_meta = scan_summary(content)
                    logger.info(f"Chat taste checker: {taste_meta['total_findings']} findings (high={taste_meta['high']})")
                    
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
                                purpose="taste_rewrite"
                            )
                            rewritten = rewrite_result.get("content", "").strip()
                            if rewritten and len(rewritten) > 10:
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

            usage = data.get("usage", {})
            # PERF-FIX: set token_count up front and combine the assistant
            # message + generation log into a single commit (fewer round-trips).
            msg = Message(
                conversation_id=conversation_id,
                role="assistant",
                content=content,
                model_id=model_id,
                provider_id=provider_id,
                status="completed",
                token_count=usage.get("total_tokens", 0),
            )
            db.add(msg)
            await db.commit()
            await db.refresh(msg)

            await artifact_service.extract_and_store(db, conversation_id, msg.id, content)

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
        finally:
            # Only close a per-request provider we created; the manager's
            # cached provider must stay alive for other requests.
            if _owns_provider:
                try:
                    await provider.close()
                except Exception:
                    pass

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
        
        # Persist user message from the last message in the payload
        user_query = content_to_text(messages[-1].get("content", "")) if messages else ""
        if user_query:
            user_msg = Message(
                conversation_id=conversation_id,
                role="user",
                content=user_query,
                status="completed",
            )
            db.add(user_msg)
            await db.commit()
            # FIX: index the user message so /conversations/search finds chat
            # content (REST routes already index; the streaming path did not).
            try:
                from backend.services.search_service import index_message_fts
                await index_message_fts(db, user_msg.id, conversation_id, user_query)
            except Exception as fts_err:
                logger.warning(f"FTS indexing failed for user message (non-critical): {fts_err}")
            # New message → cached context assembly for this conversation is stale.
            _invalidate_context_cache(conversation_id)
        
        # create initial streaming message in DB
        msg = Message(
            conversation_id=conversation_id,
            role="assistant",
            content="",
            model_id=model_id,
            provider_id=provider_id,
            status="streaming",
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

        # BUG-03 FIX: Use configured model from WorkerRuntime, not hardcoded fallback
        if not model_id:
            # QA-E2E FIX: The user's explicit engine config (set in Settings >
            # Providers → written to AIC_MODEL_* env) must take priority over
            # auto-picking from provider_models — the first "valid" model in the
            # list may have no active credentials on the endpoint (404).
            from backend.config import settings
            env_model = (
                settings.AIC_MODEL_CRAFTER
                or settings.AIC_MODEL_THINKER
                or settings.AIC_MODEL_SPRINTER
            )
            if env_model:
                model_id = env_model
                # QA-FIX: the env model must be paired with the env provider's
                # base_url/api_key — otherwise an env model gets sent to an
                # auto-detected DB provider's endpoint (404).
                env_base_url = settings.AIC_LLM_BASE_URL or ""
                env_api_key = settings.AIC_LLM_API_KEY or ""
                if env_base_url and env_api_key:
                    env_base_url = env_base_url.rstrip("/")
                    if not env_base_url.endswith("/v1"):
                        env_base_url += "/v1"
                    config = (env_base_url, env_api_key)
            else:
                # BUG-14 FIX: Resolve provider_id first so we can look up ProviderModel
                if not provider_id:
                    # Auto-detect: find first enabled provider's ID
                    prov_res = await db.execute(select(Provider).where(Provider.enabled == True).limit(1))
                    auto_prov = prov_res.scalars().first()
                    if auto_prov:
                        provider_id = auto_prov.id

                if provider_id:
                    # Try to find a valid model from the provider's model list
                    res = await db.execute(
                        select(ProviderModel.model_id).where(ProviderModel.provider_id == provider_id)
                    )
                    all_models = res.scalars().all()
                    if all_models:
                        # Filter out combo/bad models, pick first valid one
                        excluded_prefixes = ("combo/", "IAMHC/")
                        excluded_substrings = ("free", "big-pickle", "deepseek", "r1")
                        valid_models = [
                            m for m in all_models
                            if not m.startswith(excluded_prefixes)
                            and not any(s in m.lower() for s in excluded_substrings)
                        ]
                        if not valid_models:
                            valid_models = [m for m in all_models if not m.startswith("combo/")]
                        if valid_models:
                            model_id = valid_models[0]
            
            # If still no model, try to get from worker_runtime configuration
            if not model_id:
                from backend.models.schema import WorkerRuntime
                wr_result = await db.execute(
                    select(WorkerRuntime).where(WorkerRuntime.is_enabled == True).limit(1)
                )
                worker_runtime = wr_result.scalars().first()
                if worker_runtime and worker_runtime.model_id:
                    model_id = worker_runtime.model_id
                    if not provider_id and worker_runtime.provider_id:
                        provider_id = worker_runtime.provider_id
                        # Re-fetch config with correct provider
                        config = await cls._get_provider_config(db, provider_id)
                        if config:
                            base_url, api_key = config
                            url = f"{base_url}/chat/completions"
                            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            
            # Only use env fallback if absolutely no configuration exists
            # AND no DB provider is active — mixing an env model (e.g.
            # AIC_MODEL_CRAFTER) with a DB provider's base_url would send a
            # model that does not exist on that provider → confusing 404/400.
            if not model_id:
                if provider_id:
                    error_msg = "No model configured for this provider. Select a model in Settings > Providers."
                    msg.content = error_msg
                    yield f"data: {json.dumps({'type': 'error', 'error': error_msg})}\n\n"
                    msg.status = "error"
                    await db.commit()
                    return
                from backend.config import settings
                model_id = settings.AIC_MODEL_CRAFTER or settings.AIC_MODEL_SPRINTER
                if not model_id:
                    error_msg = "No model configured. Please configure a model in Settings > Live Company."
                    msg.content = error_msg
                    yield f"data: {json.dumps({'type': 'error', 'error': error_msg})}\n\n"
                    msg.status = "error"
                    await db.commit()
                    return

        if not config:
            error_msg = "No provider configuration found."
            msg.content = error_msg
            yield f"data: {json.dumps({'type': 'error', 'error': error_msg})}\n\n"
            msg.status = "error"
            await db.commit()
            return
            
        base_url, api_key = config
        url = f"{base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        
        # WP-01: Build context before LLM call
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
        
        # BUG-05 FIX + QA-249-R4: Apply token budget to prevent context overflow
        from backend.services.context_builder import get_context_policy, get_model_context_window, get_context_policy_for_window
        from backend.services.context_overflow import estimate_tokens
        
        # Get the appropriate context policy based on model capabilities
        policy = get_context_policy("crafter")  # Default policy (60k tokens)
        metadata_available = False
        
        if provider_id and model_id:
            try:
                context_window = await get_model_context_window(db, provider_id, model_id)
                if context_window:
                    policy = get_context_policy_for_window(context_window)
                    metadata_available = True
                    logger.info(f"Using context policy for window {context_window}: max_tokens={policy.max_tokens}")
                else:
                    logger.warning(f"Model {model_id} context_window not found in DB, using conservative fallback (60k tokens). Run fetch-models to auto-detect.")
                    yield f"data: {json.dumps({'type': 'warning', 'message': f'Context window unknown for model {model_id}, using conservative policy (60k tokens). Run fetch-models to update.'})}\n\n"
            except Exception as e:
                logger.warning(f"Failed to get model context window, using default policy: {e}")
                yield f"data: {json.dumps({'type': 'warning', 'message': 'Unable to determine model capacity, using conservative limit (60k tokens)'})}\n\n"
        
        # Inject system prompt if needed
        has_system = any(m.get("role") == "system" for m in messages)
        if system_prompt and not has_system:
            messages = [{"role": "system", "content": system_prompt}] + messages
        
        # Estimate tokens
        estimated = estimate_tokens(messages)
        
        # QA-249-R5: Removed hard_limit guard at 90% — only truncate at actual max_tokens
        # Old logic rejected 160k conversations that were still valid within 183k limit
        
        # QA-249-R5 FIX: Only truncate if exceeds policy.max_tokens (hard ceiling), not 90%
        # Previously truncated at 90% (148k) which broke valid 160k conversations
        if policy.max_tokens > 0 and estimated > policy.max_tokens:
            logger.warning(f"Message history exceeds max_tokens: {estimated} > {policy.max_tokens}, truncating...")
            # Keep system messages, drop oldest user/assistant messages
            system_messages = [m for m in messages if m.get("role") == "system"]
            other_messages = [m for m in messages if m.get("role") != "system"]
            
            # Truncate from the beginning (oldest messages) until under policy.max_tokens
            while estimate_tokens(system_messages + other_messages) > policy.max_tokens and len(other_messages) > 1:
                other_messages.pop(0)
            
            messages = system_messages + other_messages
            new_estimated = estimate_tokens(messages)
            logger.info(f"Truncated to {len(messages)} messages, estimated {new_estimated} tokens")
            
            # Verify after truncate
            if new_estimated > policy.max_tokens:
                error_msg = f"Cannot truncate context below limit ({new_estimated:,} > {policy.max_tokens:,} tokens). Start a new session."
                logger.error(error_msg)
                yield f"data: {json.dumps({'type': 'error', 'error': error_msg})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                return
            
            yield f"data: {json.dumps({'type': 'warning', 'message': f'Context truncated: {estimated:,} → {new_estimated:,} tokens'})}\n\n"
        
        # QA-249-R6: Flatten history before sending to upstream (workaround VansRouter bug)
        from llm.provider import _flatten_history
        messages = _flatten_history(messages)
        
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
            # PERF-FIX: stream chunks live to the frontend as they arrive
            # (no full-response buffering). Content is accumulated in a list
            # and joined once (avoids O(n²) string concat).
            content_parts: list[str] = []
            stream_usage = None

            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream("POST", url, headers=headers, json=payload) as res:
                    # QA-249-R5: Handle upstream 400 CONTENT_LENGTH_EXCEEDS_THRESHOLD
                    if res.status_code == 400:
                        try:
                            error_body = await res.aread()
                            error_json = json.loads(error_body)
                            error_reason = error_json.get("reason", "")
                            error_message = error_json.get("message", "")

                            # Check if it's a content length threshold error from upstream
                            if "CONTENT_LENGTH_EXCEEDS_THRESHOLD" in error_reason or \
                               "exceeds threshold" in error_message.lower() or \
                               "content length" in error_message.lower():
                                friendly_msg = "Context terlalu besar untuk model ini. Mulai sesi baru atau minta ringkasan."
                                logger.error(f"Upstream content length error: estimated={estimated}, model={model_id}, reason={error_reason}")
                                msg.status = "error"
                                msg.content = friendly_msg
                                await db.commit()
                                yield f"data: {json.dumps({'type': 'error', 'error': friendly_msg})}\n\n"
                                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                                return
                        except Exception:
                            pass  # Fall through to generic error handling

                    res.raise_for_status()

                    async for line in res.aiter_lines():
                        if line.startswith("data: "):
                            data_str = line[6:].strip()
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk_json = json.loads(data_str)
                                # Capture usage from the last chunk (some providers send it mid-stream)
                                if chunk_json.get("usage"):
                                    stream_usage = chunk_json["usage"]
                                delta = chunk_json.get("choices", [{}])[0].get("delta", {})
                                chunk_content = delta.get("content", "")
                                if chunk_content:
                                    content_parts.append(chunk_content)
                                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk_content})}\n\n"
                            except Exception:
                                pass

            raw_content = "".join(content_parts)
            msg.content = raw_content

            # Taste check + rewrite AFTER streaming. The already-streamed chunks
            # stay visible; when a cleaner rewrite is produced, emit a `rewrite`
            # SSE event (renderer dispatches it to onRewrite) and persist the
            # rewritten text so the next reload shows the clean version.
            try:
                from backend.services.taste_checker import has_ai_slop, scan_summary, REWRITE_PROMPT
                if raw_content and has_ai_slop(raw_content, threshold=1):
                    taste_meta = scan_summary(raw_content)
                    logger.info(f"Stream taste checker: {taste_meta['total_findings']} findings (high={taste_meta['high']})")
                    if taste_meta["high"] > 0:
                        try:
                            from llm.provider import provider_manager, ModelTier
                            rewrite_result = await provider_manager.chat(
                                messages=[
                                    {"role": "system", "content": "You are a text editor. Rewrite the given text to remove AI patterns. Keep the meaning and tone. Do NOT add explanations, just output the rewritten text."},
                                    {"role": "user", "content": REWRITE_PROMPT + raw_content},
                                ],
                                tier=ModelTier.SPRINTER,
                                temperature=0.3,
                                max_tokens=len(raw_content) + 200,
                                purpose="taste_rewrite",
                            )
                            rewritten = (rewrite_result.get("content", "") or "").strip()
                            if rewritten and len(rewritten) > 10:
                                from backend.services.taste_checker import has_ai_slop as check_again
                                if not check_again(rewritten, threshold=1):
                                    logger.info("Stream taste rewrite successful — cleaner output")
                                    msg.content = rewritten
                                    yield f"data: {json.dumps({'type': 'rewrite', 'content': rewritten})}\n\n"
                                else:
                                    logger.info("Stream taste rewrite still has AI-isms — using original")
                            else:
                                logger.debug("Stream taste rewrite returned empty — using original")
                        except Exception as rewrite_err:
                            logger.debug(f"Stream taste rewrite failed (non-critical): {rewrite_err}")
            except Exception as taste_err:
                logger.debug(f"Stream taste checker exception (non-critical): {taste_err}")

            msg.status = "completed"
            # Store token_count from upstream usage if available, otherwise estimate
            if stream_usage and stream_usage.get("total_tokens"):
                msg.token_count = stream_usage["total_tokens"]
            else:
                # Estimate: ~4 chars per token for content + messages
                msg.token_count = len(msg.content) // 4 + sum(len(m.get("content", "")) // 4 for m in messages)
            await db.commit()
            # FIX: index the finalized assistant message so /conversations/search
            # finds streaming chat content (REST routes already index).
            try:
                from backend.services.search_service import index_message_fts
                await index_message_fts(db, msg.id, conversation_id, msg.content or "")
            except Exception as fts_err:
                logger.warning(f"FTS indexing failed for assistant message (non-critical): {fts_err}")
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

        except httpx.HTTPStatusError as e:
            # QA-249-R5: Catch HTTPStatusError for 400 responses not caught above
            if e.response.status_code == 400:
                try:
                    error_json = e.response.json()
                    error_reason = error_json.get("reason", "")
                    error_message = error_json.get("message", "")
                    
                    if "CONTENT_LENGTH_EXCEEDS_THRESHOLD" in error_reason or \
                       "exceeds threshold" in error_message.lower() or \
                       "content length" in error_message.lower():
                        friendly_msg = "Context terlalu besar untuk model ini. Mulai sesi baru atau minta ringkasan."
                        logger.error(f"Upstream content length error (HTTPStatusError): estimated={estimated}, model={model_id}")
                        msg.status = "error"
                        msg.content = friendly_msg
                        await db.commit()
                        yield f"data: {json.dumps({'type': 'error', 'error': friendly_msg})}\n\n"
                        yield f"data: {json.dumps({'type': 'done'})}\n\n"
                        return
                except Exception:
                    pass
            
            # Generic HTTP error
            msg.status = "error"
            await db.commit()
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
        except Exception as e:
            # QA-249-R5: Check if exception message contains threshold indicators
            error_str = str(e).lower()
            if "content_length_exceeds_threshold" in error_str or \
               "exceeds threshold" in error_str or \
               ("content length" in error_str and "exceed" in error_str):
                friendly_msg = "Context terlalu besar untuk model ini. Mulai sesi baru atau minta ringkasan."
                logger.error(f"Upstream content length error (Exception): estimated={estimated}, model={model_id}, error={e}")
                msg.status = "error"
                msg.content = friendly_msg
                await db.commit()
                yield f"data: {json.dumps({'type': 'error', 'error': friendly_msg})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                return
            
            msg.status = "error"
            await db.commit()
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

chat_service = ChatService()
