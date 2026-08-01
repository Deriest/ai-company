"""AIC Platform — Configuration."""
from pathlib import Path
from pydantic_settings import BaseSettings
import os
import secrets
import json


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
                    return data.get("version", "2.4.20")
            except (json.JSONDecodeError, KeyError):
                pass
    return "2.4.20"


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}
    # Core
    APP_NAME: str = "AIC Platform"
    VERSION: str = _read_version_from_package_json()
    DEBUG: bool = True

    # Database — absolute path is set after ensure_dirs when AIC_DATA_DIR is present
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/aic.db"
    DB_ECHO: bool = False

    # Auth — auto-generates secure key if not in env
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24h
    API_KEY_HEADER: str = "X-API-Key"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173",
        "http://192.168.2.10:8000", "http://localhost:8000",
        "http://127.0.0.1:5174", "http://localhost:5174",
        "*",  # ponytail: wildcard for LAN/dev; lock down if exposing public
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

    # Runtime
    WORKER_TIMEOUT: int = 600  # seconds
    BARRIER_TIMEOUT: int = 600  # seconds
    MAX_RECOVERY_ATTEMPTS: int = 3

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
        # Auto-generate secure JWT secret if not set via env
        if not self.SECRET_KEY:
            key_file = self.DATA_DIR / ".jwt_secret"
            if key_file.exists():
                self.SECRET_KEY = key_file.read_text().strip()
            else:
                self.SECRET_KEY = secrets.token_hex(32)
                key_file.write_text(self.SECRET_KEY)


settings = Settings()
settings.ensure_dirs()
