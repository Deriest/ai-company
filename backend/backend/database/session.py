from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

from backend.config import settings

DATABASE_URL = settings.DATABASE_URL

engine = create_async_engine(DATABASE_URL, echo=False)
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
