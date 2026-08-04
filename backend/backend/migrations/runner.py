"""
Simple database migration runner.
Tracks applied migrations in a schema_migrations table.
"""

import logging
import re
from sqlalchemy import text
from backend.database.session import engine

logger = logging.getLogger(__name__)

# H10: parse "ALTER TABLE <table> ADD COLUMN <column>" statements so a
# duplicate-column error can be verified against the real schema before the
# migration is marked applied.
_ADD_COLUMN_RE = re.compile(
    r"ALTER\s+TABLE\s+([^\s]+)\s+ADD\s+COLUMN\s+([^\s]+)",
    re.IGNORECASE,
)

MIGRATIONS = [
    {
        "version": "001",
        "name": "initial_schema",
        "description": "Create all initial tables (handled by SQLAlchemy create_all)",
        "up": "SELECT 1",  # No-op, handled by Base.metadata.create_all
        "down": "SELECT 1",
    },
    {
        "version": "002",
        "name": "add_worker_runtime_fields",
        "description": "Add label, description, system_prompt, is_enabled to worker_runtime",
        "up": """
            ALTER TABLE worker_runtime ADD COLUMN label VARCHAR DEFAULT '';
            ALTER TABLE worker_runtime ADD COLUMN description VARCHAR DEFAULT '';
            ALTER TABLE worker_runtime ADD COLUMN system_prompt VARCHAR DEFAULT '';
            ALTER TABLE worker_runtime ADD COLUMN is_enabled BOOLEAN DEFAULT 1;
        """,
        "down": "SELECT 1",
    },
    {
        "version": "003",
        "name": "add_orchestration_tables",
        "description": "Create orchestration_sessions, tasks, approvals, workflow_definitions, checkpoints",
        "up": "SELECT 1",  # Handled by create_all
        "down": "SELECT 1",
    },
    {
        "version": "004",
        "name": "add_job_scheduler_tables",
        "description": "Create jobs and job_logs tables",
        "up": "SELECT 1",
        "down": "SELECT 1",
    },
    {
        "version": "005",
        "name": "add_mcp_tables",
        "description": "Create mcp_registry, mcp_tools, mcp_tool_executions",
        "up": "SELECT 1",
        "down": "SELECT 1",
    },
    {
        "version": "006",
        "name": "add_memory_table",
        "description": "Create memory_entries table",
        "up": "SELECT 1",
        "down": "SELECT 1",
    },
    {
        "version": "007",
        "name": "add_rag_tables",
        "description": "Create rag_documents and rag_chunks tables",
        "up": "SELECT 1",
        "down": "SELECT 1",
    },
    {
        "version": "008",
        "name": "add_automation_tables",
        "description": "Create event_hooks, triggers, notifications tables",
        "up": "SELECT 1",
        "down": "SELECT 1",
    },
    {
        "version": "009",
        "name": "add_project_id_to_conversations",
        "description": "Add project_id column to conversations table",
        "up": "ALTER TABLE conversations ADD COLUMN project_id VARCHAR REFERENCES projects(id) ON DELETE SET NULL",
        "down": "SELECT 1",
    },
    {
        "version": "010",
        "name": "add_active_project_to_local_profile",
        "description": "Add active_project_id column to local_profile table",
        "up": "ALTER TABLE local_profile ADD COLUMN active_project_id VARCHAR REFERENCES projects(id) ON DELETE SET NULL",
        "down": "SELECT 1",
    },
    {
        "version": "011",
        "name": "add_approval_config_to_local_profile",
        "description": "Add approval_config JSON column to local_profile table",
        "up": "ALTER TABLE local_profile ADD COLUMN approval_config VARCHAR",
        "down": "SELECT 1",
    },
    {
        "version": "012",
        "name": "repair_conversation_timestamps",
        "description": "Repair nullable timestamps created by the legacy conversation mapper",
        "up": """
            UPDATE messages
            SET created_at = COALESCE(updated_at, CURRENT_TIMESTAMP)
            WHERE created_at IS NULL;
            UPDATE messages
            SET updated_at = created_at
            WHERE updated_at IS NULL;
            UPDATE conversations
            SET created_at = COALESCE(updated_at, CURRENT_TIMESTAMP)
            WHERE created_at IS NULL;
            UPDATE conversations
            SET updated_at = created_at
            WHERE updated_at IS NULL;
        """,
        "down": "SELECT 1",
    },
    {
        "version": "013",
        "name": "deprecated_auto_detect_context",
        "description": "Deprecated: context_window now auto-detected via fetch-models (QA-249-R4)",
        "up": "SELECT 1",  # No-op, auto-detection handles this
        "down": "SELECT 1",
    },
    {
        "version": "014",
        "name": "add_context_cache_tracking",
        "description": "Add context_source and context_cached_at to provider_models for Hermes-style waterfall detection (QA-2411)",
        "up": """
            ALTER TABLE provider_models ADD COLUMN context_source VARCHAR;
            ALTER TABLE provider_models ADD COLUMN context_cached_at TIMESTAMP;
        """,
        "down": "SELECT 1",
    },
    {
        "version": "015",
        "name": "add_user_id_to_conversations",
        "description": "Add user_id column to conversations table for multi-user support (QA-2419-R9)",
        "up": "ALTER TABLE conversations ADD COLUMN user_id VARCHAR REFERENCES users(id) ON DELETE SET NULL",
        "down": "SELECT 1",
    },
    {
        "version": "016",
        "name": "ensure_provider_models_table",
        "description": "Ensure provider_models table exists with all columns (QA-2419-R9)",
        "up": """
            CREATE TABLE IF NOT EXISTS provider_models (
                id VARCHAR PRIMARY KEY,
                provider_id VARCHAR NOT NULL REFERENCES providers(id) ON DELETE CASCADE,
                model_id VARCHAR NOT NULL,
                display_name VARCHAR NOT NULL,
                owned_by VARCHAR,
                context_window INTEGER,
                context_source VARCHAR,
                context_cached_at TIMESTAMP,
                max_output_tokens INTEGER,
                supports_vision BOOLEAN DEFAULT 0,
                supports_tool_calling BOOLEAN DEFAULT 0,
                supports_streaming BOOLEAN DEFAULT 1,
                supports_json_mode BOOLEAN DEFAULT 0,
                supports_reasoning BOOLEAN DEFAULT 0,
                supports_function_calling BOOLEAN DEFAULT 0,
                supports_embeddings BOOLEAN DEFAULT 0,
                raw_metadata JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            )
        """,
        "down": "SELECT 1",
    },
]


