import pytest
from unittest.mock import AsyncMock, MagicMock
from llm.provider import LLMProvider, ProviderConfig, LLMError

@pytest.mark.asyncio
async def test_list_models_normalization_and_deduplication():
    config = ProviderConfig(name="test", base_url="http://test/v1", api_key="key")
    provider = LLMProvider(config)
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": [
            {"id": "gpt-4", "owned_by": "openai"},
            {"id": "gpt-4", "owned_by": "openai"},
            {"name": "claude-3", "owned_by": "anthropic"},
            "raw-model-name"
        ]
    }
    provider.client.get = AsyncMock(return_value=mock_resp)

    models = await provider.list_models()
    assert len(models) == 3
    assert models[0]["id"] == "gpt-4"
    assert models[0]["owned_by"] == "openai"
    assert models[1]["id"] == "claude-3"
    assert models[1]["owned_by"] == "anthropic"
    assert models[2]["id"] == "raw-model-name"
    assert models[2]["owned_by"] == ""

@pytest.mark.asyncio
async def test_list_models_fallback_v1():
    config = ProviderConfig(name="test", base_url="http://test", api_key="key")
    provider = LLMProvider(config)
    
    mock_resp_404 = MagicMock()
    mock_resp_404.status_code = 404
    
    mock_resp_200 = MagicMock()
    mock_resp_200.status_code = 200
    mock_resp_200.json.return_value = {"models": [{"id": "ollama-model"}]}
    
    async def mock_get(url):
        if url == "/models":
            return mock_resp_404
        return mock_resp_200

    provider.client.get = AsyncMock(side_effect=mock_get)

    models = await provider.list_models()
    assert len(models) == 1
    assert models[0]["id"] == "ollama-model"
