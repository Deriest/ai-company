"""AIC Platform — LLM Provider Abstraction.

Supports any OpenAI-compatible API:
- OpenAI (api.openai.com)
- OpenRouter (openrouter.ai)
- Local models (vLLM, LM Studio, Ollama, etc.)
- Custom gateways (9router, vansrouter, AMRouter)

Model routing by tier:
- thinker: complex reasoning (planning, architecture)
- crafter: implementation (coding, writing)
- sprinter: fast tasks (review, status)
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
import json
import logging
import os

import httpx

from runtime.adaptive import AdaptiveRuntimeProfile, adaptive_runtime, capabilities_from_metadata

logger = logging.getLogger("aic.llm")


class ModelTier(str, Enum):
    THINKER = "thinker"
    CRAFTER = "crafter"
    SPRINTER = "sprinter"


# Worker fallback chains — only within the thinker/crafter/sprinter group.
# If the assigned model for a worker errors, retry with the next worker's
# model in the chain. Never falls back to tiers the user did not assign.
#   thinker  error -> crafter  -> sprinter
#   crafter  error -> thinker  -> sprinter
#   sprinter error -> crafter  -> thinker
_WORKER_FALLBACK_CHAINS: dict[str, list["ModelTier"]] = {
    ModelTier.THINKER.value: [ModelTier.THINKER, ModelTier.CRAFTER, ModelTier.SPRINTER],
    ModelTier.CRAFTER.value: [ModelTier.CRAFTER, ModelTier.THINKER, ModelTier.SPRINTER],
    ModelTier.SPRINTER.value: [ModelTier.SPRINTER, ModelTier.CRAFTER, ModelTier.THINKER],
}


def _worker_fallback_chain(tier: "ModelTier | str") -> list["ModelTier"]:
    """Return the ordered tier fallback chain for a worker tier.

    Tiers outside the thinker/crafter/sprinter group (or unknown values)
    resolve to a single-element chain so they never cross-cover.
    """
    t_str = tier.value if isinstance(tier, ModelTier) else str(tier)
    chain = _WORKER_FALLBACK_CHAINS.get(t_str)
    if chain is not None:
        return list(chain)
    # Unknown/non-worker tier — try only what was requested.
    try:
        return [ModelTier(t_str)]
    except ValueError:
        return [ModelTier.CRAFTER]


@dataclass
class ProviderConfig:
    """Configuration for an LLM provider."""
    name: str = "default"
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    models: dict[str, str] = field(default_factory=lambda: {
        ModelTier.THINKER.value: "gpt-4o",
        ModelTier.CRAFTER.value: "gpt-4o-mini",
        ModelTier.SPRINTER.value: "gpt-4o-mini",
    })
    timeout: int = 120
    max_retries: int = 4
    fallback_provider: str | None = None

    def get_model(self, tier: ModelTier | str) -> str:
        t = tier.value if isinstance(tier, ModelTier) else str(tier)
        return self.models.get(t, self.models.get(ModelTier.CRAFTER.value, "gpt-4o-mini"))


@dataclass
class UsageRecord:
    """Token usage record for tracking."""
    provider: str
    model: str
    tier: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_estimate: float = 0.0
    timestamp: str = ""
    purpose: str = ""  # conversation, planner, coding, review, etc.

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        self.total_tokens = self.prompt_tokens + self.completion_tokens


class UsageTracker:
    """Tracks LLM token usage."""
    def __init__(self):
        self._records: list[UsageRecord] = []
        self._lock = None

    def record(self, record: UsageRecord) -> None:
        self._records.append(record)
        if len(self._records) > 10000:
            self._records = self._records[-5000:]
        logger.info(f"LLM usage: {record.provider}/{record.model} "
                     f"tokens={record.total_tokens} purpose={record.purpose}")
        # Persist to DB (fire-and-forget)
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._persist(record))
        except RuntimeError:
            pass  # No event loop — skip persistence

    async def _persist(self, record: UsageRecord) -> None:
        """Persist usage record to database."""
        try:
            from storage.database import async_session
            from storage.models import LLMUsageLog
            async with async_session() as session:
                session.add(LLMUsageLog(
                    provider=record.provider,
                    model=record.model,
                    tier=record.tier,
                    purpose=record.purpose,
                    prompt_tokens=record.prompt_tokens,
                    completion_tokens=record.completion_tokens,
                    total_tokens=record.total_tokens,
                    cost_estimate=record.cost_estimate,
                ))
                await session.commit()
        except Exception as e:
            logger.debug(f"Failed to persist LLM usage: {e}")

    def summary(self, since: datetime | None = None) -> dict:
        records = self._records
        if since:
            records = [r for r in records if r.timestamp >= since.isoformat()]

        total_tokens = sum(r.total_tokens for r in records)
        by_provider: dict[str, int] = {}
        by_purpose: dict[str, int] = {}
        by_model: dict[str, int] = {}

        for r in records:
            by_provider[r.provider] = by_provider.get(r.provider, 0) + r.total_tokens
            by_purpose[r.purpose] = by_purpose.get(r.purpose, 0) + r.total_tokens
            by_model[r.model] = by_model.get(r.model, 0) + r.total_tokens

        return {
            "total_requests": len(records),
            "total_tokens": total_tokens,
            "by_provider": by_provider,
            "by_purpose": by_purpose,
            "by_model": by_model,
        }

    def recent(self, limit: int = 50) -> list[dict]:
        return [
            {
                "provider": r.provider,
                "model": r.model,
                "tier": r.tier,
                "prompt_tokens": r.prompt_tokens,
                "completion_tokens": r.completion_tokens,
                "total_tokens": r.total_tokens,
                "purpose": r.purpose,
                "timestamp": r.timestamp,
            }
            for r in self._records[-limit:]
        ]


# Singleton
usage_tracker = UsageTracker()


class LLMProvider:
    """OpenAI-compatible LLM provider with fallback support."""

    def _init_profiles(self):
        """Seed adaptive profiles for configured models using conservative defaults."""
        for tier, model in self.config.models.items():
            cap = capabilities_from_metadata(self.config.name, model, None)
            adaptive_runtime.register(cap)

    def __init__(self, config: ProviderConfig):
        self.config = config
        self._init_profiles()
        headers = {"Content-Type": "application/json"}
        if config.api_key:
            headers["Authorization"] = f"Bearer {config.api_key}"
        self.client = httpx.AsyncClient(
            base_url=config.base_url.rstrip("/"),
            headers=headers,
            timeout=config.timeout,
        )

    async def chat(
        self,
        messages: list[dict[str, str]],
        tier: ModelTier | str = ModelTier.CRAFTER,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        purpose: str = "conversation",
        **kwargs,
    ) -> dict:
        """Send a chat completion request.

        Returns dict with:
        - content: str (the response text)
        - model: str (model used)
        - usage: dict (token counts)
        - raw: dict (full response)
        """
        model = self.config.get_model(tier)
        tier_str = tier.value if isinstance(tier, ModelTier) else str(tier)

        # QA-249-R6: Flatten history to workaround VansRouter multi-turn bug
        messages = _flatten_history(messages)

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            **kwargs,
        }
        # Suppress thinking output for reasoning models (FREE, DeepSeek-R1, etc.)
        if "free" in model.lower() or "deepseek" in model.lower() or "r1" in model.lower():
            payload["reasoning_effort"] = "low" 
        if max_tokens:
            payload["max_tokens"] = max_tokens

        last_error = None
        for attempt in range(self.config.max_retries + 1):
            try:
                resp = await self.client.post("/chat/completions", json=payload)
                resp.raise_for_status()
                text = (resp.text or "").strip()
                if not text:
                    raise LLMError(
                        f"Empty LLM response body from {model} "
                        f"at {self.config.base_url}/chat/completions "
                        f"(HTTP {resp.status_code})"
                    )
                data = None
                try:
                    data = resp.json()
                except Exception:
                    pass
                if data is None:
                    # Providers like VansRouter always return SSE even for
                    # non-streaming requests.  Parse leading `data: {...}` lines.
                    import json as _json
                    import re as _re
                    sse_lines = _re.findall(r'^data:\s*(.*)', text, _re.MULTILINE)
                    if sse_lines:
                        merged = []
                        for line in sse_lines:
                            stripped = line.strip()
                            if stripped and stripped != "[DONE]":
                                try:
                                    parsed = _json.loads(stripped)
                                    merged.append(parsed)
                                except _json.JSONDecodeError:
                                    pass
                        if merged:
                            # Merge choices from multiple SSE chunks.
                            # SSE chunks use "delta" instead of "message" —
                            # convert to "message" for the non-streaming parser.
                            full_content = ""
                            usage = {}
                            # Track tool_calls by index and merge across chunks
                            tool_calls_map: dict[int, dict] = {}
                            for m in merged:
                                if m.get("usage"):
                                    usage = m["usage"]
                                ch = m.get("choices", [])
                                if ch:
                                    delta = ch[0].get("delta", {})
                                    if delta.get("content"):
                                        full_content += delta["content"]
                                    # Merge tool_calls deltas by index
                                    if delta.get("tool_calls"):
                                        for tc_delta in delta["tool_calls"]:
                                            idx = tc_delta.get("index", 0)
                                            if idx not in tool_calls_map:
                                                tool_calls_map[idx] = {
                                                    "index": idx,
                                                    "id": tc_delta.get("id", ""),
                                                    "type": "function",
                                                    "function": {
                                                        "name": tc_delta.get("function", {}).get("name", ""),
                                                        "arguments": tc_delta.get("function", {}).get("arguments", ""),
                                                    },
                                                }
                                            else:
                                                # Concatenate function.name and function.arguments
                                                existing = tool_calls_map[idx]
                                                fn_delta = tc_delta.get("function", {})
                                                if fn_delta.get("name"):
                                                    existing["function"]["name"] += fn_delta["name"]
                                                if fn_delta.get("arguments"):
                                                    existing["function"]["arguments"] += fn_delta["arguments"]
                                                if tc_delta.get("id"):
                                                    existing["id"] = tc_delta["id"]
                            
                            # Build message with content and tool_calls (if any)
                            message = {"content": full_content, "role": "assistant"}
                            if tool_calls_map:
                                # Sort by index to preserve order
                                message["tool_calls"] = [tool_calls_map[k] for k in sorted(tool_calls_map.keys())]
                            
                            data = {
                                "choices": [{"message": message}],
                                "usage": usage,
                            }
                    if data is None:
                        # Prefer first complete JSON object; tolerate leading noise
                        start = text.find("{")
                        if start < 0:
                            raise LLMError(
                                f"Non-JSON LLM response from {model} "
                                f"at {self.config.base_url}: {text[:120]!r}"
                            )
                        brace = 0
                        end = 0
                        for i, ch in enumerate(text[start:], start):
                            if ch == "{":
                                brace += 1
                            elif ch == "}":
                                brace -= 1
                                if brace == 0:
                                    end = i + 1
                                    break
                        if end <= start:
                            raise LLMError(
                                f"Incomplete JSON LLM response from {model}: {text[:120]!r}"
                            )
                        data = _json.loads(text[start:end])

                choices = data.get("choices") if isinstance(data, dict) else None
                if not choices:
                    raise LLMError(
                        f"LLM response missing choices from {model} "
                        f"at {self.config.base_url} (HTTP {resp.status_code}). "
                        f"Raw keys: {list(data.keys()) if isinstance(data, dict) else 'not-a-dict'}"
                    )
                msg = choices[0].get("message") or {}
                content = msg.get("content") or ""
                # OpenRouter / VansRouter may put answer in reasoning or content
                reasoning = msg.get("reasoning_content") or msg.get("reasoning") or ""

                # Strip thinking tags from content (DeepSeek R1 style)
                if content:
                    import re as _re
                    for tag in ("thinking", "thought", "reason"):
                        content = _re.sub(
                            rf'<{tag}>.*?</{tag}>', '', content, flags=_re.DOTALL
                        ).strip()
                        content = _re.sub(
                            rf'<𝑎𝑛𝑡𝑚𝑙:{tag}>.*?</𝑎𝑛𝑡𝑚𝑙:{tag}>', '', content, flags=_re.DOTALL
                        ).strip()
                    # FREE/reasoning models sometimes dump "Thinking.\n ..." without tags
                    if content.startswith("Thinking."):
                        # Find end of thinking block — look for actual response after double newline
                        parts = content.split("\n\n", 1)
                        if len(parts) > 1 and len(parts[0]) > 50:
                            content = parts[1].strip()

                # If content looks like raw reasoning (no actual answer), try reasoning_content
                # Reasoning models often dump process into content and answer into reasoning_content
                if reasoning and not content:
                    content = reasoning
                elif reasoning and content:
                    # Check if content is just thinking dump (heuristic: >500 chars and no punctuation at end)
                    if len(content) > 500 and not content.rstrip().endswith(('.', '!', '?', '"', '}', ']')):
                        content = reasoning  # Use reasoning_content as the actual answer

                # Try other fields as last resort
                if not content:
                    for field in ("text", "output", "response"):
                        if msg.get(field):
                            content = msg[field]
                            break
                if not content:
                    logger.warning(
                        f"LLM empty content. Model={model} URL={self.config.base_url} "
                        f"Keys: {list(msg.keys())}"
                    )
                usage = data.get("usage", {})

                # Track usage
                record = UsageRecord(
                    provider=self.config.name,
                    model=model,
                    tier=tier_str,
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                    purpose=purpose,
                )
                usage_tracker.record(record)

                return {
                    "content": content,
                    "model": model,
                    "usage": usage,
                    "raw": data,
                }

            except httpx.HTTPStatusError as e:
                last_error = e
                logger.warning(
                    f"LLM HTTP error (attempt {attempt+1}): "
                    f"{e.response.status_code} for {model} "
                    f"at {self.config.base_url}: {e.response.text[:200]}"
                )
                if e.response.status_code in (429, 502, 503, 504):
                    # Rate limit / proxy busy / 502 ResourceExhausted — wait with exponential backoff
                    import asyncio
                    await asyncio.sleep(3 * (2 ** attempt))
                elif e.response.status_code >= 500:
                    import asyncio
                    await asyncio.sleep(2)
                else:
                    # Client error — don't retry
                    break
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                last_error = e
                logger.warning(f"LLM connection error (attempt {attempt+1}): {e}")
                import asyncio
                await asyncio.sleep(1)

        # All retries failed
        if last_error:
            logger.error(f"LLM request failed after {self.config.max_retries + 1} attempts: {last_error}")
            raise LLMError(f"LLM request failed: {last_error}") from last_error

        raise LLMError("LLM request failed for unknown reason")

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        tier: ModelTier | str = ModelTier.CRAFTER,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        purpose: str = "conversation",
        **kwargs,
    ):
        """Stream LLM response token by token.

        Yields dicts with:
        - type: 'chunk' | 'error' | 'done'
        - content: str (for chunk)
        - error: str (for error)
        - model: str (for done)
        - usage: dict (for done)
        """
        model = self.config.get_model(tier)
        tier_str = tier.value if isinstance(tier, ModelTier) else str(tier)

        # QA-249-R6: Flatten history to workaround VansRouter multi-turn bug
        messages = _flatten_history(messages)

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
            **kwargs,
        }
        if "free" in model.lower() or "deepseek" in model.lower() or "r1" in model.lower():
            payload["reasoning_effort"] = "low"
        if max_tokens:
            payload["max_tokens"] = max_tokens

        try:
            async with self.client.stream("POST", "/chat/completions", json=payload) as resp:
                resp.raise_for_status()
                buffer = ""
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            choices = data.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield {"type": "chunk", "content": content}
                                # Forward tool_calls deltas for streaming tool use
                                if delta.get("tool_calls"):
                                    yield {"type": "tool_calls", "tool_calls": delta["tool_calls"]}
                        except json.JSONDecodeError:
                            continue

                # Track usage on completion
                record = UsageRecord(
                    provider=self.config.name,
                    model=model,
                    tier=tier_str,
                    purpose=purpose,
                )
                usage_tracker.record(record)
                yield {"type": "done", "model": model, "usage": {}}

        except httpx.HTTPStatusError as e:
            logger.warning(f"LLM stream HTTP error: {e.response.status_code}")
            yield {"type": "error", "error": f"HTTP {e.response.status_code}: {e.response.text[:200]}"}
        except Exception as e:
            logger.warning(f"LLM stream error: {e}")
            # Fallback: call chat() and chunk the response
            try:
                result = await self.chat(messages=messages, tier=tier, temperature=temperature,
                                        max_tokens=max_tokens, purpose=purpose, **kwargs)
                content = result.get("content", "")
                for i in range(0, len(content), 20):
                    yield {"type": "chunk", "content": content[i:i+20]}
                yield {"type": "done", "model": result.get("model", model), "usage": result.get("usage", {})}
            except Exception as fallback_err:
                yield {"type": "error", "error": str(fallback_err)}

    async def list_models(self) -> list[dict]:
        """List available models from the provider.

        Handles URL normalization: if base_url ends with /v1, requests /models.
        If not, tries /v1/models then /models.
        Raises LLMError on network/auth failures so callers can surface diagnostics.
        """
        try:
            # Try /models first (base_url should include /v1)
            resp = await self.client.get("/models")
            if resp.status_code == 404:
                # base_url might not include /v1 — try /v1/models
                resp = await self.client.get("/v1/models")
            resp.raise_for_status()
            data = resp.json()
            # OpenAI format: {"data": [...]}
            # Ollama format: {"models": [...]}
            # Raw list: [...]
            models = data.get("data", data.get("models", data if isinstance(data, list) else []))
            if not isinstance(models, list):
                models = []
            # Normalize: ensure each model has an "id" field and capabilities
            normalized = []
            for m in models:
                if isinstance(m, str):
                    normalized.append({"id": m, "owned_by": ""})
                elif isinstance(m, dict):
                    mid = m.get("id") or m.get("name") or m.get("model") or ""
                    if mid:
                        normalized.append({
                            "id": mid, 
                            "owned_by": m.get("owned_by", ""),
                            "capabilities": m, # retain raw payload for capability extraction
                        })
            # Deduplicate by id
            seen = set()
            deduped = []
            for m in normalized:
                if m["id"] not in seen:
                    seen.add(m["id"])
                    # Seed adaptive profile from discovered metadata
                    cap = capabilities_from_metadata(self.config.name, m["id"], m.get("capabilities", {}), source="provider_discovery")
                    adaptive_runtime.register(cap)
                    deduped.append(m)
            return deduped
        except Exception as e:
            logger.warning(f"Failed to list models: {e}")
            raise LLMError(f"Failed to list models: {e}") from e

    async def close(self):
        await self.client.aclose()


class LLMError(Exception):
    pass


def _flatten_history(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    """Flatten multi-turn history into 2 messages (system + user) to workaround VansRouter bug.
    
    VansRouter returns empty response (200, len=0) for multi-turn conversations with large messages.
    This function compresses all history into a single system message containing the conversation,
    plus the final user question as a separate user message.
    
    Args:
        messages: List of message dicts with 'role' and 'content'
    
    Returns:
        Flattened list: [system(history), user(last_question)] if >2 messages, else unchanged
    """
    if len(messages) <= 2:
        return messages
    
    # Separate system, history, and last user message
    system_messages = [m for m in messages if m.get("role") == "system"]
    other_messages = [m for m in messages if m.get("role") != "system"]
    
    if not other_messages:
        return messages
    
    # Last message should be user question
    last_message = other_messages[-1]
    history_messages = other_messages[:-1]
    
    # Build compressed system message with full conversation history
    history_parts = []
    
    # Add original system prompts first
    for sys_msg in system_messages:
        history_parts.append(sys_msg.get("content", ""))
    
    # Add conversation history
    if history_messages:
        history_parts.append("\n## Conversation History\n")
        for i, msg in enumerate(history_messages):
            role = msg.get("role", "user")
            content = msg.get("content", "")
            history_parts.append(f"{role}: {content}\n")
    
    # Combine into single system message
    compressed_system = "\n".join(history_parts).strip()
    
    # Return: [system(full_history), user(current_question)]
    return [
        {"role": "system", "content": compressed_system},
        {"role": "user", "content": last_message.get("content", "")},
    ]


# ── Provider Manager ───────────────────────────────────

class ProviderManager:
    """Manages multiple LLM providers with fallback."""

    def __init__(self):
        self._providers: dict[str, LLMProvider] = {}
        self._configs: dict[str, ProviderConfig] = {}
        self._active: str | None = None

    def register(self, config: ProviderConfig) -> None:
        """Register or update a provider."""
        # Close existing provider if updating
        if config.name in self._providers:
            # Can't await here — caller should call aregister for async
            self._providers.pop(config.name, None)

        self._configs[config.name] = config
        self._providers[config.name] = LLMProvider(config)

        if not self._active:
            self._active = config.name

        logger.info(f"Registered LLM provider: {config.name} ({config.base_url})")

    async def aregister(self, config: ProviderConfig) -> None:
        """Async register — closes existing provider properly."""
        if config.name in self._providers:
            await self._providers[config.name].close()

        self._configs[config.name] = config
        self._providers[config.name] = LLMProvider(config)

        if not self._active:
            self._active = config.name

        logger.info(f"Registered LLM provider: {config.name} ({config.base_url})")

    def set_active(self, name: str) -> None:
        if name not in self._configs:
            raise LLMError(f"Unknown provider: {name}")
        self._active = name
        logger.info(f"Active LLM provider: {name}")

    def get_active(self) -> LLMProvider | None:
        if not self._active:
            return None
        return self._providers.get(self._active)

    def get_active_with_key(self) -> LLMProvider | None:
        """QA-2441: Return a provider with a usable (non-empty) API key.

        get_active() returns the FIRST registered provider (e.g. an
        env-configured router registered at startup before the DB providers),
        which may have an empty api_key — producing
        "Illegal header value b'Bearer '" downstream.
        Prefer the active provider when its key is usable; otherwise return
        the first registered provider with a non-empty key.
        """
        active = self.get_active()
        if active is not None and (active.config.api_key or "").strip():
            return active
        for name, provider in self._providers.items():
            if name == self._active:
                continue
            if (provider.config.api_key or "").strip():
                logger.info(
                    f"Active provider '{self._active}' has no usable API key — "
                    f"using '{name}' instead"
                )
                return provider
        return None

    def get_active_profile(self, tier: ModelTier | str = ModelTier.CRAFTER) -> "AdaptiveRuntimeProfile | None":
        """Get the adaptive runtime profile for the active provider and requested tier."""
        from runtime.adaptive import adaptive_runtime
        provider = self.get_active()
        if not provider:
            return None
        model = provider.config.get_model(tier)
        return adaptive_runtime.get(provider.config.name, model)

    def get_provider(self, name: str) -> LLMProvider | None:
        return self._providers.get(name)

    def list_providers(self) -> list[dict]:
        return [
            {
                "name": name,
                "base_url": cfg.base_url,
                "models": cfg.models,
                "is_active": name == self._active,
                "fallback": cfg.fallback_provider,
            }
            for name, cfg in self._configs.items()
        ]

    async def chat(self, messages: list[dict], tier: ModelTier | str = ModelTier.CRAFTER, **kwargs) -> dict:
        """Chat using active provider with smart worker fallback routing.

        Fallback chains (only within the thinker/crafter/sprinter worker group):
          thinker  error -> crafter  -> sprinter
          crafter  error -> thinker  -> sprinter
          sprinter error -> crafter  -> thinker
        """
        provider = self.get_active()
        if not provider:
            raise LLMError("No LLM provider configured")

        # Determine fallback chain of tiers
        tiers_to_try = _worker_fallback_chain(tier)

        last_error = None
        for t in tiers_to_try:
            try:
                return await provider.chat(messages, tier=t, **kwargs)
            except LLMError as e:
                last_error = e
                logger.warning(f"Tier {t} failed on provider '{provider.config.name}': {e}. Retrying with next tier in chain.")

        # Fallback to secondary provider if configured
        if self._active:
            cfg = self._configs.get(self._active)
            if cfg and cfg.fallback_provider:
                fallback = self._providers.get(cfg.fallback_provider)
                if fallback:
                    logger.warning(f"Falling back to provider '{cfg.fallback_provider}'")
                    for t in tiers_to_try:
                        try:
                            return await fallback.chat(messages, tier=t, **kwargs)
                        except LLMError as e:
                            last_error = e

        if last_error:
            raise last_error
        raise LLMError("LLM request failed across all routing attempts")

    async def chat_stream(self, messages: list[dict], tier: ModelTier | str = ModelTier.CRAFTER, **kwargs):
        """Stream LLM response using active provider with smart worker fallback.

        Fallback chains (only within the thinker/crafter/sprinter worker group):
          thinker  error -> crafter  -> sprinter
          crafter  error -> thinker  -> sprinter
          sprinter error -> crafter  -> thinker
        """
        provider = self.get_active()
        if not provider:
            yield {"type": "error", "error": "No LLM provider configured"}
            return

        tiers_to_try = _worker_fallback_chain(tier)

        for t in tiers_to_try:
            has_error = False
            async for chunk in provider.chat_stream(messages, tier=t, **kwargs):
                if chunk.get("type") == "error":
                    has_error = True
                    logger.warning(f"Stream tier {t} failed: {chunk.get('error')}")
                    break
                yield chunk
            if not has_error:
                return

        # Fallback to secondary provider
        if self._active:
            cfg = self._configs.get(self._active)
            if cfg and cfg.fallback_provider:
                fallback = self._providers.get(cfg.fallback_provider)
                if fallback:
                    logger.warning(f"Stream falling back to provider '{cfg.fallback_provider}'")
                    async for chunk in fallback.chat_stream(messages, tier=tiers_to_try[0], **kwargs):
                        yield chunk
                    return

        yield {"type": "error", "error": "LLM stream failed across all routing attempts"}

    async def close_all(self):
        for provider in self._providers.values():
            await provider.close()


# Singleton
provider_manager = ProviderManager()


def init_provider_from_env() -> ProviderConfig | None:
    """Initialize provider from environment variables."""
    base_url = os.environ.get("AIC_LLM_BASE_URL", "")
    api_key = os.environ.get("AIC_LLM_API_KEY", "")
    thinker = os.environ.get("AIC_MODEL_THINKER", "")
    crafter = os.environ.get("AIC_MODEL_CRAFTER", "")
    sprinter = os.environ.get("AIC_MODEL_SPRINTER", "")

    if not base_url:
        return None

    models = {}
    if thinker:
        models[ModelTier.THINKER.value] = thinker
    if crafter:
        models[ModelTier.CRAFTER.value] = crafter
    if sprinter:
        models[ModelTier.SPRINTER.value] = sprinter

    if not models:
        models = {
            ModelTier.THINKER.value: "kc/nvidia/nemotron-3-ultra-550b-a55b:free",
            ModelTier.CRAFTER.value: "kc/poolside/laguna-s-2.1:free",
            ModelTier.SPRINTER.value: "kc/poolside/laguna-xs-2.1:free",
        }

    return ProviderConfig(
        name=os.environ.get("AIC_LLM_PROVIDER_NAME", "default"),
        base_url=base_url,
        api_key=api_key,
        models=models,
    )
