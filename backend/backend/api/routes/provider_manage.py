"""Provider management API — update provider config, test connection, health check."""
import json
import os
from pathlib import Path

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
            "modelCount": result.get("model_count", 0),
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
    """Get current provider config from persistent JSON file, fallback to .env/settings."""
    # Try reading from persistent engine_config.json first
    data_dir = os.environ.get("AIC_DATA_DIR", "")
    data = {}
    if data_dir:
        config_path = Path(data_dir) / "engine_config.json"
        if config_path.exists():
            try:
                with open(config_path) as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass

    from backend.config import settings

    provider_name = data.get("provider_name") or settings.AIC_LLM_PROVIDER_NAME or "default"

    # QA-SEC FIX (P0 #5): the key is never stored in plaintext — engine_config.json
    # holds the encrypted value; fall back to the encrypted DB store.
    has_key = bool(data.get("api_key"))
    if not has_key:
        try:
            from backend.database.session import AsyncSessionLocal
            async with AsyncSessionLocal() as db:
                res = await db.execute(select(Provider).where(Provider.name == provider_name))
                p = res.scalars().first()
                has_key = bool(p and p.api_key)
        except Exception:
            pass

    return {
        "base_url": data.get("base_url") or settings.AIC_LLM_BASE_URL or "",
        "api_key": "***" if has_key else "",
        "provider_name": provider_name,
        "thinker": data.get("thinker") or settings.AIC_MODEL_THINKER or "",
        "crafter": data.get("crafter") or settings.AIC_MODEL_CRAFTER or "",
        "sprinter": data.get("sprinter") or settings.AIC_MODEL_SPRINTER or "",
        "vision": data.get("vision") or settings.AIC_MODEL_VISION or "",
    }

