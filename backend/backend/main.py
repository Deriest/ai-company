"""
AIC-ADE Backend — FastAPI Application.

Desktop-only architecture: backend binds to 127.0.0.1 and only accepts
localhost requests. No authentication required for single-user desktop use.
"""

import os
import asyncio
import logging
from uuid import uuid4
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from backend.database.session import init_db, AsyncSessionLocal, engine
from backend.config import settings
from backend.services.search_service import init_fts5
from backend.middleware.logging_middleware import logging_middleware
from backend.middleware.metrics import metrics_middleware, metrics_endpoint

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ────────────────────────────────────────────────
    # H5: enable structured JSON logging (aic.* loggers) once at startup.
    try:
        from observability.logger import setup_logger
        setup_logger("backend")
    except Exception as e:
        logger.warning(f"Observability logger setup failed: {e}")

    # SECURITY: if AIC_TESTING=1 is set, the auth dependency in
    # backend/api/dependencies.py fail-opens (missing token == authenticated).
    # This is a TEST-ONLY escape hatch — never set it in production.
    if os.environ.get("AIC_TESTING") == "1":
        logger.warning(
            "AIC_TESTING=1 detected — auth fail-open is ACTIVE; never set this in production"
        )

    await init_db()
    # Defensive self-heal for existing DBs: seed the workers table (Lease rows
    # FK -> workers.id). Idempotent — safe to run on every startup.
    try:
        from backend.database.workers_seed import seed_workers
        async with AsyncSessionLocal() as db:
            await seed_workers(db)
    except Exception as e:
        logger.warning(f"Workers seed at startup failed (non-critical): {e}")
    async with AsyncSessionLocal() as db:
        await init_fts5(db)
    # FIX: run_migrations is invoked inside init_db() — do not call it twice at
    # startup (harmless but wasteful).

    # Initialize LLM provider from environment
    from llm.provider import provider_manager, init_provider_from_env, ProviderConfig
    config = init_provider_from_env()
    if config:
        await provider_manager.aregister(config)
        logger.info(f"LLM provider initialized: {config.name} ({config.base_url})")
    else:
        logger.warning("No LLM provider configured (AIC_LLM_BASE_URL not set) — workers will use fallback templates")
    
    # BUG-01 FIX: Register providers from database
    from backend.models.schema import Provider, ProviderModel, WorkerRuntime
    from backend.services.crypto import decrypt as decrypt_api_key
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        # QA-2440 FIX: Register connected providers first so provider_manager's
        # active provider is a working one, and skip providers whose API key is
        # empty/undecryptable — they can never authenticate and previously became
        # the active provider, breaking AgentRunner/workers/chat.
        result = await db.execute(
            select(Provider)
            .where(Provider.enabled == True)
            .order_by(
                (Provider.status == "connected").desc(),
                Provider.last_refresh_at.desc(),
            )
        )
        db_providers = result.scalars().all()
        for p in db_providers:
            try:
                base_url = p.base_url.rstrip("/")
                if not base_url.endswith("/v1"):
                    base_url += "/v1"
                api_key = decrypt_api_key(p.api_key)
                if not (api_key or "").strip():
                    logger.warning(f"Skipping DB provider {p.name}: no usable API key")
                    continue
                
                # Get models for this provider
                model_result = await db.execute(
                    select(ProviderModel).where(ProviderModel.provider_id == p.id)
                )
                provider_models = model_result.scalars().all()
                
                # R2 FIX: Build models dict from worker_runtime, not first_model
                models = {}
                
                # QA-FIX: env AIC_MODEL_* must only be applied to the provider
                # whose endpoint matches AIC_LLM_BASE_URL — stamping them onto
                # every DB provider would send a model that doesn't exist on
                # the wrong provider's endpoint (404).
                from llm.provider import _env_models_for_base_url
                for tier, model in _env_models_for_base_url(base_url).items():
                    if model:
                        models[tier] = model
                
                # Query worker_runtime to get role-specific model assignments
                # (only fill tiers not already set by env config)
                worker_result = await db.execute(
                    select(WorkerRuntime).where(WorkerRuntime.provider_id == p.id)
                )
                workers = worker_result.scalars().all()
                
                # Map worker roles to their assigned models
                for worker in workers:
                    if worker.model_id:
                        # Map worker role to provider tier
                        role_to_tier = {
                            "thinker": "thinker",
                            "crafter": "crafter",
                            "planner": "thinker",  # planner uses thinker tier
                            "reviewer": "thinker",
                            "manager": "thinker",
                        }
                        tier = role_to_tier.get(worker.role)
                        if tier and tier not in models:
                            models[tier] = worker.model_id
                
                # Fallback: if no worker_runtime models, find a valid non-combo model
                if not models and provider_models:
                    # Filter out models that are known-bad defaults:
                    #   combo/*       — combo strategies, no direct credentials
                    #   IAMHC/*       — provider without reliable credentials (525 errors)
                    #   *free*        — free tiers may be rate-limited/unreliable
                    #   *big-pickle*  — known unreliable alias
                    excluded_prefixes = ("combo/", "IAMHC/")
                    excluded_substrings = ("free", "big-pickle", "deepseek", "r1")
                    valid_models = [
                        m for m in provider_models
                        if not m.model_id.startswith(excluded_prefixes)
                        and not any(s in m.model_id.lower() for s in excluded_substrings)
                    ]
                    # If everything got filtered (unlikely), fall back to any non-combo
                    if not valid_models:
                        valid_models = [m for m in provider_models if not m.model_id.startswith("combo/")]
                    if valid_models:
                        fallback_model = valid_models[0].model_id
                        models = {
                            "thinker": fallback_model,
                            "crafter": fallback_model,
                            "sprinter": fallback_model,
                        }
                
                db_config = ProviderConfig(
                    name=p.name,
                    base_url=base_url,
                    api_key=api_key,
                    models=models if models else None,
                )
                await provider_manager.aregister(db_config)
                logger.info(f"LLM provider from DB registered: {p.name} ({base_url}) with {len(provider_models)} models")
            except Exception as e:
                logger.error(f"Failed to register provider {p.name} from DB: {e}")

    # Validate embedding provider
    from backend.services.embedding_provider import validate_embedding_provider
    # P1 #7: validate_embedding_provider() runs a sync httpx probe (Ollama
    # detect) — run it in a thread so startup never blocks the async loop.
    validation = await asyncio.to_thread(validate_embedding_provider)
    logger.info(f"Embedding provider: {validation['provider']} (production_ready={validation['production_ready']})")
    if validation['warning']:
        if "CRITICAL" in validation['warning']:
            logger.error(validation['warning'])
        else:
            logger.warning(validation['warning'])

    logger.info("AIC-ADE Backend started successfully")

    # Start heartbeat scheduler for worker health monitoring
    from backend.services.heartbeat import start_heartbeat
    start_heartbeat()

    # H7: start the background job worker so queued jobs actually execute.
    try:
        from backend.services.job_scheduler import job_scheduler
        await job_scheduler.start_background_worker(AsyncSessionLocal)
        logger.info("Background job worker started")
    except Exception as e:
        logger.warning(f"Failed to start background job worker: {e}")

    # H7: run startup self-heal (repairs stale leases / stuck tasks).
    try:
        from backend.self_healing import run_startup_self_heal
        await run_startup_self_heal()
    except Exception as e:
        logger.warning(f"Startup self-heal failed: {e}")

    # H5: wire the event recorder to the bus (persists events to DB).
    try:
        from events.recorder import subscribe_recorder
        await subscribe_recorder()
        logger.info("Event recorder subscribed")
    except Exception as e:
        logger.warning(f"Failed to subscribe event recorder: {e}")

    yield
    # ── Shutdown ───────────────────────────────────────────────
    from backend.services.heartbeat import stop_heartbeat
    stop_heartbeat()
    # H7: stop the background job worker.
    try:
        from backend.services.job_scheduler import job_scheduler
        await job_scheduler.stop_background_worker()
    except Exception as e:
        logger.warning(f"Failed to stop background job worker: {e}")
    # H3: disconnect all MCP clients so stdio subprocesses are terminated.
    try:
        from backend.services.mcp_client import mcp_pool
        await mcp_pool.disconnect_all()
    except Exception as e:
        logger.warning(f"Failed to disconnect MCP clients on shutdown: {e}")
    # Close all LLM provider httpx clients (leak fix).
    try:
        await provider_manager.close_all()
    except Exception as e:
        logger.warning(f"Failed to close LLM providers on shutdown: {e}")


