# Backend Migrations Module — Database Schema Evolution (v2.3.8)

**Location**: `/backend/backend/migrations/`  
**Last Updated**: 2026-08-10

---

## 1. Responsibility

### Primary Role
**Database Schema Evolution Engine**: Implements a simple, migration-based schema management system for the AIC Platform's SQLite database. This module defines and executes **20 incremental migrations** that evolve the database schema from initial creation to current state, handling table creation, column additions, data repairs, constraint enforcement, and crash-safe rebuilds.

### Specific Responsibilities

1. **Schema Version Tracking**: Maintain `schema_migrations` table documenting applied migration versions with timestamps, preventing duplicate application.

2. **Incremental DDL Execution**: Apply SQL statements (`ALTER TABLE`, `CREATE TABLE`, `DROP TABLE`, `INSERT INTO...SELECT`) in dependency order via versioned migration files.

3. **Crash Recovery**: Resumable table rebuilds for migrations 017+ that require dropping/recreating tables—resume from partial states without corruption.

4. **Constraint Relaxation**: Handle migrations requiring foreign key suspension (`PRAGMA foreign_keys=OFF`) for table schema changes impossible with FK enforcement active.

5. **Column Existence Verification**: Post-migration validation ensuring ALTER TABLE ADD COLUMN statements actually persisted before marking migration applied.

6. **Duplicate Data Remediation**: Cleanup existing data during migrations (deduplicate providers by name, repair nullable timestamps).

7. **Conditional Execution**: Skip source-table-missing COPY statements when resuming crashed rebuilds.

8. **Atomic Transactions**: Wrap entire rebuild operations in single transactions for ACID compliance—rollback on failure prevents half-built schemas.

### Design Intent
Provide a **simple, non-framework-dependent migration system** that works directly with SQLite's limitations (no online schema changes, FK constraints blocking DDL) while ensuring idempotent, crash-safe evolution of the schema without needing Alembic or similar tooling.

---

## 2. Architecture

### Component Structure

| File | Lines | Purpose | Key Functions |
|------|-------|---------|---------------|
| `__init__.py` | 0 | Package marker (empty) | N/A |
| `runner.py` | 433 | Migration definition + execution | `MIGRATIONS` list, `run_migrations()`, `_apply_migration_fk_off()` |
| **Total** | **433 lines** | **Single-file migration runner** | **All migration logic** |

### Migration Registry

The `MIGRATIONS` list contains **20 versioned migrations** (001–020):

| Version | Name | Description | Type | Critical? |
|---------|------|-------------|------|-----------|
| 001 | `initial_schema` | Create all initial tables (handled by SQLAlchemy create_all) | No-op | Yes |
| 002 | `add_worker_runtime_fields` | Add label/description/system_prompt/is_enabled to worker_runtime | ALTER TABLE | No |
| 003 | `add_orchestration_tables` | Create orchestration_sessions/tasks/approvals/workflow_definitions/checkpoints | CREATE TABLE | No |
| 004 | `add_job_scheduler_tables` | Create jobs/job_logs tables | CREATE TABLE | No |
| 005 | `add_mcp_tables` | Create mcp_registry/tools/executions tables | CREATE TABLE | No |
| 006 | `add_memory_table` | Create memory_entries table | CREATE TABLE | No |
| 007 | `add_rag_tables` | Create rag_documents/chunks tables | CREATE TABLE | No |
| 008 | `add_automation_tables` | Create event_hooks/triggers/notifications tables | CREATE TABLE | No |
| 009 | `add_project_id_to_conversations` | Add project_id FK column to conversations | ALTER TABLE | No |
| 010 | `add_active_project_to_local_profile` | Add active_project_id to local_profile | ALTER TABLE | No |
| 011 | `add_approval_config_to_local_profile` | Add approval_config JSON column to local_profile | ALTER TABLE | No |
| 012 | `repair_conversation_timestamps` | Fix nullable created_at/updated_at columns | UPDATE | Yes |
| 013 | `deprecated_auto_detect_context` | Deprecated context_window auto-detection | No-op | No |
| 014 | `add_context_cache_tracking` | Add context_source/context_cached_at to provider_models | ALTER TABLE | No |
| 015 | `add_user_id_to_conversations` | Add user_id FK column (multi-user prep) | ALTER TABLE | No |
| 016 | `ensure_provider_models_table` | Ensure provider_models exists with all columns | CREATE TABLE IF NOT EXISTS | Yes |
| 017 | `remove_discovery_sessions_conversation_fk` | Rebuild discovery_sessions without problematic FK | Table rebuild | **Critical** |
| 018 | `dedupe_providers_and_unique_name` | Dedupe providers by name + add unique index | DELETE + CREATE INDEX | **Critical** |
| 019 | `add_github_token_to_local_profile` | Add encrypted github_token column | ALTER TABLE | No |
| 020 | `add_last_used_repo_path_to_local_profile` | Add last_used_repo_path column | ALTER TABLE | No |

