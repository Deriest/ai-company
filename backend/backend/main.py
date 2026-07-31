"""
AIC-ADE Backend — FastAPI Application.

Desktop-only architecture: backend binds to 127.0.0.1 and only accepts
localhost requests. No authentication required for single-user desktop use.
"""

import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from backend.database.session import init_db, AsyncSessionLocal, engine
from backend.services.search_service import init_fts5
from backend.middleware.logging_middleware import logging_middleware
from backend.middleware.metrics import metrics_middleware, metrics_endpoint

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ────────────────────────────────────────────────
    await init_db()
    async with AsyncSessionLocal() as db:
        await init_fts5(db)
    from backend.migrations.runner import run_migrations
    await run_migrations()

    # Initialize LLM provider from environment
    from llm.provider import provider_manager, init_provider_from_env
    config = init_provider_from_env()
    if config:
        provider_manager.register(config)
        logger.info(f"LLM provider initialized: {config.name} ({config.base_url})")
    else:
        logger.warning("No LLM provider configured (AIC_LLM_BASE_URL not set) — workers will use fallback templates")

    # Validate embedding provider
    from backend.services.embedding_provider import validate_embedding_provider
    validation = validate_embedding_provider()
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

    yield
    # ── Shutdown ───────────────────────────────────────────────
    from backend.services.heartbeat import stop_heartbeat
    stop_heartbeat()


app = FastAPI(
    title="AIC-ADE Backend",
    version="2.4.2",
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

@app.middleware("http")
async def rate_limit_wrapper(request: Request, call_next):
    return await _rate_limit_mw(request, call_next)

@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["x-content-type-options"] = "nosniff"
    response.headers["x-frame-options"] = "DENY"
    return response

@app.middleware("http")
async def logging_wrapper(request: Request, call_next):
    return await logging_middleware(request, call_next)

@app.middleware("http")
async def metrics_wrapper(request: Request, call_next):
    return await metrics_middleware(request, call_next)

@app.middleware("http")
async def localhost_only_middleware(request: Request, call_next):
    """
    Enforce localhost-only access for desktop security.
    Blocks requests from non-localhost clients.
    """
    client_host = request.client.host if request.client else ""
    # Allow localhost, 127.0.0.1, ::1, and Electron internal
    if client_host not in ("127.0.0.1", "localhost", "::1", "", "testclient"):
        return JSONResponse(
            status_code=403,
            content={"detail": "Access denied: desktop-only server"},
        )
    return await call_next(request)


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
app.include_router(pipeline_router, prefix="")
from backend.api.routes.dashboard import router as dashboard_router
app.include_router(dashboard_router, prefix="")
from backend.api.routes.skills import router as skills_router
from backend.api.routes.projects import router as projects_router
app.include_router(skills_router, prefix="")
app.include_router(projects_router, prefix="")
from backend.api.routes.approval_config import router as approval_config_router
app.include_router(approval_config_router, prefix="")
from backend.api.routes.provider_manage import router as provider_manage_router
app.include_router(provider_manage_router, prefix="")
from backend.api.routes.tasks import router as tasks_router
app.include_router(tasks_router, prefix="")

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
