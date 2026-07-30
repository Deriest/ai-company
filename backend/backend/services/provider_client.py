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

def infer_capabilities(model_id: str, raw_meta: dict) -> dict:
    id_lower = model_id.lower()
    is_claude = any(x in id_lower for x in ["claude", "opus", "sonnet", "haiku"])
    is_gpt = any(x in id_lower for x in ["gpt", "o1", "o3"])
    is_ds = "deepseek" in id_lower
    is_qwen = "qwen" in id_lower
    is_gemini = "gemini" in id_lower
    is_small = any(x in id_lower for x in ["mini", "3b", "haiku", "flash"])
    is_reason = any(x in id_lower for x in ["opus", "o3", "reasoner", "r1"])

    context_window = raw_meta.get("context_length", raw_meta.get("context_window", None))
    if not context_window:
        if is_claude and "opus" in id_lower: context_window = 200000
        elif is_claude: context_window = 200000
        elif is_gpt and "4.1" in id_lower: context_window = 1000000
        elif is_gpt: context_window = 128000
        elif is_gemini: context_window = 1000000
        elif is_ds: context_window = 64000
        elif is_small: context_window = 32000
        else: context_window = 8192

    return {
        "context_window": context_window,
        "supports_vision": is_claude or is_gpt or is_gemini or "vision" in id_lower or "4o" in id_lower,
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
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=httpx.Timeout(10.0, read=30.0)
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
                except:
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