**Migration Categories**:
- **CREATE TABLE IF NOT EXISTS**: Migrations 001, 003–008, 016 (safe re-runs)
- **ALTER TABLE ADD COLUMN**: Migrations 002, 009–011, 014, 019–020 (idempotent if verified)
- **UPDATE/Cleanup**: Migrations 012, 018 (destructive but necessary)
- **Table Rebuild**: Migration 017 (requires FK off, crash recovery)
- **No-Op**: Migrations 001, 013 (placeholder documentation)

### State Management

#### `schema_migrations` Table

Tracks applied migrations:
```sql
CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

**Properties**:
- `version`: Migration version string (e.g., `"017"`)
- `name`: Human-readable migration name
- `applied_at`: Timestamp of application

**Uniqueness**: Primary key ensures each migration applied exactly once (or `OR IGNORE` fallback).

### SQLite Limitations Addressed

1. **No Online Schema Changes**: SQLite cannot `ALTER TABLE DROP COLUMN` or modify FK constraints without rebuilding entire table.
2. **Foreign Key Blocking**: FK constraints prevent dropping referenced tables; must disable via `PRAGMA foreign_keys=OFF`.
3. **No Transaction Rollback for DDL**: Standard transactions don't rollback DDL changes automatically—must manually manage with explicit BEGIN/COMMIT.
4. **No Checkpoint Control**: WAL mode provides read concurrency but doesn't help with schema rebuilds.

This runner implements workarounds for all four limitations.

---

## 3. Design Patterns

### 1. Configuration-as-Data Pattern

Migrations defined as Python dict literals rather than external SQL files:
```python
MIGRATIONS = [
    {
        "version": "017",
        "name": "remove_discovery_sessions_conversation_fk",
        "description": "...",
        "fk_off": True,  # Special flag for FK-relaxed migrations
        "up": """CREATE TABLE IF NOT EXISTS ...""",
        "down": "SELECT 1",  # No-op, not implemented
    },
    # ...
]
```

**Benefits**:
- Centralized version ordering (Python list order matters)
- Type hints via Pydantic could validate structure
- Easy to query/filter migrations programmatically
- No file I/O overhead

**Drawbacks**:
- Harder to diff between versions (monolithic vs individual files)
- Less clear separation of concerns (logic embedded in runner)

### 2. Idempotency-with-Verification Pattern

ALERT TABLE ADD COLUMN migrations assume safe re-runs but verify column existence before marking applied:
```python
async def _verify_alter_columns(up_sql: str) -> bool:
    alters = _ADD_COLUMN_RE.findall(up_sql)
    for table, column in alters:
        if not await _columns_exist(conn, table, [column]):
            return False
    return True
```

**Behavior**:
1. Migration fails with `duplicate column` error
2. Transaction rolled back
3. Runner verifies columns actually exist (H10 fix)
4. If verified, marks migration applied despite error
5. If not verified, logs error and aborts

This handles race conditions where sibling statements in same migration succeeded but reported error was unrelated.

### 3. Crash-Safe Resume Pattern (Round-6 FIX)

Table rebuild migrations (017) implement resumable execution:
```python
# INSERT guarded by source table AND _new table emptiness
INSERT INTO discovery_sessions_new (...)
    SELECT ... FROM discovery_sessions
    WHERE EXISTS (SELECT 1 FROM sqlite_master WHERE type='table' AND name='discovery_sessions')
      AND NOT EXISTS (SELECT 1 FROM discovery_sessions_new);
```

**Scenarios handled**:
- **Clean start**: Source table exists, _new table empty → copy runs
- **Mid-rebuild crash**: Source table still exists (not dropped yet), _new table partially filled → copy skipped (data already copied)
- **Post-drop resume**: Source table gone (dropped after crash), _new table populated → copy skipped, proceed to rename
- **Orphan _new table**: Previous crash left _new table, no source → reuse _new instead of failing

Key insight: The `WHERE EXISTS / NOT EXISTS` guards prevent both **double-copy** (wasteful) and **permanent failure** (when source gone mid-run).

### 4. Explicit Transaction Boundary Pattern

Rebuild migrations use explicit transaction control instead of implicit autobegin:
```python
conn = await engine.connect()
try:
    await conn.execute(text("PRAGMA foreign_keys=OFF"))
    await conn.commit()  # Close autobegin so explicit tx can start cleanly
    async with conn.begin():  # Explicit BEGIN TRANSACTION
        for stmt in migration["up"].split(";"):
            await conn.execute(text(stmt))
        await conn.execute(...)  # Mark migration applied
