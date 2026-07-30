from fastapi import APIRouter
from backend.api.routes.core import router as core_router
from backend.api.routes.orchestration import router as orchestration_router
from backend.api.routes.workflows import router as workflows_router
from backend.api.routes.jobs import router as jobs_router
from backend.api.routes.mcp import router as mcp_router
from backend.api.routes.memory import router as memory_router
from backend.api.routes.rag import router as rag_router
from backend.api.routes.automation import router as automation_router

router = APIRouter()

router.include_router(core_router, tags=["core"])
router.include_router(orchestration_router, tags=["orchestration"])
router.include_router(workflows_router, tags=["workflows"])
router.include_router(jobs_router, tags=["jobs"])
router.include_router(mcp_router, tags=["mcp"])
router.include_router(memory_router, tags=["memory"])
router.include_router(rag_router, tags=["rag"])
router.include_router(automation_router, tags=["automation"])
