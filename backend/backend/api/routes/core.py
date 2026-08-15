"""Core routes — barrel file that combines all sub-modules."""
from fastapi import APIRouter, Depends
from backend.api.dependencies import require_current_user
from backend.api.routes.providers import router as providers_router
from backend.api.routes.conversations import router as conversations_router
from backend.api.routes.messages import router as messages_router
from backend.api.routes.chat import router as chat_router
from backend.api.routes.workers import router as workers_router

router = APIRouter(dependencies=[Depends(require_current_user)])
router.include_router(providers_router)
router.include_router(conversations_router)
router.include_router(messages_router)
router.include_router(chat_router)
router.include_router(workers_router)