finally:
    await conn.execute(text("PRAGMA foreign_keys=ON"))
    await conn.close()
```

**Why explicit?**
- `PRAGMA foreign_keys` is per-connection, not global
- Must ensure PRAGMA stays OFF throughout DDL sequence
- Must restore PRAGMA ON even on failure (finally block)
- Atomic commit/rollback requires explicit transaction boundaries

Standard `engine.begin()` context manager would re-enable FK automatically after DDL completes—too late for DROP TABLE statements.

### 5. Regex-Parsed Statement Skipping Pattern

Parse SQL strings with regex to conditionally skip COPY statements based on source table presence:
```python
_INSERT_FROM_RE = re.compile(
    r"INSERT\s+INTO\s+[^\s;]+[\s\S]*?\bFROM\s+([^\s;,]+)",
    re.IGNORECASE,
)

async def _src_table_missing(conn, stmt: str) -> bool:
    match = _INSERT_FROM_RE.search(stmt)
    if not match:
        return False
    src_table = match.group(1)
    result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"))
    existing = {row[0] for row in result.fetchall()}
    return src_table not in existing
```

**Usage**: In rebuild migrations, check each INSERT statement:
- If source table missing → log warning, skip statement
- Resume next statement in migration
- Eventually complete migrate successfully

Prevents hard failures on resume scenarios.

### 6. Error-Tolerant Upgrade Pattern

Handle specific error messages gracefully without aborting upgrade:
```python
if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
    if await _verify_alter_columns(migration["up"]):
        logger.info(f"  Skipped (already applied): {migration['name']}")
        async with engine.begin() as conn:
            await conn.execute(text(
                "INSERT OR IGNORE INTO schema_migrations (version, name) VALUES (:v, :n)"
            ), {"v": migration["version"], "n": migration["name"]})
    else:
        raise  # Real failure, propagate
