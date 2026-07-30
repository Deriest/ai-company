"""Provider routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete
from typing import List
from datetime import datetime

from backend.database.session import get_db
from backend.models.schema import Provider, ProviderModel
from backend.schemas.api_models_v2 import (
    ProviderCreate, ProviderUpdate, ProviderWithModelsResponse,
    ProviderTestResponse, ModelInfo, ModelCapabilities,
)
from backend.services.crypto import encrypt, decrypt
from backend.services.provider_client import ProviderClient, ProviderAPIError, ProviderConnectionError, ProviderTimeoutError

router = APIRouter()


def _to_provider_response(p: Provider, models: List[ProviderModel] = None) -> ProviderWithModelsResponse:
    if models is None:
        models = []

    model_infos = []
    for m in models:
        model_infos.append(ModelInfo(
            id=m.model_id,
            name=m.display_name,
            capabilities=ModelCapabilities(
                contextWindow=m.context_window or 8192,
                vision=m.supports_vision,
                toolCalling=m.supports_tool_calling,
                streaming=m.supports_streaming,
                reasoning=m.supports_reasoning,
                functionCalling=m.supports_function_calling,
                jsonMode=m.supports_json_mode,
                embedding=m.supports_embeddings,
                maxOutputTokens=m.max_output_tokens or 4096
            )
        ))

    return ProviderWithModelsResponse(
        id=p.id,
        name=p.name,
        endpoint=p.base_url,
        apiKey="***" if p.api_key else "",
        enabled=p.enabled,
        status=p.status,
        latencyMs=p.latency_ms or 0,
        version="1.0",
        healthNotes=["chat.completions"] if p.status == "connected" else [],
        models=model_infos,
        modelsCachedAt=p.last_refresh_at.isoformat() if p.last_refresh_at else None,
        lastRefreshAt=p.last_refresh_at.isoformat() if p.last_refresh_at else None,
    )


@router.get("/health")
async def health_check():
    llm_configured = False
    try:
        from llm.provider import provider_manager
        llm_configured = bool(getattr(provider_manager, "_providers", {}))
    except Exception:
        pass
    return {"status": "healthy", "version": "2.4.0A", "service": "AIC-ADE Backend", "llm_configured": llm_configured}


@router.get("/providers", response_model=List[ProviderWithModelsResponse])
async def list_providers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Provider))
    providers = result.scalars().all()

    responses = []
    for p in providers:
        m_result = await db.execute(select(ProviderModel).where(ProviderModel.provider_id == p.id))
        models = m_result.scalars().all()
        responses.append(_to_provider_response(p, models))

    return responses


@router.post("/providers", response_model=ProviderWithModelsResponse)
async def create_provider(provider: ProviderCreate, db: AsyncSession = Depends(get_db)):
    new_provider = Provider(
        name=provider.name,
        base_url=provider.endpoint,
        api_key=encrypt(provider.apiKey),
        enabled=True,
        status="disconnected",
        latency_ms=0
    )
    db.add(new_provider)
    await db.commit()
    await db.refresh(new_provider)
    return _to_provider_response(new_provider)


@router.patch("/providers/{id}", response_model=ProviderWithModelsResponse)
async def update_provider(id: str, update: ProviderUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Provider).where(Provider.id == id))
    provider = result.scalars().first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    if update.name is not None: provider.name = update.name
    if update.endpoint is not None: provider.base_url = update.endpoint
    if update.apiKey is not None and update.apiKey != "***":
        provider.api_key = encrypt(update.apiKey)
    if update.enabled is not None:
        provider.enabled = update.enabled
        if not provider.enabled:
            provider.status = "disabled"
        elif provider.status == "disabled":
            provider.status = "disconnected"

    if update.status is not None: provider.status = update.status
    if update.latencyMs is not None: provider.latency_ms = update.latencyMs

    await db.commit()

    m_result = await db.execute(select(ProviderModel).where(ProviderModel.provider_id == id))
    models = m_result.scalars().all()

    return _to_provider_response(provider, models)


@router.delete("/providers/{id}")
async def delete_provider(id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Provider).where(Provider.id == id))
    provider = result.scalars().first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    await db.delete(provider)
    await db.commit()
    return {"status": "ok"}


@router.post("/providers/{id}/test", response_model=ProviderTestResponse)
async def test_provider(id: str, db: AsyncSession = Depends(get_db)):
    # Can test existing provider
    result = await db.execute(select(Provider).where(Provider.id == id))
    provider = result.scalars().first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    return await _run_test(provider.base_url, decrypt(provider.api_key))


@router.post("/providers/test-ephemeral", response_model=ProviderTestResponse)
async def test_ephemeral_provider(data: ProviderCreate):
    # Test before creating
    return await _run_test(data.endpoint, data.apiKey)


async def _run_test(base_url: str, api_key: str) -> ProviderTestResponse:
    client = ProviderClient(base_url, api_key)
    try:
        res = await client.test_connection()
        await client.close()
        return ProviderTestResponse(
            ok=True,
            latencyMs=res["latency_ms"],
            version=res["version"],
            healthNotes=["chat.completions", "models.list"]
        )
    except (ProviderAPIError, ProviderConnectionError, ProviderTimeoutError) as e:
        await client.close()
        return ProviderTestResponse(ok=False, error=str(e))
    except Exception as e:
        await client.close()
        return ProviderTestResponse(ok=False, error=f"Unexpected error: {str(e)}")


@router.post("/providers/{id}/fetch-models", response_model=ProviderWithModelsResponse)
async def fetch_provider_models(id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Provider).where(Provider.id == id))
    provider = result.scalars().first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    client = ProviderClient(provider.base_url, decrypt(provider.api_key))
    try:
        raw_models, latency_ms = await client.fetch_models()
        await client.close()

        # Delete old models
        await db.execute(delete(ProviderModel).where(ProviderModel.provider_id == id))

        # Insert new models
        db_models = []
        for m in raw_models:
            pm = ProviderModel(
                provider_id=id,
                model_id=m["model_id"],
                display_name=m["display_name"],
                owned_by=m["owned_by"],
                context_window=m["context_window"],
                supports_vision=m["supports_vision"],
                supports_tool_calling=m["supports_tool_calling"],
                supports_streaming=m["supports_streaming"],
                supports_json_mode=m["supports_json_mode"],
                supports_reasoning=m["supports_reasoning"],
                supports_function_calling=m["supports_function_calling"],
                supports_embeddings=m["supports_embeddings"],
                max_output_tokens=m["max_output_tokens"],
                raw_metadata=m["raw_metadata"]
            )
            db.add(pm)
            db_models.append(pm)

        provider.status = "connected"
        provider.latency_ms = latency_ms
        provider.last_refresh_at = datetime.utcnow()
        provider.enabled = True

        await db.commit()

        return _to_provider_response(provider, db_models)

    except Exception as e:
        await client.close()
        provider.status = "error"
        await db.commit()
        raise HTTPException(status_code=500, detail=str(e))
