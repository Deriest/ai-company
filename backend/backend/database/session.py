from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
import os
import logging
from sqlalchemy.orm import sessionmaker, declarative_base

from backend.config import settings

logger = logging.getLogger(__name__)

DATABASE_URL = settings.DATABASE_URL

# All application routes use this engine. Keep SQLite writes cooperative while
# streaming chat and dashboard requests run concurrently.
# Configure connection pool for SQLite (single-writer optimization)
engine = create_async_engine(
    DATABASE_URL, 
    echo=False, 
    connect_args={"timeout": 30},
    pool_size=5,          # Keep small for SQLite WAL mode
    max_overflow=10,      # Allow temporary scaling during spikes
    pool_pre_ping=True,   # Detect stale connections
    pool_recycle=3600,    # Recycle connections hourly
)


@event.listens_for(engine.sync_engine, "connect")
def _configure_sqlite_connection(dbapi_conn, _connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.execute("PRAGMA synchronous=NORMAL")
    # FIX: SQLite defaults FK enforcement OFF, so ondelete=CASCADE/SET NULL never
    # fired and delete routes left orphaned rows. Enable per-connection (SQLite
    # pragmas are connection-scoped).
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

async def init_db():
    # Import all models
    import storage.models
    from storage.models import Base as StorageBase
    import backend.models.schema
    import backend.models.conversation
    import backend.models.ai_runtime
    import backend.models.orchestration
    import backend.models.jobs
    import backend.models.mcp
    import backend.models.local_profile

    # Create ALL tables on the same engine (checkfirst=True skips existing)
    # Storage tables first (includes conversations with user_id)
    async with engine.begin() as conn:
        await conn.run_sync(StorageBase.metadata.create_all)
    # Backend tables (checkfirst=True will skip duplicates)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Run migrations
    from backend.migrations.runner import run_migrations
    await run_migrations()

    # Initialize FTS5 search index
    from backend.services.search_service import init_fts5
    async with AsyncSessionLocal() as db:
        await init_fts5(db)

    # Seed built-in skills
    from backend.skill_engine import seed_builtin_skills
    async with AsyncSessionLocal() as db:
        await seed_builtin_skills(db)

    # Seed the workers table (Lease rows FK -> workers.id). Idempotent —
    # INSERT OR IGNORE per WORKER_REGISTRY key. Required so the executor's
    # Lease inserts never crash with a FOREIGN KEY constraint failure.
    # Seed the workers table (Lease rows FK -> workers.id). Idempotent —
    # INSERT OR IGNORE per WORKER_REGISTRY key. Required so the executor's
    # Lease inserts never crash with a FOREIGN KEY constraint failure.
    from backend.database.workers_seed import seed_workers
    async with AsyncSessionLocal() as db:
        await seed_workers(db)

    # Enforce strict file permissions on database (S3.2)
    try:
        db_path_str = DATABASE_URL.replace('sqlite+aiosqlite:///', '')
        if '/' in db_path_str:  # Not in-memory
            db_path = __import__('pathlib').Path(db_path_str.split('?')[0])
            if db_path.exists():
                os.chmod(db_path, 0o600)  # Owner read/write only
                logger.info(f"Set database permissions to 0o600 for {db_path}")
    except OSError as e:
        # Specific error logging with actionable message
        logger.error(
            f"Failed to set database file permissions to 0o600: {e}. "
            "Database may be accessible to other users on system. "
            "Consider manual chmod for sensitive applications."
        )
    except Exception as e:
        # Log any other unexpected errors specifically
        logger.error(
            f"Unexpected error setting database permissions: {type(e).__name__}: {str(e)}"
        )
