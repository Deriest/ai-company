import httpx
import time
import json
import logging
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

class ProviderAPIError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Provider API Error {status_code}: {message}")

class ProviderConnectionError(Exception):
    pass

class ProviderTimeoutError(Exception):
    pass


_MODELS_DEV_CACHE: dict | None = None


def _load_models_dev() -> dict:
    """Lazy-load the bundled models.dev database (universal, gateway-agnostic).

    File: backend/data/models_dev.json (~3.5MB, 176 providers).
    Falls back to {} if missing/corrupt so detection still works via pattern layer.
    """
    global _MODELS_DEV_CACHE
    if _MODELS_DEV_CACHE is not None:
        return _MODELS_DEV_CACHE
    import os
    candidates = [
        os.path.join(os.path.dirname(__file__), "..", "..", "data", "models_dev.json"),
        os.path.join(os.path.dirname(__file__), "..", "data", "models_dev.json"),
        os.path.join(os.getcwd(), "data", "models_dev.json"),
    ]
    for path in candidates:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                _MODELS_DEV_CACHE = data if data else {}
                logger.info(f"Loaded models.dev database ({len(_MODELS_DEV_CACHE)} providers) from {path}")
                return _MODELS_DEV_CACHE
        except FileNotFoundError:
            continue
        except Exception as e:
            logger.warning(f"Failed to load models.dev from {path}: {e}")
    _MODELS_DEV_CACHE = {}
    return _MODELS_DEV_CACHE


def _lookup_models_dev(model_id: str) -> int | None:
    """Lookup context window in the bundled models.dev database.

    Strips the vendor prefix (e.g. 'ag/claude-sonnet-4-6' -> 'claude-sonnet-4-6'),
    then searches all providers for an exact match. Returns None if not found
    so the caller falls through to the pattern layer.
    """
    try:
        dev = _load_models_dev()
        if not dev:
            return None
        base = model_id.split("/")[-1] if "/" in model_id else model_id
        base_dot = base.replace("-", ".")
        for provider, info in dev.items():
            models = info.get("models", {}) if isinstance(info, dict) else {}
            if not models:
                continue
            if base in models:
                return models[base].get("limit", {}).get("context")
            if base_dot in models:
                return models[base_dot].get("limit", {}).get("context")
        return None
    except Exception as e:
        logger.warning(f"models.dev lookup failed for {model_id}: {e}")
        return None


def _iter_nested_dicts(obj: dict | list, depth: int = 0, max_depth: int = 5) -> dict:
    """Recursively flatten nested dict/list structures into a flat dict.
    
    Used to find context window values buried in nested metadata structures
    from various provider endpoints (vLLM, LM Studio, Ollama-compat, etc).
    """
    if depth > max_depth:
        return {}
    
    result = {}
    
    if isinstance(obj, dict):
        for key, value in obj.items():
            result[key] = value
            if isinstance(value, (dict, list)):
                nested = _iter_nested_dicts(value, depth + 1, max_depth)
                result.update(nested)
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, (dict, list)):
                nested = _iter_nested_dicts(item, depth + 1, max_depth)
                result.update(nested)
    
    return result


def _probe_context_from_metadata(raw_meta: dict) -> int | None:
    """Probe context window from raw model metadata.
    
    Many OpenAI-compatible servers expose context window in their /models endpoint:
    - vLLM: max_model_len
    - LM Studio: context_length, max_context_length
    - LiteLLM: max_tokens (context, not output)
    - Ollama-compat: context_window, contextWindow
    - Standard: capabilities.contextWindow, limit.context
    
    Returns None if no context found, allowing waterfall to continue.
    """
    if not raw_meta or not isinstance(raw_meta, dict):
        return None
    
    # Flatten nested structures to find context keys at any level
    flat = _iter_nested_dicts(raw_meta)
    
    # Priority-ordered list of context keys (most specific first)
    context_keys = [
        "context_window",
        "contextWindow", 
        "context_length",
        "max_context_length",
        "max_model_len",
        "model_length",
    ]
    
    for key in context_keys:
        if key in flat:
            val = flat[key]
            if isinstance(val, int) and val > 0:
                logger.debug(f"Probed context from metadata key '{key}': {val}")
                return val
    
    # Check for max_tokens but be careful - could be output limit, not context
    # Only trust if it's reasonably large (> 32K suggests context, not output)
    if "max_tokens" in flat:
        val = flat["max_tokens"]
        if isinstance(val, int) and val > 32000:
            logger.debug(f"Probed context from metadata key 'max_tokens': {val}")
            return val
    
    return None