async def ensure_migration_table():
    """Create the schema_migrations table if it doesn't exist."""
    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version VARCHAR PRIMARY KEY,
                name VARCHAR NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))


async def get_applied_versions() -> set:
    """Get set of already-applied migration versions."""
    await ensure_migration_table()
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT version FROM schema_migrations"))
        return {row[0] for row in result.fetchall()}


async def _columns_exist(conn, table: str, columns: list[str]) -> bool:
    """Verify every column actually exists on the table (H10)."""
    try:
        result = await conn.execute(text(f"PRAGMA table_info({table})"))
        rows = result.fetchall()
    except Exception:
        return False
    existing = {row[1] for row in rows}
    return all(col in existing for col in columns)


async def _verify_alter_columns(up_sql: str) -> bool:
    """Check that every ALTER TABLE ADD COLUMN in the migration is present.

    H10: on a "duplicate column" error the transaction may have rolled back,
    so a sibling statement in the same migration could have failed while the
    reported error was unrelated. Only mark applied once the columns are real.
    """
    alters = _ADD_COLUMN_RE.findall(up_sql)
    if not alters:
        return True  # no ADD COLUMN statements to verify
    async with engine.begin() as conn:
        for table, column in alters:
            if not await _columns_exist(conn, table, [column]):
                logger.warning(
                    f"Migration verification failed: column {column} missing from {table}"
                )
                return False
    return True


async def run_migrations():
    """Run all pending migrations."""
    applied = await get_applied_versions()
    pending = [m for m in MIGRATIONS if m["version"] not in applied]

    if not pending:
        logger.info("Database is up to date")
        return

    for migration in pending:
        logger.info(f"Applying migration {migration['version']}: {migration['name']}")
        try:
            async with engine.begin() as conn:
                for stmt in migration["up"].strip().split(";"):
                    stmt = stmt.strip()
                    if stmt and stmt != "SELECT 1":
                        await conn.execute(text(stmt))
                await conn.execute(text(
                    "INSERT INTO schema_migrations (version, name) VALUES (:v, :n)"
                ), {"v": migration["version"], "n": migration["name"]})
            logger.info(f"  Applied: {migration['description']}")
        except Exception as e:
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                # H10: only mark applied after verifying the columns actually
                # exist — the reported error may mask a different failure in
                # the same transaction (which was rolled back).
                if await _verify_alter_columns(migration["up"]):
                    logger.info(f"  Skipped (already applied): {migration['name']}")
                    async with engine.begin() as conn:
                        await conn.execute(text(
                            "INSERT OR IGNORE INTO schema_migrations (version, name) VALUES (:v, :n)"
                        ), {"v": migration["version"], "n": migration["name"]})
                else:
                    logger.error(f"  Failed: {e}")
                    raise
            else:
                logger.error(f"  Failed: {e}")
                raise
