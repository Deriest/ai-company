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

# Round-6: parse the source table of an "INSERT INTO <to> ... SELECT ... FROM
# <from>" copy statement so a fk_off rebuild can skip the copy when the source
# table is missing (a prior run crashed mid-rebuild and already copied the data).
_INSERT_FROM_RE = re.compile(
    r"INSERT\s+INTO\s+[^\s;]+[\s\S]*?\bFROM\s+([^\s;,]+)",
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
    {
        "version": "017",
        "name": "remove_discovery_sessions_conversation_fk",
        "description": "Rebuild discovery_sessions without the FK on conversation_id (the pipeline stores a task id there, not a conversation id)",
        # SQLite cannot drop an FK constraint without a table rebuild, and the
        # rebuild must run with FK enforcement OFF (the referenced chain
        # discovery_sessions <- engineering_briefs <- ... makes an FK-ordered
        # drop impossible). The runner applies fk_off migrations on a connection
        # with PRAGMA foreign_keys=OFF, then re-enables it.
        "fk_off": True,
        # Round-6 FIX (crash-safety): the rebuild is resumable. If the process
        # dies mid-rebuild (e.g. between DROP TABLE and ALTER RENAME), the next
        # start must recover instead of failing permanently with "no such table".
        #   - CREATE TABLE IF NOT EXISTS: a leftover _new table from a crashed
        #     run is reused instead of being dropped/recreated.
        #   - the INSERT is guarded so it only copies when the source table
        #     exists AND the _new table is empty (SQLite commits each statement
        #     atomically, so a crash mid-INSERT cannot leave a partial copy).
        "up": """
            CREATE TABLE IF NOT EXISTS discovery_sessions_new (
                id VARCHAR PRIMARY KEY,
                conversation_id VARCHAR NOT NULL,
                user_id VARCHAR,
                status VARCHAR NOT NULL DEFAULT 'new_request',
                round_number INTEGER DEFAULT 0,
                questions_asked INTEGER DEFAULT 0,
                questions_answered INTEGER DEFAULT 0,
                context TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            INSERT INTO discovery_sessions_new (id, conversation_id, user_id, status, round_number, questions_asked, questions_answered, context, created_at, updated_at)
                SELECT id, conversation_id, user_id, status, round_number, questions_asked, questions_answered, context, created_at, updated_at FROM discovery_sessions
                WHERE EXISTS (SELECT 1 FROM sqlite_master WHERE type='table' AND name='discovery_sessions')
                  AND NOT EXISTS (SELECT 1 FROM discovery_sessions_new);
            DROP TABLE IF EXISTS discovery_sessions;
            ALTER TABLE discovery_sessions_new RENAME TO discovery_sessions;
            CREATE INDEX IF NOT EXISTS idx_discovery_sessions_conversation ON discovery_sessions(conversation_id);
            CREATE INDEX IF NOT EXISTS idx_discovery_sessions_user ON discovery_sessions(user_id);
            CREATE INDEX IF NOT EXISTS idx_discovery_sessions_status ON discovery_sessions(status);
        """,
        "down": "SELECT 1",
    },
    {
        "version": "018",
        "name": "dedupe_providers_and_unique_name",
        "description": "Dedupe existing providers by name (keep the first-inserted row per name), then add a unique index on providers.name so POST /providers and POST /providers/config both enforce name uniqueness",
        "up": """
            DELETE FROM providers
            WHERE id IN (
                SELECT p.id
                FROM providers p
                JOIN (
                    SELECT name, MIN(rowid) AS keep_rowid
                    FROM providers
                    GROUP BY name
                ) k ON k.name = p.name
                WHERE p.rowid != k.keep_rowid
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_providers_name ON providers(name);
        """,
        "down": "SELECT 1",
    },
    {
        "version": "019",
        "name": "add_github_token_to_local_profile",
        "description": "Add encrypted github_token column to local_profile (GitHub personal token for setup/settings, stored via backend.services.crypto Fernet)",
        # Matches the 010/011 pattern: simple nullable VARCHAR ADD COLUMN. The
        # plaintext is never stored — the route encrypts before writing, and the
        # /profile API masks reads as "***".
        "up": "ALTER TABLE local_profile ADD COLUMN github_token VARCHAR",
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


async def _apply_migration(migration: dict) -> None:
    """Apply a normal migration inside a transaction."""
    async with engine.begin() as conn:
        for stmt in migration["up"].strip().split(";"):
            stmt = stmt.strip()
            if stmt and stmt != "SELECT 1":
                await conn.execute(text(stmt))
        await conn.execute(text(
            "INSERT INTO schema_migrations (version, name) VALUES (:v, :n)"
        ), {"v": migration["version"], "n": migration["name"]})


async def _src_table_missing(conn, stmt: str) -> bool:
    """Return True when an INSERT...SELECT statement's source table is missing.

    Round-6: a fk_off rebuild (migration 017) can crash between DROP TABLE and
    ALTER RENAME. On the next start the source table no longer exists, so the
    plain statement would fail permanently with "no such table" — even though
    the data was already copied into the _new table before the crash. SQLite
    refuses to even parse a statement referencing a missing table, so this
    guard must live in Python rather than in a SQL WHERE clause.
    """
    match = _INSERT_FROM_RE.search(stmt)
    if not match:
        return False
    src_table = match.group(1)
    result = await conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
    ))
    existing = {row[0] for row in result.fetchall()}
    return src_table not in existing


async def _apply_migration_fk_off(migration: dict) -> None:
    """Apply a table-rebuild migration with FK enforcement relaxed.

    SQLite cannot drop/modify an FK column without rebuilding the table, and the
    referenced-table chain makes an FK-ordered drop impossible. PRAGMA
    foreign_keys is a no-op inside a transaction, so it is set on the connection
    before the DDL statements run, then re-enabled before the connection returns
    to the pool. The pragma is restored in a finally block so a failed migration
    can never leak a pooled connection with FK enforcement still OFF.

    Round-6: the whole rebuild now runs inside one explicit transaction
    (``conn.begin()``) so it is atomic — a crash mid-rebuild rolls back instead
    of leaving a half-rebuilt state (old table dropped, _new table orphaned)
    that the next start would trip over. The migration marker is committed
    together with the DDL, so migration 017 is no longer re-run on every start.
    """
    conn = await engine.connect()
    try:
        await conn.execute(text("PRAGMA foreign_keys=OFF"))
        # Close SQLAlchemy's autobegin bookkeeping so the explicit transaction
        # below can start cleanly (the pragma itself is already live at the
        # SQLite driver level).
        await conn.commit()
        async with conn.begin():
            for stmt in migration["up"].strip().split(";"):
                stmt = stmt.strip()
                if stmt and stmt != "SELECT 1":
                    # Round-6: skip a copy statement whose source table was
                    # dropped by a crashed earlier run — the data is already in
                    # the _new table, so the rebuild can resume.
                    if await _src_table_missing(conn, stmt):
                        logger.warning(
                            f"Migration {migration['version']}: skipping statement — "
                            f"source table missing (resuming from a partial rebuild): "
                            f"{stmt[:80]}"
                        )
                        continue
                    await conn.execute(text(stmt))
            await conn.execute(text(
                "INSERT OR IGNORE INTO schema_migrations (version, name) VALUES (:v, :n)"
            ), {"v": migration["version"], "n": migration["name"]})
    finally:
        try:
            await conn.execute(text("PRAGMA foreign_keys=ON"))
        finally:
            await conn.close()


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
            if migration.get("fk_off"):
                await _apply_migration_fk_off(migration)
            else:
                await _apply_migration(migration)
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