def infer_capabilities(model_id: str, raw_meta: dict) -> dict:
    """Infer model capabilities including context window using waterfall detection.
    
    Context window waterfall (implemented here for probe layer, others in fetch_models):
    1. Probe endpoint (this function via _probe_context_from_metadata)
    2. models.dev lookup (fallback for unknown models)
    3. Hardcoded catalog (imported from model_catalog)
    4. Pattern family (model-family knowledge)
    5. Fallback 256K (changed from 8192 to match Hermes)
    
    Note: User override and persistent cache are handled at the database layer,
    not here. This function focuses on probe + waterfall for fresh detections.
    """
    id_lower = model_id.lower()
    is_claude = any(x in id_lower for x in ["claude", "opus", "sonnet", "haiku"])
    is_gpt = any(x in id_lower for x in ["gpt", "o1", "o3"])
    is_ds = "deepseek" in id_lower
    is_qwen = "qwen" in id_lower
    is_gemini = "gemini" in id_lower
    is_small = any(x in id_lower for x in ["mini", "3b", "haiku", "flash"])
    is_reason = any(x in id_lower for x in ["opus", "o3", "reasoner", "r1"])

    # ── Vision capability ──
    # Multimodal by family (claude / gpt / gemini are natively multimodal), plus
    # unambiguous vision name markers. Conservative by design: plain code models
    # (deepseek-coder, qwen3-coder, gpt-oss, llama-3.x) stay off unless they hit
    # a family flag above. o4 and qwen-vl use word-boundary regexes so bare "vl"
    # / "o4" substrings in unrelated ids do not false-positive.
    import re as _re
    _supports_vision = (
        is_claude or is_gpt or is_gemini
        or "vision" in id_lower
        or "4o" in id_lower               # gpt-4o family
        or "llava" in id_lower
        or "pixtral" in id_lower
        or "llama-4" in id_lower          # llama-4 family is natively multimodal
        or "image" in id_lower
        or bool(_re.search(r"\bo4\b|\bvl\b|\bvlm\b", id_lower))  # o4 / qwen-vl / vlm
    )

    context_window = None
    context_source = "probe"
    
    # ── Layer 1: Probe endpoint metadata (highest priority) ──
    probed = _probe_context_from_metadata(raw_meta)
    if probed:
        context_window = probed
        context_source = "probe"
        logger.info(f"Context for {model_id}: {context_window} (source: probe)")
    
    # ── Layer 2: Hardcoded catalog (verified production values) ──
    # Catalog wins over models.dev: models.dev is community-maintained and can
    # under/over-report (e.g. qwen3-coder-next 262K on models.dev vs 1M verified,
    # gpt-5.6 1.05M on models.dev vs 400K at some gateways). The catalog mirrors
    # verified production values, so it is the more trustworthy static source.
    if not context_window:
        from backend.services.model_catalog import lookup_catalog
        catalog_ctx = lookup_catalog(model_id)
        if catalog_ctx:
            context_window = catalog_ctx
            context_source = "catalog"
            logger.info(f"Context for {model_id}: {context_window} (source: catalog)")

    # ── Layer 3: models.dev universal database (176 providers) ──
    # Only consulted when the catalog has no entry (unknown/custom model).
    if not context_window:
        dev_ctx = _lookup_models_dev(model_id)
        if dev_ctx:
            context_window = dev_ctx
            context_source = "models_dev"
            logger.info(f"Context for {model_id}: {context_window} (source: models.dev)")

    # ── Layer 4: Generic family pattern (model-family knowledge) ──
    if not context_window:
        import re as _re
        norm_id = _re.sub(r"(\d)-(\d)", r"\1.\2", id_lower)

        if "claude" in norm_id and ("opus-4.6" in norm_id or "opus-4.7" in norm_id or "opus-4.8" in norm_id or "sonnet-4.6" in norm_id or "sonnet-4.7" in norm_id or "sonnet-5" in norm_id or "fable" in norm_id or "mythos" in norm_id):
            context_window = 1000000
        elif is_claude: context_window = 200000
        elif is_gemini: context_window = 1048576
        elif "gpt-5" in norm_id: context_window = 400000
        elif "gpt-4.1" in norm_id: context_window = 1000000
        elif "gpt-4o" in norm_id or "gpt-4-turbo" in norm_id: context_window = 128000
        elif "gpt-4" in norm_id or "gpt-oss" in norm_id: context_window = 128000
        elif "o1" in norm_id or "o3" in norm_id or "o4" in norm_id: context_window = 200000
        elif "grok-4.5" in norm_id: context_window = 500000
        elif "grok" in norm_id: context_window = 256000
        elif "qwen" in norm_id and ("coder" in norm_id or "max" in norm_id or "3.5" in norm_id or "3.6" in norm_id or "3.7" in norm_id or "plus" in norm_id or "omni" in norm_id or "next" in norm_id):
            context_window = 1000000
        elif "qwen" in norm_id and ("vl" in norm_id or "235b" in norm_id): context_window = 262144
        elif "qwen" in norm_id: context_window = 262144
        elif "qwq" in norm_id: context_window = 131072
        elif "kimi" in norm_id and "k3" in norm_id: context_window = 1048576
        elif "kimi" in norm_id: context_window = 262144
        elif "glm" in norm_id: context_window = 200000
        elif "deepseek" in norm_id and "v4" in norm_id: context_window = 1000000
        elif "deepseek" in norm_id: context_window = 128000
        elif "minimax-m3" in norm_id: context_window = 1048576
        elif "minimax" in norm_id: context_window = 200000
        elif "mimo" in norm_id and ("v2.5" in norm_id or "auto" in norm_id): context_window = 1048576
        elif "mimo" in norm_id: context_window = 262144
        elif "muse" in norm_id: context_window = 200000
        elif "auto" in norm_id and len(norm_id) <= 12: context_window = 200000
        elif "llama-4" in norm_id: context_window = 1000000
        elif "llama" in norm_id: context_window = 128000
        elif "codestral" in norm_id: context_window = 256000
        elif "mistral" in norm_id: context_window = 128000
        elif "command" in norm_id: context_window = 128000
        elif "sonar" in norm_id or "pplx" in norm_id or "perplexity" in norm_id: context_window = 128000
        elif "hunyuan" in norm_id or norm_id.startswith("hy3"): context_window = 262144
        elif "step-" in norm_id: context_window = 128000
        elif "nemotron" in norm_id: context_window = 128000
        elif "ling-" in norm_id: context_window = 128000
        elif is_small: context_window = 32000
        
        if context_window:
            context_source = "pattern"
            logger.info(f"Context for {model_id}: {context_window} (source: pattern)")
    
    # ── Layer 5: Fallback 256K (changed from 8192 to match Hermes) ──
    if not context_window:
        context_window = 256000
        context_source = "fallback"
        logger.info(f"Context for {model_id}: {context_window} (source: fallback)")

    return {
        "context_window": context_window,
        "context_source": context_source,
        "supports_vision": _supports_vision,
        "supports_tool_calling": "embed" not in id_lower,
        "supports_streaming": True,
        "supports_json_mode": is_gpt or is_ds or is_qwen or is_claude,
        "supports_reasoning": is_reason or is_claude or "think" in id_lower,
        "supports_function_calling": "embed" not in id_lower and not is_small,
        "supports_embeddings": "embed" in id_lower,
        "max_output_tokens": raw_meta.get("max_output_tokens") or (4096 if is_small else 32768 if is_reason else 16384)
    }

class ProviderClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        # SSRF hardening: never follow redirects on provider requests. A hostile
        # or misconfigured endpoint could otherwise redirect us to a loopback /
        # private / metadata address after validation has already passed. httpx
        # defaults to not following redirects, but we pin it explicitly so the
        # property is guaranteed regardless of httpx version changes.
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=httpx.Timeout(10.0, read=30.0),
            follow_redirects=False,
        )

    async def close(self):
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        return False

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.RequestError, ProviderTimeoutError)),
        reraise=True
    )
    async def _request(self, method: str, endpoint: str, **kwargs):
        start = time.perf_counter()
        try:
            response = await self.client.request(method, endpoint, **kwargs)
            latency_ms = int((time.perf_counter() - start) * 1000)
            logger.info(json.dumps({
                "event": "provider_request",
                "method": method,
                "endpoint": endpoint,
                "status_code": response.status_code,
                "latency_ms": latency_ms,
            }))

            # Extract detailed error message from response if available
            error_detail = ""
            if not response.is_success:
                try:
                    err_json = response.json()
                    error_detail = str(err_json.get("error", err_json.get("message", err_json)))
                except (ValueError, KeyError):
                    error_detail = response.text[:200]

            if response.status_code == 401:
                raise ProviderAPIError(401, f"Invalid API Key: {error_detail}" if error_detail else "Invalid API Key")
            elif response.status_code == 403:
                raise ProviderAPIError(403, f"Permission Denied: {error_detail}" if error_detail else "Permission Denied")
            elif response.status_code == 404:
                raise ProviderAPIError(404, "Endpoint Not Found")
            elif response.status_code == 429:
                raise ProviderAPIError(429, f"Rate Limited: {error_detail}" if error_detail else "Rate Limited")
            elif response.status_code >= 500:
                raise ProviderAPIError(response.status_code, f"Provider Internal Error: {error_detail}" if error_detail else "Provider Internal Error")
            response.raise_for_status()
            return response
        except httpx.TimeoutException as e:
            latency_ms = int((time.perf_counter() - start) * 1000)
            logger.error(json.dumps({
                "event": "provider_timeout",
                "method": method,
                "endpoint": endpoint,
                "latency_ms": latency_ms,
                "error": str(e),
            }))
            raise ProviderTimeoutError(f"Connection timeout: {str(e)}")
        except httpx.RequestError as e:
            latency_ms = int((time.perf_counter() - start) * 1000)
            logger.error(json.dumps({
                "event": "provider_connection_error",
                "method": method,
                "endpoint": endpoint,
                "latency_ms": latency_ms,
                "error": str(e),
            }))
            raise ProviderConnectionError(f"Network error: {str(e)}")

    async def fetch_models(self) -> tuple[list[dict], int]:
        start = time.perf_counter()
        try:
            response = await self._request("GET", "/models")
        except ProviderAPIError as e:
            if e.status_code == 404:
                response = await self._request("GET", "/v1/models")
            else:
                raise
        latency_ms = int((time.perf_counter() - start) * 1000)
        data = response.json()
        
        models = data.get("data", [])
        if not isinstance(models, list):
            # Try some non-standard wrappers
            if isinstance(data, list):
                models = data
            elif isinstance(data, dict) and "models" in data:
                models = data["models"]
            else:
                models = []
                
        normalized = []
        for m in models:
            if not isinstance(m, dict):
                continue
            model_id = str(m.get("id", ""))
            if not model_id:
                continue
                
            caps = infer_capabilities(model_id, m)
            
            normalized.append({
                "model_id": model_id,
                "display_name": m.get("name", m.get("display_name", model_id)),
                "owned_by": str(m.get("owned_by", "")),
                "raw_metadata": m,
                **caps
            })
            
        logger.info(json.dumps({
            "event": "fetch_models",
            "latency_ms": latency_ms,
            "model_count": len(normalized),
        }))
        return normalized, latency_ms

    async def test_connection(self) -> dict:
        models, latency_ms = await self.fetch_models()
        return {
            "status": "connected",
            "latency_ms": latency_ms,
            "model_count": len(models),
            "version": "openai-compatible/v1",
        }