@router.post("/providers/config")
async def update_env_config(payload: dict):
    """Update provider config and reload provider_manager live.

    QA-SEC FIX (P0 #5): the API key is never persisted in plaintext to .env or
    engine_config.json. It is stored encrypted in the DB (backend.services.crypto,
    mirroring the PUT /providers/{id}/config path) and only held in the process
    env for the live reload below. .env / engine_config.json keep non-secret
    values only and are chmod'ed 600.
    """
    import traceback

    try:
        from backend.database.session import AsyncSessionLocal
        from backend.services.crypto import encrypt as _encrypt, decrypt as _decrypt

        base_url = payload.get("base_url")
        api_key = payload.get("api_key")
        provider_name = payload.get("provider_name") or "default"

        # In-memory env mutation for the live reload below (process-local only,
        # never persisted to disk). Masked/"***" values are skipped so the real
        # key from the encrypted DB store is preserved.
        if base_url is not None: os.environ["AIC_LLM_BASE_URL"] = base_url
        if provider_name is not None: os.environ["AIC_LLM_PROVIDER_NAME"] = provider_name
        if "thinker" in payload: os.environ["AIC_MODEL_THINKER"] = payload["thinker"]
        if "crafter" in payload: os.environ["AIC_MODEL_CRAFTER"] = payload["crafter"]
        if "sprinter" in payload: os.environ["AIC_MODEL_SPRINTER"] = payload["sprinter"]
        if "vision" in payload: os.environ["AIC_MODEL_VISION"] = payload["vision"]
        if api_key is not None and api_key != "***":
            os.environ["AIC_LLM_API_KEY"] = api_key

        # Persist the API key encrypted in the DB (preferred store).
        stored_key = ""
        async with AsyncSessionLocal() as db:
            res = await db.execute(select(Provider).where(Provider.name == provider_name))
            prov = res.scalars().first()
            if prov:
                if base_url is not None:
                    prov.base_url = base_url
                if api_key and api_key != "***":
                    prov.api_key = _encrypt(api_key)
                prov.enabled = True
            else:
                prov = Provider(
                    name=provider_name,
                    base_url=base_url or "",
                    api_key=_encrypt(api_key) if api_key and api_key != "***" else "",
                    enabled=True,
                    status="disconnected",
                )
                db.add(prov)
            await db.commit()
            await db.refresh(prov)
            stored_key = _decrypt(prov.api_key) if prov.api_key else ""

        # Write non-secret values to .env (API key intentionally omitted; any
        # pre-existing plaintext AIC_LLM_API_KEY line is stripped).
        env_path = Path(__file__).parent.parent.parent.parent / ".env"
        env_content = ""
        if env_path.exists():
            with open(env_path, "r") as f:
                env_content = f.read()

        env_vars = {
            "AIC_LLM_BASE_URL": base_url,
            "AIC_LLM_PROVIDER_NAME": provider_name,
            "AIC_MODEL_THINKER": payload.get("thinker"),
            "AIC_MODEL_CRAFTER": payload.get("crafter"),
            "AIC_MODEL_SPRINTER": payload.get("sprinter"),
            "AIC_MODEL_VISION": payload.get("vision"),
        }
        _SECRET_ENV_KEYS = {"AIC_LLM_API_KEY"}

        new_lines = []
        for line in env_content.splitlines():
            if "=" in line and not line.startswith("#"):
                k = line.split("=")[0].strip()
                if k in _SECRET_ENV_KEYS:
                    continue  # strip stale plaintext key
                if k in env_vars and env_vars[k] is not None:
                    new_lines.append(f"{k}={env_vars[k]}")
                    del env_vars[k]
                    continue
            new_lines.append(line)

        for k, v in env_vars.items():
            if v is not None:
                new_lines.append(f"{k}={v}")

        try:
            with open(env_path, "w") as f:
                f.write("\n".join(new_lines) + "\n")
            try:
                os.chmod(env_path, 0o600)
            except OSError:
                pass
        except (PermissionError, OSError):
            # Fallback: write to data directory
            data_dir = os.environ.get("AIC_DATA_DIR", "")
            if data_dir:
                env_path = Path(data_dir) / ".env"
                with open(env_path, "w") as f:
                    f.write("\n".join(new_lines) + "\n")
                try:
                    os.chmod(env_path, 0o600)
                except OSError:
                    pass

        # Persist non-secret values to engine_config.json (encrypted key only,
        # never plaintext) for cross-restart durability.
        data_dir = os.environ.get("AIC_DATA_DIR", "")
        if data_dir:
            config_path = Path(data_dir) / "engine_config.json"
            existing = {}
            if config_path.exists():
                try:
                    with open(config_path) as f:
                        existing = json.load(f)
                except (json.JSONDecodeError, OSError):
                    pass
            # Preserve the existing stored (encrypted) key when the payload
            # re-sends a masked "***" or empty value.
            stored_key_json = existing.get("api_key", "")
            if api_key and api_key != "***":
                stored_key_json = _encrypt(api_key)
            try:
                with open(config_path, "w") as f:
                    json.dump({
                        "thinker": payload.get("thinker"),
                        "crafter": payload.get("crafter"),
                        "sprinter": payload.get("sprinter"),
                        "vision": payload.get("vision"),
                        "provider_name": provider_name,
                        "base_url": base_url,
                        "api_key": stored_key_json,
                    }, f)
                try:
                    os.chmod(config_path, 0o600)
                except OSError:
                    pass
            except OSError:
                pass  # Non-fatal; env var + .env still work if writable

        # Reload provider manager
        from llm.provider import provider_manager, init_provider_from_env, ProviderConfig
        config = init_provider_from_env()
        if config:
            provider_manager.register(config)
        # Register the DB provider live so the manager always has a usable key
        # (get_active_with_key prefers it over the empty-key env provider).
        if base_url and stored_key:
            base_url_norm = base_url.rstrip("/")
            if not base_url_norm.endswith("/v1"):
                base_url_norm += "/v1"
            models = {}
            for _tier, _model in (
                ("thinker", payload.get("thinker")),
                ("crafter", payload.get("crafter")),
                ("sprinter", payload.get("sprinter")),
                ("vision", payload.get("vision")),
            ):
                if _model:
                    models[_tier] = _model
            db_config = ProviderConfig(
                name=provider_name,
                base_url=base_url_norm,
                api_key=stored_key,
                models=models or None,
            )
            await provider_manager.aregister(db_config)
        if not provider_manager.get_active():
            provider_manager.set_active(provider_name)

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

    # BUG-15 FIX: Re-register provider live after config update
    try:
        from llm.provider import provider_manager, ProviderConfig
        base_url = provider.base_url.rstrip("/")
        if not base_url.endswith("/v1"):
            base_url += "/v1"
        api_key = decrypt(provider.api_key) if provider.api_key else ""
        config = ProviderConfig(
            name=provider.name,
            base_url=base_url,
            api_key=api_key,
        )
        await provider_manager.aregister(config)
        if not provider_manager.get_active():
            provider_manager.set_active(provider.name)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"BUG-15: Failed to register provider live: {e}")

    return {"id": provider.id, "name": provider.name, "status": provider.status}
