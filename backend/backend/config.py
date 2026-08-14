"""AIC-ADE configuration settings.

Single-user desktop application configuration:
- All paths are local to user's machine
- Database is SQLite file on disk
- LLM provider config stored in environment variables
- No multi-tenant or distributed mode support
"""
import os
from pathlib import Path


class Settings:
    """Configuration for AIC-ADE single-user desktop app."""
    
    # Application Paths (Local Only)
    DATA_DIR = Path(os.getenv("AIC_DATA_DIR", str(Path.home() / ".local" / "share" / "aic")))
    WORKSPACE_DIR = os.getenv("AIC_WORKSPACE_DIR", str(DATA_DIR / "workspaces"))
    BACKUP_DIR = os.getenv("AIC_BACKUP_DIR", str(DATA_DIR / "backups"))
    
    # Database Configuration (SQLite Local File)
    _raw_db = os.getenv("AIC_DATABASE_URL") or str(DATA_DIR / "aic_ade.db")
    # Normalize into a valid async SQLAlchemy URL. session.py strips the
    # "sqlite+aiosqlite:///" scheme to chmod the db file, so a bare-path
    # fallback must be given the driver prefix here.
    DATABASE_URL = _raw_db if "://" in _raw_db else "sqlite+aiosqlite:///" + _raw_db
    SQLITE_BUSY_TIMEOUT_MS = int(os.getenv("AIC_SQLITE_BUSY_TIMEOUT_MS", "5000"))  # 5 seconds
    
    # Worker Configuration (Single-User Execution)
    DEFAULT_LEASE_TIMEOUT_MINUTES = int(os.getenv("AIC_DEFAULT_LEASE_TIMEOUT_MINUTES", "30"))  # Configurable, default 30min
    MAX_WORKER_CONCURRENCY = int(os.getenv("AIC_MAX_WORKER_CONCURRENCY", "4"))  # Max parallel workers per task
    WORKER_RETRY_ATTEMPTS = int(os.getenv("AIC_WORKER_RETRY_ATTEMPTS", "3"))  # Per-worker retry count
    
    # Task Execution Settings
    DEFAULT_TASK_TIMEOUT_SECONDS = int(os.getenv("AIC_DEFAULT_TASK_TIMEOUT_SECONDS", "1800"))  # 30 min default
    TASK_PROGRESS_UPDATE_INTERVAL = int(os.getenv("AIC_TASK_PROGRESS_UPDATE_INTERVAL", "5"))  # Update every 5s
    
    # LLM Provider Configuration (Single Endpoint)
    AIC_LLM_BASE_URL = os.getenv("AIC_LLM_BASE_URL", "")
    AIC_LLM_API_KEY = os.getenv("AIC_LLM_API_KEY", "")
    AIC_LLM_PROVIDER_NAME = os.getenv("AIC_LLM_PROVIDER_NAME", "")
    AIC_MODEL_CRAFTER = os.getenv("AIC_MODEL_CRAFTER", "")
    AIC_MODEL_THINKER = os.getenv("AIC_MODEL_THINKER", "")
    AIC_MODEL_SPRINTER = os.getenv("AIC_MODEL_SPRINTER", "")
    AIC_MODEL_VISION = os.getenv("AIC_MODEL_VISION", "")
    AIC_LLM_REASONING_EFFORT = os.getenv("AIC_LLM_REASONING_EFFORT", "auto")
    AIC_LLM_MAX_CONCURRENT_REQUESTS = int(os.getenv("AIC_LLM_MAX_CONCURRENT_REQUESTS", "4"))
    
    # Encryption Settings
    ENCRYPTION_KEY_ROTATION_DAYS = int(os.getenv("AIC_ENCRYPTION_KEY_ROTATION_DAYS", "90"))  # Optional rotation schedule
    SECRET_BACKUP_COUNT = int(os.getenv("AIC_SECRET_BACKUP_COUNT", "3"))  # Number of backup copies to keep
    
    # Backup & Restore
    AUTO_BACKUP_ENABLED = os.getenv("AIC_AUTO_BACKUP_ENABLED", "false").lower() == "true"
    AUTO_BACKUP_SCHEDULE = os.getenv("AIC_AUTO_BACKUP_SCHEDULE", "weekly")  # daily, weekly, monthly
    BACKUP_RETENTION_DAYS = int(os.getenv("AIC_BACKUP_RETENTION_DAYS", "30"))
    
    # Logging & Observability (Single User)
    LOG_LEVEL = os.getenv("AIC_LOG_LEVEL", "INFO")
    ENABLE_STRUCTURED_LOGGING = os.getenv("AIC_ENABLE_STRUCTURED_LOGGING", "true").lower() == "true"
    METRICS_ENABLED = os.getenv("AIC_METRICS_ENABLED", "true").lower() == "true"
    
    # Security (Local Trust Model)
    LOCALHOST_ONLY = True  # Bind to 127.0.0.1 only - no remote access
    CORS_ORIGINS = ["http://localhost:5173", "http://localhost:5174"]  # Electron dev server URLs only
    JWT_SECRET_KEY = None  # For future use; not enforced in single-user mode
    AUTH_FAIL_OPEN_DETECTION = True  # Always check for AIC_TESTING=1 at runtime

    # JWT — consumed by auth/security.py (create_access_token / decode).
    # Kept compatible: read both new AIC_JWT_SECRET and legacy SECRET_KEY names.
    @property
    def SECRET_KEY(self) -> str:
        return os.getenv("AIC_JWT_SECRET") or os.getenv("SECRET_KEY") or "dev-local-only-aic-ade-please-set-AIC_JWT_SECRET-in-prod-0000"

    @property
    def ALGORITHM(self) -> str:
        return os.getenv("AIC_JWT_ALGORITHM", "HS256")

    @property
    def ACCESS_TOKEN_EXPIRE_MINUTES(self) -> int:
        return int(os.getenv("AIC_JWT_EXPIRE_MINUTES", "1440"))  # 24h default


    # Desktop identity — per-install random credential in AIC_IDENTITY_FILE.
    # Electron writes identity.json; tests may override via env.
    @property
    def IDENTITY_USERNAME(self) -> str:
        if os.getenv("AIC_IDENTITY_USERNAME"):
            return os.environ["AIC_IDENTITY_USERNAME"]
        pp = os.getenv("AIC_IDENTITY_FILE")
        if pp:
            try:
                import json as _json
                d = _json.loads(Path(pp).read_text(encoding="utf-8"))
                if isinstance(d.get("username"), str) and d["username"]:
                    return d["username"]
            except Exception:
                pass
        return "admin"

    @property
    def IDENTITY_PASSWORD(self) -> str:
        if os.getenv("AIC_IDENTITY_PASSWORD"):
            return os.environ["AIC_IDENTITY_PASSWORD"]
        pp = os.getenv("AIC_IDENTITY_FILE")
        if pp:
            try:
                import json as _json
                d = _json.loads(Path(pp).read_text(encoding="utf-8"))
                if isinstance(d.get("password"), str) and d["password"]:
                    return d["password"]
            except Exception:
                pass
        return "admin123"

    
    # App version (main.py exposes it in the FastAPI banner / /health).
    # Injected by the Electron main process via AIC_APP_VERSION when packaged.
    VERSION = os.getenv("AIC_APP_VERSION", "2.6.21")
    
    @property
    def database_path(self) -> Path:
        """Return full path to SQLite database file."""
        url = self.DATABASE_URL.replace("sqlite+aiosqlite:///", "").split("?")[0]
        return Path(url).resolve()
    
    @property
    def is_testing_mode(self) -> bool:
        """Check if testing mode is enabled (should never be true in production)."""
        return os.environ.get("AIC_TESTING") == "1"
    
    def validate(self) -> list[str]:
        """Validate configuration and return list of warnings/errors."""
        errors = []
        
        # Critical validation
        if self.is_testing_mode:
            errors.append(
                "CRITICAL: AIC_TESTING=1 detected! This should NEVER be set in production. "
                "Authentication bypass is ACTIVE."
            )
        
        # Warnings (not blocking)
        if not self.AIC_LLM_BASE_URL:
            errors.append("WARNING: AIC_LLM_BASE_URL not set — LLM providers may fail")
        
        if not self.DATA_DIR.exists():
            try:
                self.DATA_DIR.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                errors.append(f"ERROR: Cannot create data directory {self.DATA_DIR}: {e}")
        
        if self.WORKSPACE_DIR != str(self.DATA_DIR / "workspaces"):
            # Custom workspace dir
            pass
        
        return errors


# Singleton instance
settings = Settings()


# ── Module-level constants ─────────────────────────────────────────────
# These previously lived in backend/config/constants.py (a package dir that
# collided with this config.py module for the import name "backend.config").
# The module wins that name at runtime, so the constants are hosted here.
HTTP_TIMEOUT_MS = 120000                # 120s for LLM requests
DB_LOCK_RETRY_ATTEMPTS = 6
DB_LOCK_BASE_DELAY = 0.05
ADAPTIVE_TIMEOUT_MULTIPLIERS = {
    "thinker": 2.5,
    "crafter": 2.5,
    "sprinter": 1.5,
}
DEFAULT_WORKER_LEASE_TIMEOUT_MINUTES = 30
LLM_MAX_CONCURRENT_REQUESTS = 4
AGENT_RUN_SEMAPHORE_LIMIT = 2
API_REQUEST_TIMEOUT = 30
USAGE_TRACKER_MAX_RECORDS = 10000
CLARIFY_QUESTION_LIMIT = 10
MAX_ATTACHMENT_SIZE_BYTES = 25 * 1024 * 1024