app = FastAPI(
    title="AIC-ADE Backend",
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS: restrict to localhost origins for desktop-only deployment
_LOCALHOST_ORIGINS = [
    "http://localhost",
    "http://localhost:5174",
    "http://localhost:8000",
    "http://localhost:8001",
    "http://localhost:8088",
    "http://127.0.0.1",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:8001",
    "http://127.0.0.1:8088",
    "file://",  # Electron file:// protocol
    "app://.",  # Electron app:// protocol
]

# Allow dynamic port range (8000-8099)
for _port in range(8000, 8100):
    _LOCALHOST_ORIGINS.append(f"http://localhost:{_port}")
    _LOCALHOST_ORIGINS.append(f"http://127.0.0.1:{_port}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_LOCALHOST_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


from backend.middleware.rate_limiter import rate_limit_middleware as _rate_limit_mw
from backend.middleware.validation import validation_middleware as _validation_mw

@app.middleware("http")
async def validation_wrapper(request: Request, call_next):
    return await _validation_mw(request, call_next)

@app.middleware("http")
async def rate_limit_wrapper(request: Request, call_next):
    return await _rate_limit_mw(request, call_next)

@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    # Content Security Policy - restrict sources for scripts, styles, etc.
    response.headers["content-security-policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-src 'none'; object-src 'none'; base-uri 'self'; form-action 'self';"
    # XSS Protection
    response.headers["x-content-type-options"] = "nosniff"
    # Clickjacking protection
    response.headers["x-frame-options"] = "DENY"
    # Referrer policy
    response.headers["referrer-policy"] = "strict-origin-when-cross-origin"
    # Permissions policy
    response.headers["permissions-policy"] = "geolocation=(), microphone=(), camera=(), fullscreen=()"
    # Cross-domain policies
    response.headers["x-permitted-cross-domain-policies"] = "none"
    # HSTS - not applicable for localhost, but included for completeness
    # response.headers["strict-transport-security"] = "max-age=31536000; includeSubDomains; preload"
    return response

@app.middleware("http")
async def logging_wrapper(request: Request, call_next):
    # H5: propagate a trace_id through the aic.* loggers so the structured
    # JSON formatter emits one trace per request (set before the middleware
    # logs, reset after so the contextvar never leaks to the next request).
    from observability.logger import set_trace_id, reset_trace_id
    token = set_trace_id(request.headers.get("x-request-id") or str(uuid4()))
    try:
        return await logging_middleware(request, call_next)
    finally:
        reset_trace_id(token)

@app.middleware("http")
async def metrics_wrapper(request: Request, call_next):
    return await metrics_middleware(request, call_next)

@app.middleware("http")
async def localhost_only_middleware(request: Request, call_next):
    """
    Enforce localhost-only access for desktop security.

    Blocks requests from non-localhost clients. Two independent checks:
    1. The client socket address must be local.
    2. The Host header must resolve to a local host (blocks DNS rebinding,
       where a hostile page's hostname resolves to 127.0.0.1 with an
       attacker-controlled Host header).
    """
    client_host = request.client.host if request.client else ""
    # Allow localhost, 127.0.0.1, ::1, and Electron internal. The httpx
    # ASGITransport client host "testclient" is only permitted in test mode so
    # it cannot be used to bypass the localhost-only guard at runtime.
    allowed_client_hosts = {"127.0.0.1", "localhost", "::1", ""}
    if _test_mode_enabled():
        allowed_client_hosts.add("testclient")
    if client_host not in allowed_client_hosts:
        return JSONResponse(
            status_code=403,
            content={"detail": "Access denied: desktop-only server"},
        )

    # DNS-rebinding guard: the Host header must name a local host. Parse the
    # host part exactly (strip port / IPv6 brackets) — the same logic the
    # websocket endpoint uses — so tricks like "127.0.0.1.evil.com" are rejected.
    host_header = request.headers.get("host", "")
    if not _host_header_is_localhost(host_header):
        return JSONResponse(
            status_code=403,
            content={"detail": "Access denied: invalid Host header"},
        )

    return await call_next(request)


def _test_mode_enabled() -> bool:
    """True when the deterministic pytest flag (AIC_TESTING=1) is active."""
    return os.environ.get("AIC_TESTING") == "1"


# Localhost hosts always allowed. "test"/"testserver" are the httpx
# ASGITransport Host headers used by the test suite and are only permitted in
# test mode (AIC_TESTING=1) so a hostile page cannot reach the server by
# sending an arbitrary Host header at runtime.
_LOCALHOST_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
if _test_mode_enabled():
    _LOCALHOST_HOSTS = _LOCALHOST_HOSTS | frozenset({"test", "testserver"})


def _host_header_is_localhost(host: str) -> bool:
    """Parse a Host header and compare the host part exactly."""
    if not host:
        return False
    raw = host.strip()
    if raw.startswith("["):  # IPv6 literal, e.g. [::1]:8000
        if "]" in raw:
            raw = raw.split("]", 1)[0]
        else:
            raw = raw[1:]
        raw = raw.lstrip("[")
    elif raw.startswith("::") and ":" in raw:
        # bare IPv6 literal, e.g. "::1" (no port)
        raw = raw
    else:
        raw = raw.split(":", 1)[0]
    return raw.strip().lower() in _LOCALHOST_HOSTS


# Core routes
from backend.api.routes.core import router as core_router
from backend.middleware.error_handler import global_exception_handler, value_error_handler

app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(ValueError, value_error_handler)


# ── Observability Endpoints ────────────────────────────────────

@app.get("/metrics")
async def get_metrics():
    """Return in-memory request metrics as JSON."""
    return await metrics_endpoint()


@app.get("/readiness")
async def readiness():
    """Check whether the database connection is alive."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ready", "database": "ok"}
    except Exception as exc:
        logger.error(f"Readiness check failed: {exc}")
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "database": str(exc)},
        )


# ── Routes ─────────────────────────────────────────────────────

app.include_router(core_router, prefix="")

# Auth routes (local desktop identity)
from backend.api.routes.auth import router as auth_router
app.include_router(auth_router, prefix="")

# PI-1 routes
from backend.api.routes.orchestration import router as orchestration_router
from backend.api.routes.workflows import router as workflows_router
from backend.api.routes.jobs import router as jobs_router
from backend.api.routes.mcp import router as mcp_router
from backend.api.routes.memory import router as memory_router
from backend.api.routes.rag import router as rag_router
from backend.api.routes.automation import router as automation_router

app.include_router(orchestration_router, prefix="")
app.include_router(workflows_router, prefix="")
app.include_router(jobs_router, prefix="")
app.include_router(mcp_router, prefix="")
app.include_router(memory_router, prefix="")
app.include_router(rag_router, prefix="")
from backend.api.routes.profile import router as profile_router
app.include_router(profile_router, prefix="")
app.include_router(automation_router, prefix="")
from backend.api.routes.pipeline import router as pipeline_router
app.include_router(pipeline_router, prefix="/api")
from backend.api.routes.dashboard import router as dashboard_router
app.include_router(dashboard_router, prefix="")
from backend.api.routes.skills import router as skills_router
from backend.api.routes.plugins import router as plugins_router
from backend.api.routes.projects import router as projects_router
app.include_router(skills_router, prefix="")
app.include_router(plugins_router, prefix="")
app.include_router(projects_router, prefix="")
from backend.api.routes.approval_config import router as approval_config_router
app.include_router(approval_config_router, prefix="")
from backend.api.routes.provider_manage import router as provider_manage_router
app.include_router(provider_manage_router, prefix="")
from backend.api.routes.tasks import router as tasks_router
app.include_router(tasks_router, prefix="")

# Full app-data backup/restore (supersedes the per-conversation export/import)
from backend.api.routes.backup import router as backup_router
app.include_router(backup_router, prefix="")

# BUG-03 FIX: Mount workers_router — was orphan (PATCH /runtime/workers/{role} returned 404)
from backend.api.routes.workers import router as workers_router
app.include_router(workers_router, prefix="")

# Agent execution route (OpenCode-style real tool execution)
from backend.api.routes.agent import router as agent_router
app.include_router(agent_router, prefix="")

# Legacy routes (backend/routes/)
from backend.routes.conversations import router as conversations_router
from backend.routes.websocket import router as websocket_router
from backend.routes.context import router as context_router
from backend.routes.usage import router as usage_router
from backend.routes.discovery import router as discovery_router
from backend.routes.planning import router as planning_router
from backend.routes.taskgraph import router as taskgraph_router
from backend.routes.dispatcher import router as dispatcher_router
from backend.routes.verification import router as verification_router
from backend.routes.delivery import router as delivery_router
from backend.routes.autonomy import router as autonomy_router

app.include_router(conversations_router, prefix="/api/conversations")
app.include_router(websocket_router, prefix="/ws")
app.include_router(context_router, prefix="/api/context")
app.include_router(usage_router, prefix="/api")
app.include_router(discovery_router, prefix="/api/discovery")
app.include_router(planning_router, prefix="/api/planning")
app.include_router(taskgraph_router, prefix="/api/taskgraph")
app.include_router(dispatcher_router, prefix="/api/dispatcher")
app.include_router(verification_router, prefix="/api/verification")
app.include_router(delivery_router, prefix="/api/delivery")
app.include_router(autonomy_router, prefix="/api/autonomy")
