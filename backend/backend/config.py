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
    DATABASE_URL = os.getenv("AIC_DATABASE_URL", str(DATA_DIR / "aic_ade.db"))
    SQLITE_BUSY_TIMEOUT_MS = int(os.getenv("AIC_SQLITE_BUSY_TIMEOUT_MS", "5000"))  # 5 seconds
    
    # Worker Configuration (Single-User Execution)
    DEFAULT_LEASE_TIMEOUT_MINUTES = int(os.getenv("AIC_DEFAULT_LEASE_TIMEOUT_MINUTES", "30"))  # Configurable, default 30min
    MAX_WORKER_CONCURRENCY = int(os.getenv("AIC_MAX_WORKER_CONCURRENCY", "4"))  # Max parallel workers per task
    WORKER_RETRY_ATTEMPTS = int(os.getenv("AIC_WORKER_RETRY_ATTEMPTS", "3"))  # Per-worker retry count
    
    # Task Execution Settings
    DEFAULT_TASK_TIMEOUT_SECONDS = int(os.getenv("AIC_DEFAULT_TASK_TIMEOUT_SECONDS", "1800"))  # 30 min default
    TASK_PROGRESS_UPDATE_INTERVAL = int(os.getenv("AIC_TASK_PROGRESS_UPDATE_INTERVAL", "5"))  # Update every 5s
    
    # LLM Provider Configuration (Single Endpoint)
    LLM_BASE_URL = os.getenv("AIC_LLM_BASE_URL", "")
    LLM_API_KEY = os.getenv("AIC_LLM_API_KEY", "")
    LLM_MODEL_CRAFTER = os.getenv("AIC_MODEL_CRAFTER", "")
    LLM_MODEL_THINKER = os.getenv("AIC_MODEL_THINKER", "")
    LLM_MODEL_SPRINTER = os.getenv("AIC_MODEL_SPRINTER", "")
    LLM_REASONING_EFFORT = os.getenv("AIC_LLM_REASONING_EFFORT", "auto")
    LLM_MAX_CONCURRENT_REQUESTS = int(os.getenv("AIC_LLM_MAX_CONCURRENT_REQUESTS", "4"))
    
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
    
    @property
    def database_path(self) -> Path:
        """Return full path to SQLite database file."""
        return Path(self.DATABASE_URL).resolve()
    
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
        if not self.LLM_BASE_URL:
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
