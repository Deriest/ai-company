"""AIC Platform — storage metadata and shared database session access."""
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.session import AsyncSessionLocal, engine
from storage.models import Base

# The backend and storage models share one SQLite file. Re-export the primary
# session factory instead of maintaining an independent connection pool.
async_session = AsyncSessionLocal


async def init_db():
    """Create all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session
