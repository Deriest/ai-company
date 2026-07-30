"""AIC Platform — Database session and initialization."""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker

from backend.config import settings
from storage.models import Base

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    connect_args={"timeout": 30},  # SQLite busy timeout in seconds
    pool_pre_ping=True,
)

# Set WAL journal mode + busy_timeout on first connect (SQLite concurrency fix)
from sqlalchemy import event
@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=30000")  # 30s
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    """Create all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session
