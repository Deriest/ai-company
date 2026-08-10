"""AIC Platform — storage metadata and shared database session access."""
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Callable
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import scoped_session

from backend.database.session import engine
from storage.models import Base

logger = logging.getLogger("aic.db")


session_factory = async_sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


@asynccontextmanager
async def get_session(auto_commit: bool = True) -> AsyncGenerator[AsyncSession, None]:
    """Auto-commit context manager for safe DB access.
    
    Usage:
        async with get_session(auto_commit=True) as session:
            ...
    
    Automatically commits on success, rolls back on error, and ensures cleanup.
    All route handlers should use this pattern instead of Depends(get_session).
    """
    session: AsyncSession = session_factory()
    try:
        yield session
        if auto_commit:
            await session.commit()
            logger.debug(f"Session committed: {id(session)}")
    except Exception as e:
        logger.warning(f"Session rolled back due to error: {e}", exc_info=False)
        await session.rollback()
        raise
    finally:
        await session.close()
        logger.debug(f"Session closed: {id(session)}")


async def init_db():
    """Create all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def make_session():
    """Make an async session directly (for internal use only).
    
    Returns a callable that creates sessions without auto-commit management.
    Deprecated: use get_session() context manager instead.
    """
    logger.warning("make_session() is deprecated; use get_session() context manager")
    return session_factory


# Legacy export for compatibility - returns a callable, not a coroutine
async_session = make_session
