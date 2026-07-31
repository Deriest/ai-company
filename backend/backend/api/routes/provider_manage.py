"""Provider management API — update provider config, test connection, health check."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.database.session import get_db
from backend.models.schema import Provider
from backend.services.crypto import encrypt, decrypt
from backend.services.provider_client import ProviderClient, ProviderAPIError, ProviderConnectionError, ProviderTimeoutError

router = APIRouter()


@router.post("/providers/test-connection")
async def test_provider_connection(payload: dict):
    """Test connection to a provider endpoint without saving."""
    endpoint = payload.get("endpoint", "").strip()
    api_key = payload.get("api_key", "").strip()
    provider_id = payload.get("provider_id", "").strip()
    if not endpoint:
        raise HTTPException(status_code=400, detail="Endpoint required")

    # If api_key is "***" (masked) and provider_id is provided, decrypt the stored key
    if api_key == "***" and provider_id:
        from sqlalchemy.future import select
        from backend.database.session import AsyncSessionLocal
        from backend.models.schema import Provider
        from backend.services.crypto import decrypt
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Provider).where(Provider.id == provider_id))
            provider = result.scalar_one_or_none()
            if provider:
                api_key = decrypt(provider.api_key) or ""

    if not api_key:
        return {"success": False, "error": "API Key is required", "error_type": "missing_api_key"}

    endpoint = endpoint.rstrip("/")

    client = ProviderClient(endpoint, api_key)
    try:
        result = await client.test_connection()
        await client.close()
        return {
            "success": True,
            "latency_ms": result.get("latency_ms", 0),
            "model_count": result.get("model_count", 0),
        }
    except ProviderAPIError as e:
        await client.close()
        return {"success": False, "error": e.message, "error_type": "api_error", "status_code": e.status_code}
    except ProviderConnectionError as e:
        await client.close()
        return {"success": False, "error": str(e), "error_type": "connection_error"}
    except ProviderTimeoutError as e:
        await client.close()
        return {"success": False, "error": str(e), "error_type": "timeout"}
    except Exception as e:
        await client.close()
        return {"success": False, "error": str(e), "error_type": "unknown"}

@router.get("/providers/health")
async def provider_health(db: AsyncSession = Depends(get_db)):
    """Check health of all configured providers."""
    result = await db.execute(select(Provider).where(Provider.enabled == True))
    providers = result.scalars().all()

    health = []
    for p in providers:
        client = ProviderClient(p.base_url, decrypt(p.api_key))
        try:
            test = await client.test_connection()
            await client.close()
            health.append({
                "id": p.id,
                "name": p.name,
                "status": "connected",
                "latency_ms": test.get("latency_ms", 0),
            })
        except Exception as e:
            await client.close()
            health.append({
                "id": p.id,
                "name": p.name,
                "status": "error",
                "error": str(e),
            })

    return health

@router.get("/providers/config")
async def get_env_config():
    """Get current provider config from .env."""
    from backend.config import settings
    
    return {
        "base_url": settings.AIC_LLM_BASE_URL or "",
        "api_key": "***" if settings.AIC_LLM_API_KEY else "",
        "provider_name": settings.AIC_LLM_PROVIDER_NAME or "default",
        "thinker": settings.AIC_MODEL_THINKER or "",
        "crafter": settings.AIC_MODEL_CRAFTER or "",
        "sprinter": settings.AIC_MODEL_SPRINTER or "",
    }

@router.post("/providers/config")
async def update_env_config(payload: dict):
    """Update provider config in .env and reload provider_manager live."""
    import os, traceback
    from pathlib import Path
    
    try:
        # Update current process env
        if "base_url" in payload: os.environ["AIC_LLM_BASE_URL"] = payload["base_url"]
        if "api_key" in payload: os.environ["AIC_LLM_API_KEY"] = payload["api_key"]
        if "provider_name" in payload: os.environ["AIC_LLM_PROVIDER_NAME"] = payload["provider_name"]
        if "thinker" in payload: os.environ["AIC_MODEL_THINKER"] = payload["thinker"]
        if "crafter" in payload: os.environ["AIC_MODEL_CRAFTER"] = payload["crafter"]
        if "sprinter" in payload: os.environ["AIC_MODEL_SPRINTER"] = payload["sprinter"]
        
        # Write to .env file
        env_path = Path(__file__).parent.parent.parent.parent / ".env"
        env_content = ""
        if env_path.exists():
            with open(env_path, "r") as f:
                env_content = f.read()
                
        lines = env_content.splitlines()
        env_vars = {
            "AIC_LLM_BASE_URL": payload.get("base_url"),
            "AIC_LLM_API_KEY": payload.get("api_key"),
            "AIC_LLM_PROVIDER_NAME": payload.get("provider_name"),
            "AIC_MODEL_THINKER": payload.get("thinker"),
            "AIC_MODEL_CRAFTER": payload.get("crafter"),
            "AIC_MODEL_SPRINTER": payload.get("sprinter"),
        }
        
        new_lines = []
        for line in lines:
            if "=" in line and not line.startswith("#"):
                k = line.split("=")[0].strip()
                if k in env_vars and env_vars[k] is not None:
                    new_lines.append(f"{k}={env_vars[k]}")
                    del env_vars[k]
                    continue
            new_lines.append(line)
            
        for k, v in env_vars.items():
            if v is not None:
                new_lines.append(f"{k}={v}")
                
# Write to .env file (try backend dir first, fallback to data dir)
        env_path = Path(__file__).parent.parent.parent.parent / ".env"
        try:
            with open(env_path, "w") as f:
                f.write("\n".join(new_lines) + "\n")
        except (PermissionError, OSError):
            # Fallback: write to data directory
            data_dir = os.environ.get("AIC_DATA_DIR", "")
            if data_dir:
                env_path = Path(data_dir) / ".env"
                with open(env_path, "w") as f:
                    f.write("\n".join(new_lines) + "\n")
            
        # Reload provider manager
        from llm.provider import provider_manager, init_provider_from_env
        config = init_provider_from_env()
        if config:
            provider_manager.register(config)
            
        return {"success": True}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
        
    return {"success": True}

@router.put("/providers/{provider_id}/config")
async def update_provider_config(provider_id: str, payload: dict, db: AsyncSession = Depends(get_db)):
    """Update provider configuration (name, endpoint, api_key, enabled)."""
    result = await db.execute(select(Provider).where(Provider.id == provider_id))
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    if "name" in payload:
        provider.name = payload["name"]
    if "endpoint" in payload:
        provider.base_url = payload["endpoint"]
    if "api_key" in payload and payload["api_key"]:
        provider.api_key = encrypt(payload["api_key"])
    if "enabled" in payload:
        provider.enabled = payload["enabled"]

    await db.commit()
    await db.refresh(provider)
    return {"id": provider.id, "name": provider.name, "status": provider.status}