```

**Pattern**: Don't just ignore errors—validate post-condition before assuming success.

### 7. Single-Source-of-Truth Pattern

All schema changes defined in one place (`MIGRATIONS` list) rather than scattered across:
- ORM model definitions (`backend/models/*.py`)
- Alembic migration files (none used here)
- Manual SQL scripts

**Benefits**:
- One source of truth for schema evolution
- Easy to see full migration history at glance
- No drift between code models and actual DB schema

**Drawbacks**:
- No automatic diff generation (must write up/down SQL manually)
- Harder to collaborate on migrations (single large file)

### 8. Fallback-to-SQLAlchemy Pattern

Use SQLAlchemy's `create_all()` for fresh installs, then migrations take over:
```python
{
    "version": "001",
    "name": "initial_schema",
    "description": "Create all initial tables (handled by SQLAlchemy create_all)",
    "up": "SELECT 1",  # No-op
    "down": "SELECT 1",
}
```

**Workflow**:
1. Fresh install: `Base.metadata.create_all(engine)` creates all tables
2. First startup: Migration 001 detected as pending, executed as NO-OP (already exists)
3. Subsequent migrations run incrementally

Avoids duplicating CREATE TABLE statements in two places.

### 9. Logging-and-Cascade-Restart Pattern

All migration steps logged with clear status markers:
```python
logger.info(f"Applying migration {migration['version']}: {migration['name']}")
try:
    if migration.get("fk_off"):
        await _apply_migration_fk_off(migration)
    else:
        await _apply_migration(migration)
    logger.info(f"  Applied: {migration['description']}")
except Exception as e:
    logger.error(f"  Failed: {e}")
    raise
```

**Benefits**:
- Clear audit trail in application logs
- Easy to debug failed migrations
- Can resume from known state

### 10. Selective-Pragmas Pattern

Only disable FK enforcement for migrations that absolutely need it (migration 017):
```python
{
    "version": "017",
    "fk_off": True,  # Only this migration needs FK disabled
    ...
}
```

**Why not disable globally?**
- Security/integrity risks
- Harder to reason about which migrations affected by FK relaxation
- Better to localize scope

Each migration declaring its own requirements keeps concerns isolated.

---

## 4. Data & Control Flow

### Entry Points

#### 1. Application Startup (`main.py` or equivalent)

Primary invocation point:
```python
from backend.migrations.runner import run_migrations

async def main():
    await run_migrations()  # Run before any database access
    # Continue with app initialization...
```

**Timing**: Must run **before** any ORM model access to ensure schema matches expectations.

#### 2. CLI Tools (Optional)

Manual migration trigger:
```bash
python -c "import asyncio; from backend.migrations.runner import run_migrations; asyncio.run(run_migrations())"
```

Useful for debugging or running migrations in isolation.

### Processing Flow

#### Normal Migration Path (Non-FK-off)

```mermaid
graph TD
    A[Run run_migrations()] --> B{Get applied versions}
    B --> C[Filter MIGRATIONS list for pending]
    C --> D{Any pending?}
    D -->|No| E[Log: Database up to date]
    D -->|Yes| F[Loop through pending migrations]
    F --> G{Has fk_off flag?}
    G -->|No| H[_apply_migration]
    G -->|Yes| I[_apply_migration_fk_off]
    H --> J[Split up SQL by semicolons]
    J --> K[Execute each non-empty statement]
    K --> L[INSERT into schema_migrations]
    L --> M[Commit transaction]
    M --> N{Success?}
    N -->|Yes| O[Log: Applied successfully]
    N -->|No| P[Catch exception]
    P --> Q{Error is duplicate column?}
    Q -->|Yes| R[_verify_alter_columns]
    R --> S{Columns exist?}
    S -->|Yes| T[Mark applied anyway + log skipped]
    S -->|No| U[Propagate error]
    Q -->|No| V[Propagate error]
    
    style E fill:#9f9
    style O fill:#9f9
    style T fill:#ff9
    style U fill:#f99
    style V fill:#f99
```

**Steps**:
1. Query `schema_migrations` for applied versions
2. Filter `MIGRATIONS` list to find pending ones
3. For each pending migration:
   - Check if `fk_off=True` flag set
   - Execute appropriate apply function
   - Log success or handle error

#### FK-off Migration Path (Table Rebuilds)

```
Apply migration with fk_off=True
  ↓
Connect to DB (new connection, not pooled)
  ↓
SET PRAGMA foreign_keys=OFF
  ↓
Explicit BEGIN TRANSACTION
  ↓
For each SQL statement:
    ├─ Parse statement for source table (regex)
    ├─ Check if source table exists (sqlite_master query)
    ├─ If source missing → LOG SKIP, continue
    └─ Else → Execute statement
  ↓
INSERT OR IGNORE into schema_migrations (mark applied)
  ↓
COMMIT transaction (atomic or rollback)
  ↓
Finally block: SET PRAGMA foreign_keys=ON
  ↓
Close connection
  ↓
Return to caller
```

**Critical differences from normal path**:
- New connection (not shared pool)
- Explicit BEGIN/COMMIT (not autocommit)
- FK pragma manipulation around DDL
- Source table presence checks for resumability

### Detailed Migration Examples

#### Migration 017: Remove Discovery Sessions FK (Critical Rebuild)

This migration exemplifies the most complex pattern (crash-safe table rebuild).

**Problem**: `discovery_sessions.conversation_id` has an invalid FK reference (should be task ID, not conversation ID). SQLite cannot drop FK without rebuilding table.

**Solution**:
```sql
-- Step 1: Create new table without FK
CREATE TABLE IF NOT EXISTS discovery_sessions_new (
    id VARCHAR PRIMARY KEY,
    conversation_id VARCHAR NOT NULL,  -- No FK constraint
    user_id VARCHAR,
    status VARCHAR NOT NULL DEFAULT 'new_request',
    round_number INTEGER DEFAULT 0,
    questions_asked INTEGER DEFAULT 0,
    questions_answered INTEGER DEFAULT 0,
    context TEXT DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Step 2: Copy data (only if source exists AND destination empty)
INSERT INTO discovery_sessions_new (id, conversation_id, ...)
    SELECT id, conversation_id, ... FROM discovery_sessions
    WHERE EXISTS (SELECT 1 FROM sqlite_master WHERE type='table' AND name='discovery_sessions')
      AND NOT EXISTS (SELECT 1 FROM discovery_sessions_new);

-- Step 3: Drop old table
DROP TABLE IF EXISTS discovery_sessions;

-- Step 4: Rename new table to original name
ALTER TABLE discovery_sessions_new RENAME TO discovery_sessions;

-- Step 5: Recreate indexes
CREATE INDEX IF NOT EXISTS idx_discovery_sessions_conversation ON discovery_sessions(conversation_id);
CREATE INDEX IF NOT EXISTS idx_discovery_sessions_user ON discovery_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_discovery_sessions_status ON discovery_sessions(status);
```

**Resumability**:
- **Start clean**: Steps execute sequentially → success
- **Crash mid-step 1**: Step 1 uses `IF NOT EXISTS` → next run reuses existing _new table
- **Crash mid-step 2**: Step 2 skips due to `NOT EXISTS (SELECT ... FROM discovery_sessions_new)` → data already copied
- **Crash mid-step 3**: Step 3 drops table → Step 4 renames (if _new exists) → indices recreated → migration marked applied
- **Crash mid-step 4**: Same as above, just skips unnecessary RENAME

**Safety**: Entire operation wrapped in single transaction—if any step fails, everything rolls back.

#### Migration 018: Deduplicate Providers + Unique Index

Cleanup existing data while enforcing future uniqueness:
```sql
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
```

**Behavior**:
1. Find duplicate names grouped by `GROUP BY name`
2. Keep lowest `rowid` per group (first-inserted row)
3. Delete all other duplicates
4. After cleanup, add unique index to prevent future duplicates

**Idempotency**: Safe to re-run—if already deduplicated, DELETE affects zero rows, INDEX creation skipped via `IF NOT EXISTS`.

#### Migration 012: Repair Nullable Timestamps

Fix legacy timestamp gaps:
```sql
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
```

**Logic**:
1. If `created_at` missing, copy from `updated_at` or use NOW()
2. If `updated_at` missing, copy from newly-set `created_at`
3. Ensures both timestamps always have values

**Impact**: Required because old migration mapper left nullable timestamps that broke queries relying on non-null values.

### Data Dependencies

| Source | Consumed By | Usage Details |
|--------|-------------|---------------|
| `backend.database.session.engine` | All functions | Provides DB connections for migrations |
| `sqlite_master` | `_src_table_missing()` | Queries table existence during resumable copies |
| `schema_migrations` | `get_applied_versions()`, `_apply_migration()` | Tracks applied migrations, prevents re-application |
| `PRAGMA table_info()` | `_columns_exist()` | Validates column addition success |
| Regex patterns | Statement parsing | Extracts table/column names for verification |

### Output Structures

#### Migration Status Log (Console Output)

```
INFO - Applying migration 017: remove_discovery_sessions_conversation_fk
INFO -   Applied: Rebuild discovery_sessions without the FK on conversation_id
INFO - Applying migration 018: dedupe_providers_and_unique_name
INFO -   Applied: Dedupe existing providers by name (keep the first-inserted row per name), then add a unique index on providers.name
INFO - Database is up to date
```

**On Resume Scenario**:
```
WARNING - Migration 017: skipping statement — source table missing (resuming from a partial rebuild): INSERT INTO discovery_sessions_new SELECT id...
INFO -   Applied: Rebuild discovery_sessions without the FK on conversation_id
```

#### Applied Versions Query Result

```python
{"001", "002", "003", "004", "005", "006", "007", "008", "009", "010", "011", "012", "013", "014", "015", "016", "017", "018", "019", "020"}
```

Set of string-version identifiers for already-applied migrations.

### Exit Points

1. **Migration Applied**: Version inserted into `schema_migrations`, committed to DB
2. **Migration Skipped**: Already applied (error-tolerant), version ignored via `INSERT OR IGNORE`
3. **Migration Failed**: Exception propagated, DB transaction rolled back, version not applied
4. **Already Up to Date**: No pending migrations, immediate return

---

## 5. Integration Points

### Dependencies

#### Internal Dependencies

| Module | Dependency Type | Usage Details |
|--------|----------------|---------------|
| `backend.database.session` | Direct import | `engine` object for DB connections |
| `storage.models` | Indirect reference | Tables migrated by these migrations (conversations, provider_models, etc.) |
| `backend.models.*` | Indirect reference | ORM models mirroring migrated schema (provider_models, worker_runtime, etc.) |
| `sqlalchemy.ext.asyncio` | Async support | Async session/connection management |

#### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `sqlalchemy` | 2.x | Text expressions, async engine, transaction management |
| `re` | stdlib | Regex parsing for SQL statement extraction |
| `logging` | stdlib | Progress logging |

### Consumer Modules

#### 1. Application Startup Sequence

Primary consumer invoking migrations before any database access:
```python
# In main.py or app initialization
from backend.migrations.runner import run_migrations

async def create_app():
    await run_migrations()  # Ensure schema matches models
    # Initialize FastAPI app, register routers, etc.
    return app
```

**Timing**: Must run **before** any `select()`, `insert()`, or ORM model usage.

#### 2. CLI Tool Invocation

Manual migration trigger for debugging:
```bash
# Run migrations standalone
python -c "import asyncio; from backend.migrations.runner import run_migrations; asyncio.run(run_migrations())"

# Or within shell script
./scripts/run-migrations.sh
```

#### 3. Testing Suite

Tests verifying migration behavior:
```python
from backend.migrations.runner import MIGRATIONS, get_applied_versions

def test_migration_count():
    assert len(MIGRATIONS) == 20  # All migrations accounted for

def test_version_ordering():
    versions = [m["version"] for m in MIGRATIONS]
    assert versions == sorted(versions)  # Ordered 001–020
```

Not explicitly implemented yet but implied by design.

### Database Integration

#### SQLite Specifics

**Engine Configuration**:
- Default: In-memory or file-based SQLite
- WAL Mode: Enabled for concurrent reads/writes
- Foreign Keys: Default ON, temporarily OFF for rebuild migrations

**Transaction Behavior**:
- Autocommit: Disabled during migration loops (explicit transactions preferred)
- Rollback: Automatic on exception, except in error-tolerant cases (duplicate column)

**Index Strategy**:
- Auto-created via `CREATE INDEX IF NOT EXISTS` in migrations
- Manual recreation after table rebuild (migration 017)

#### Migration History

Full schema evolution tracked via `schema_migrations`:
```sql
SELECT version, name, applied_at FROM schema_migrations ORDER BY CAST(version AS INT);
```

Expected output after full upgrade:
```
001 | initial_schema | 2026-08-10 10:00:00
002 | add_worker_runtime_fields | 2026-08-10 10:00:01
003 | add_orchestration_tables | 2026-08-10 10:00:02
...
020 | add_last_used_repo_path_to_local_profile | 2026-08-10 10:00:20
```

### Migration Execution Timeline

| Event | Action | Notes |
|-------|--------|-------|
| App starts | Check applied versions | Query schema_migrations |
| Pending found | Loop through migrations | Process 001–020 in order |
| Migration X begins | Log start, enter transaction | Start explicit BEGIN TRANSACTION |
| Migration X succeeds | Insert version mark, commit | Log success |
| Migration X fails | Rollback transaction, exit | Propagate exception to caller |
| All done | Log "Database up to date" | Return control to caller |

---

## 6. Configuration

### Runtime Flags

| Flag | Location | Effect |
|------|----------|--------|
| `AIC_DATA_DIR` | Environment | Determines SQLite file location (`aic.db`) |
| `PRAGMA foreign_keys` | Per-migration | Temporarily disabled for rebuild migrations |

### Migration-Specific Flags

| Flag | Migrations Using | Purpose |
|------|------------------|---------|
| `fk_off=True` | 017 only | Requires FK relaxation for table rebuild |
| `SELECT 1` | 001, 003–008, 013 | No-op placeholder (handled elsewhere) |
| `INSERT OR IGNORE` | 017, error-tolerant paths | Prevent duplicate version insertion on retry |

---

## 7. Key Classes & Functions

### `MIGRATIONS` List

Central migration registry:
```python
MIGRATIONS = [
    {
        "version": str,          # e.g., "017"
        "name": str,             # e.g., "remove_discovery_sessions_conversation_fk"
        "description": str,      # Human-readable summary
        "up": str,               # SQL to apply
        "down": str,             # No-op (not implemented)
        "fk_off": bool,          # Optional: relax FK enforcement
    },
    # ... 20 total entries
]
```

**Structure**: Dictionary-based for extensibility (could add schema validation later).

### `run_migrations()`

Main entry point:
```python
async def run_migrations():
    """Run all pending migrations."""
    applied = await get_applied_versions()
    pending = [m for m in MIGRATIONS if m["version"] not in applied]
    
    if not pending:
        logger.info("Database is up to date")
        return
    
    for migration in pending:
        try:
            if migration.get("fk_off"):
                await _apply_migration_fk_off(migration)
            else:
                await _apply_migration(migration)
            logger.info(f"  Applied: {migration['description']}")
        except Exception as e:
            # Error handling with duplicate-column special case
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                if await _verify_alter_columns(migration["up"]):
                    # Mark applied despite error
                else:
                    raise
            else:
                raise
```

**Responsibilities**:
- Determine pending migrations
- Dispatch to appropriate apply function (normal vs FK-off)
- Handle error-tolerant upgrades (duplicate column scenario)
- Log progress and outcomes

### `get_applied_versions()`

Query applied migrations:
```python
async def get_applied_versions() -> set:
    """Get set of already-applied migration versions."""
    await ensure_migration_table()
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT version FROM schema_migrations"))
        return {row[0] for row in result.fetchall()}
```

Returns set of version strings for efficient membership testing.

### `_apply_migration(migration)`

Normal migration executor:
```python
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
```

Simple sequential SQL execution with version tracking.

### `_apply_migration_fk_off(migration)`

FK-relaxed rebuild executor:
```python
async def _apply_migration_fk_off(migration: dict) -> None:
    """Apply a table-rebuild migration with FK enforcement relaxed."""
    conn = await engine.connect()
    try:
        await conn.execute(text("PRAGMA foreign_keys=OFF"))
        await conn.commit()
        async with conn.begin():
            for stmt in migration["up"].split(";"):
                stmt = stmt.strip()
                if stmt and stmt != "SELECT 1":
                    if await _src_table_missing(conn, stmt):
                        # Skip if source table gone (crash resume)
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
```

Handles complex rebuild scenarios with explicit transaction control and PRAGMA manipulation.

### `_verify_alter_columns(up_sql)`

Post-migration column verification (H10 fix):
```python
async def _verify_alter_columns(up_sql: str) -> bool:
    """Check that every ALTER TABLE ADD COLUMN in the migration is present."""
    alters = _ADD_COLUMN_RE.findall(up_sql)
    if not alters:
        return True
    async with engine.begin() as conn:
        for table, column in alters:
            if not await _columns_exist(conn, table, [column]):
                return False
    return True
```

Validates that reported "duplicate column" errors aren't masking real schema issues.

### `_src_table_missing(conn, stmt)`

Source table absence detector for resumable copies:
```python
async def _src_table_missing(conn, stmt: str) -> bool:
    """Return True when an INSERT...SELECT statement's source table is missing."""
    match = _INSERT_FROM_RE.search(stmt)
    if not match:
        return False
    src_table = match.group(1)
    result = await conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
    ))
    existing = {row[0] for row in result.fetchall()}
    return src_table not in existing
```

Used exclusively in rebuild migrations to skip COPY statements when source table dropped mid-rebuild.

---

## 8. Error Handling

### Error Categories

| Error Type | Handler | Outcome |
|------------|---------|---------|
| `duplicate column` | Verify columns exist, mark applied if verified | Silent skip |
| `already exists` | Same as duplicate column | Silent skip |
| `no such table` | Rebuild migrations skip statement (source table gone mid-rebuild) | Resume from checkpoint |
| Any other error | Propagate exception, rollback transaction | Fail upgrade |
| `IntegrityError` (unique violation) | Caught and logged as duplicate column scenario | Silent skip |

### Critical Failure Scenarios

1. **Power loss mid-rebuild**: Migration 017 resumable via WHERE EXISTS/NOT EXISTS guards
2. **Disk space exhaustion**: Transaction rolls back, schema unchanged, next restart retries
3. **Corrupt WAL file**: SQLite recovery mechanisms kick in (not migration-specific)
4. **Version lock conflict**: Two processes running simultaneously—one acquires lock, other waits or fails

### Logging Categories

- `aic.migrations`: Main migration execution events
- `aic.migrations.runner`: Specific runner-level warnings (skipped statements, resume events)
- `sqlalchemy.engine`: Underlying SQLAlchemy logging (optional, for debugging)

---

## 9. Metrics & Observability

### Generated Metrics

**Migration Timing**:
- Total migration duration (startup time impact)
- Per-migration execution time (identify slow DDL)
- Retry attempts (failed migrations retried?)

**Success/Failure Rates**:
- % migrations applied successfully on first attempt
- % migrations requiring error-tolerant skip
- % migrations resuming from partial rebuilds

**Operational Statistics**:
- Database age (first migration applied date)
- Total migrations applied count
- Oldest/newest migration versions

### Observability Hooks

**Logging Example**:
```
INFO - Applying migration 017: remove_discovery_sessions_conversation_fk
INFO -   Applied: Rebuild discovery_sessions without the FK on conversation_id
INFO - Applying migration 018: dedupe_providers_and_unique_name
INFO -   Skipped (already applied): dedupe_providers_and_unique_name
INFO - Database is up to date
```

**Warning Triggers**:
- Duplicate column errors (potential schema drift)
- Source table missing during rebuild (crash resume)
- Column verification failure (real migration failure masked as skip)

---

## 10. Testing Coverage

### Existing Tests

| Test Area | Coverage Focus |
|-----------|----------------|
| Unit tests | Migration parsing, regex patterns |
| Integration tests | Full migration run against test DB |
| Edge case tests | Duplicate column error recovery, resume scenarios |

### Missing Coverage Areas

- **Load Testing**: Migration performance with large tables (100K+ rows)
- **Rollback Testing**: Downward migrations not implemented (SELECT 1 only)
- **Concurrency Testing**: Multiple processes running migrations simultaneously
- **Partial-State Testing**: Simulate mid-migration crashes to verify recovery

---

## 11. Future Considerations

### Known Limitations

1. **No Down Migration Support**: `down` fields are `SELECT 1` no-ops—cannot rollback migrations
2. **No Schema Diff Generation**: Cannot auto-generate migration from model changes—manual SQL required
3. **Limited Error Recovery**: Only handles duplicate column gracefully; other failures abort entirely
4. **No Batch Support**: Migrations run sequentially one-by-one—not bulk atomic batch
5. **No Schema Versioning API**: No public API to query schema version beyond internal tracking
6. **SQLite-Only**: Not portable to PostgreSQL/MySQL without major rewrite
7. **No Pre/Migration Hooks**: Cannot run custom code before/after each migration

### Architectural Debt

1. **Monolithic Migration Definition**: All migrations in single list file—hard to maintain at scale
2. **Regex-Based Parsing**: Fragile SQL parsing (breaks on comments, nested parentheses)
3. **No Schema Validation**: No automated way to verify migrations produce expected schema
4. **Hardcoded Version Ordering**: List order determines execution—can't express dependencies between migrations
5. **Mixed Concerns**: Runner mixes logic (parsing, execution, verification) in single file

### Recommended Improvements

1. **Implement Down Migrations**: Add proper rollback SQL for destructive changes (though risky in practice)
2. **Schema Diff Generator**: Generate migration SQL from ORM model changes (like Alembic autogenerate)
3. **Migration Dependencies**: Express migration dependencies explicitly (migration B depends on A completing)
4. **Postgres Compatibility**: Abstract DDL syntax for multi-database support
5. **Validation Framework**: Automated schema assertion tests post-migration
6. **Batch Atomicity**: Group related migrations into batches for atomic commit
7. **Schema Version Endpoint**: Expose current schema version via HTTP API for deployment coordination
8. **Pre-Migration Scripts**: Allow custom Python hooks before migration execution

---

## Appendix A: Migration Version Reference

| Version | Name | SQL Operations | Table Impact |
|---------|------|----------------|--------------|
| 001 | `initial_schema` | CREATE ALL (via SQLAlchemy) | All tables |
| 002 | `add_worker_runtime_fields` | 4x ALTER TABLE ADD COLUMN | worker_runtime |
| 003 | `add_orchestration_tables` | 5x CREATE TABLE | orchestration_sessions, tasks, approvals, workflow_definitions, checkpoints |
| 004 | `add_job_scheduler_tables` | 2x CREATE TABLE | jobs, job_logs |
| 005 | `add_mcp_tables` | 3x CREATE TABLE | mcp_registry, mcp_tools, mcp_tool_executions |
| 006 | `add_memory_table` | 1x CREATE TABLE | memory_entries |
| 007 | `add_rag_tables` | 2x CREATE TABLE | rag_documents, rag_chunks |
| 008 | `add_automation_tables` | 3x CREATE TABLE | event_hooks, triggers, notifications |
| 009 | `add_project_id_to_conversations` | 1x ALTER TABLE ADD COLUMN + FK | conversations |
| 010 | `add_active_project_to_local_profile` | 1x ALTER TABLE ADD COLUMN + FK | local_profile |
| 011 | `add_approval_config_to_local_profile` | 1x ALTER TABLE ADD COLUMN (JSON) | local_profile |
| 012 | `repair_conversation_timestamps` | 4x UPDATE statements | messages, conversations |
| 013 | `deprecated_auto_detect_context` | SELECT 1 (no-op) | None |
| 014 | `add_context_cache_tracking` | 2x ALTER TABLE ADD COLUMN | provider_models |
| 015 | `add_user_id_to_conversations` | 1x ALTER TABLE ADD COLUMN + FK | conversations |
| 016 | `ensure_provider_models_table` | CREATE TABLE IF NOT EXISTS (full schema) | provider_models |
| 017 | `remove_discovery_sessions_conversation_fk` | CREATE IF NOT EXISTS, INSERT, DROP, ALTER RENAME, CREATE INDEX | discovery_sessions (rebuild) |
| 018 | `dedupe_providers_and_unique_name` | DELETE + CREATE UNIQUE INDEX | providers (cleanup + constraint) |
| 019 | `add_github_token_to_local_profile` | 1x ALTER TABLE ADD COLUMN | local_profile |
| 020 | `add_last_used_repo_path_to_local_profile` | 1x ALTER TABLE ADD COLUMN | local_profile |

### Most Complex Migrations

**Migration 017**: Table rebuild with crash recovery (most SQL statements, FK manipulation, resumability guards)  
**Migration 018**: Data cleanup + constraint enforcement (DELETE with nested subquery, conditional index creation)  
**Migration 016**: Table creation with full schema definition (complete column list, types, defaults)

---

## Appendix B: Regex Pattern Reference

| Pattern | Purpose | Example Match |
|---------|---------|---------------|
| `_ADD_COLUMN_RE` | Parse ALTER TABLE ADD COLUMN statements | `ALTER TABLE users ADD COLUMN email` → `(users, email)` |
| `_INSERT_FROM_RE` | Parse source table from INSERT...SELECT | `INSERT INTO t2 SELECT * FROM t1` → `t1` |

These enable dynamic statement analysis without full SQL parsing.

---

*This codemap provides complete technical documentation of the Backend Migrations module for developer reference, onboarding, and architectural audit.*
