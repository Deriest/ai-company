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
    if not endpoint:
        raise HTTPException(status_code=400, detail="Endpoint required")
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
