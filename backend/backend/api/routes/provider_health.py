"""Provider health check endpoint — re-exports from provider_manage for independent registration."""
from backend.api.routes.provider_manage import router

__all__ = ["router"]
