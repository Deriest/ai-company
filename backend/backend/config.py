"""AIC Platform — Configuration.

Licensed under MIT License - See LICENSE file for details.
"""
from pathlib import Path
from pydantic_settings import BaseSettings
import os
import secrets
import json
import logging

logger = logging.getLogger(__name__)


def _resolve_data_dir(base_dir: Path) -> Path:
    """Prefer AIC_DATA_DIR (packaged desktop userData) over repo-local data/."""
    env = os.environ.get("AIC_DATA_DIR", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return base_dir / "data"


def _read_version_from_package_json() -> str:
    """Read version from app/package.json if available, fallback to hardcoded."""
    # Try multiple possible locations for package.json
    candidates = [
        Path(__file__).parent.parent.parent / "app" / "package.json",  # backend/../app/package.json
        Path(__file__).parent.parent / "package.json",  # backend/package.json
        Path.cwd() / "app" / "package.json",
        Path.cwd() / "package.json",
    ]
    for path in candidates:
        if path.exists():
            try:
                with open(path) as f:
                    data = json.load(f)
                    return data.get("version", "unknown")
            except (json.JSONDecodeError, KeyError):
                pass
    return "unknown"


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}
    # Core
    APP_NAME: str = "AIC Platform"
    VERSION: str = _read_version_from_package_json()
    DEBUG: bool = False

    # Database — absolute path is set after ensure_dirs when AIC_DATA_DIR is present
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/aic.db"
    DB_ECHO: bool = False

    # Auth — auto-generates secure key if not in env
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24h
    API_KEY_HEADER: str = "X-API-Key"

    # Per-install desktop identity — written by the Electron main process
    # to userData/aic-ade/identity.json and passed via AIC_IDENTITY_FILE.
    # Environment variables take precedence over the file.
    # DEFAULT_* constants are DEPRECATED test-only placeholders; do not use.
    AIC_IDENTITY_FILE: str = ""
    AIC_IDENTITY_USERNAME: str = ""
    AIC_IDENTITY_PASSWORD: str = ""
    # DEPRECATED: Test-only fallbacks, should NEVER be used in production.
    # Removed from practical use - startup fails without valid identity.

    # Server — desktop-only: bind to localhost; never expose on the LAN.
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:5174", "http://localhost:5174",
    ]

    # OpenCode
    OPENCODE_BIN: str = "opencode"
    OPENCODE_TIMEOUT: int = 600  # 10 min per worker

    # LLM (OpenAI-compatible)
    AIC_LLM_BASE_URL: str = ""
    AIC_LLM_API_KEY: str = ""
    AIC_LLM_PROVIDER_NAME: str = "default"
    AIC_MODEL_THINKER: str = ""
    AIC_MODEL_CRAFTER: str = ""
    AIC_MODEL_SPRINTER: str = ""
    AIC_MODEL_VISION: str = ""

    # Runtime
    WORKER_TIMEOUT: int = 600  # seconds
    BARRIER_TIMEOUT: int = 600  # seconds
    MAX_RECOVERY_ATTEMPTS: int = 3
    # PHASE 2 FIX: Configurable max iterations for agent runs
    MAX_AGENT_ITERATIONS: int = 20  # Increased from 10 to support multi-phase tasks

    # Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: Path = _resolve_data_dir(BASE_DIR)
    TASKS_DIR: Path = DATA_DIR / "tasks"
    WORKSPACE_DIR: Path = DATA_DIR / "workspace"

    def ensure_dirs(self):
        """Create required directories and pin DB to writable data dir."""
        self.DATA_DIR = _resolve_data_dir(self.BASE_DIR)
        self.TASKS_DIR = self.DATA_DIR / "tasks"
        self.WORKSPACE_DIR = self.DATA_DIR / "workspace"
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.TASKS_DIR.mkdir(parents=True, exist_ok=True)
        self.WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
        # Force absolute SQLite path so packaged installs never write into read-only resources
        db_path = (self.DATA_DIR / "aic.db").resolve()
        self.DATABASE_URL = f"sqlite+aiosqlite:///{db_path}"
        # CRITICAL GAP-1 FIX: JWT secret MUST be provided via environment variable
        # Remove file-based fallback to prevent accidental Git commits and enable rotation
        from os import environ
        
        if "AIC_JWT_SECRET" not in environ:
            raise ValueError(
                """
JWT_SECRET must be provided via AIC_JWT_SECRET environment variable!

Generate a secure 32+ character secret with:
    python -c "import secrets; print(secrets.token_hex(32))"

Set it like:
    export AIC_JWT_SECRET=$(python -c "import secrets; print(secrets.token_hex(32))")

In production deployments (Docker, systemd, etc.), set AIC_JWT_SECRET in your
environment configuration. NEVER store secrets in files or commit them to Git.
""".strip()
            )
        
        self.SECRET_KEY = environ["AIC_JWT_SECRET"]
        
        # Validate minimum length for cryptographic security
        if len(self.SECRET_KEY) < 32:
            raise ValueError(
                f"JWT_SECRET too short (minimum 32 characters required, got {len(self.SECRET_KEY)})"
            )
            
        # Optional: Warn about non-alphanumeric characters
        if not all(c.isalnum() for c in self.SECRET_KEY):
            logger.warning(
                "AIC_JWT_SECRET contains non-alphanumeric characters. "
                "This is supported but consider using only [a-zA-Z0-9] for maximum compatibility."
            )
        
        # Load per-install identity written by the Electron main process.
        # Precedence: AIC_IDENTITY_* env vars > AIC_IDENTITY_FILE.
        # Fail closed if neither is available — no fallback to defaults.
        env_username = (self.AIC_IDENTITY_USERNAME or "").strip()
        env_password = (self.AIC_IDENTITY_PASSWORD or "").strip()
        
        if env_username and env_password:
            # Both provided via env vars
            self.IDENTITY_USERNAME = env_username
            self.IDENTITY_PASSWORD = env_password
            
        elif self.AIC_IDENTITY_FILE and os.path.exists(self.AIC_IDENTITY_FILE):
            try:
                with open(self.AIC_IDENTITY_FILE, "r", encoding="utf-8") as f:
                    identity = json.load(f)
                
                username = str(identity.get("username", "")).strip()
                password = str(identity.get("password", "")).strip()
                
                # H4 FIX: Fail closed if identity file is missing required fields
                if not username or not password:
                    raise ValueError(
                        "Identity file exists but is incomplete: "
                        "missing 'username' and/or 'password' fields"
                    )
                
                self.IDENTITY_USERNAME = username
                self.IDENTITY_PASSWORD = password
                
            except (OSError, json.JSONDecodeError) as e:
                logger.error(
                    "Failed to read/parse identity file %s: %s",
                    self.AIC_IDENTITY_FILE, e
                )
                raise ValueError(
                    f"Identity file corrupted or unreadable: {e}. "
                    "Check file permissions and JSON structure."
                ) from e
            
        else:
            # M10: No identity provided - fail startup completely
            raise ValueError(
                "No identity configuration found. Set either:\n"
                "  - AIC_IDENTITY_FILE environment variable pointing to identity.json,\n"
                "  - AIC_IDENTITY_USERNAME and AIC_IDENTITY_PASSWORD environment variables.\n\n"
                "The Electron app automatically creates identity.json in userData on first run."
            )


settings = Settings()
settings.ensure_dirs()
