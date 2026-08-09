"""AIC Platform — Configuration."""
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
    # AIC_IDENTITY_USERNAME / AIC_IDENTITY_PASSWORD env vars take precedence
    # over the file. Falls back to the defaults below only when neither env
    # nor file is present, so standalone/dev/tests keep working.
    AIC_IDENTITY_FILE: str = ""
    AIC_IDENTITY_USERNAME: str = ""
    AIC_IDENTITY_PASSWORD: str = ""
    DEFAULT_IDENTITY_USERNAME: str = "admin"
    DEFAULT_IDENTITY_PASSWORD: str = "admin123"
    IDENTITY_USERNAME: str = ""
    IDENTITY_PASSWORD: str = ""

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
                # M4: restrict the secret file to the owner only.
                try:
                    os.chmod(key_file, 0o600)
                except OSError:
                    pass
        # Load per-install identity written by the Electron main process.
        # Precedence: AIC_IDENTITY_* env vars > AIC_IDENTITY_FILE > defaults.
        env_username = (self.AIC_IDENTITY_USERNAME or "").strip()
        env_password = (self.AIC_IDENTITY_PASSWORD or "").strip()
        if env_username or env_password:
            self.IDENTITY_USERNAME = env_username or self.DEFAULT_IDENTITY_USERNAME
            self.IDENTITY_PASSWORD = env_password or self.DEFAULT_IDENTITY_PASSWORD
        elif self.AIC_IDENTITY_FILE and os.path.exists(self.AIC_IDENTITY_FILE):
            try:
                with open(self.AIC_IDENTITY_FILE, "r", encoding="utf-8") as f:
                    identity = json.load(f)
                self.IDENTITY_USERNAME = str(identity.get("username", "")).strip() or self.DEFAULT_IDENTITY_USERNAME
                self.IDENTITY_PASSWORD = str(identity.get("password", "")).strip() or self.DEFAULT_IDENTITY_PASSWORD
            except (OSError, json.JSONDecodeError):
                self.IDENTITY_USERNAME = self.DEFAULT_IDENTITY_USERNAME
                self.IDENTITY_PASSWORD = self.DEFAULT_IDENTITY_PASSWORD
        elif self.AIC_IDENTITY_FILE:
            # H8: AIC_IDENTITY_FILE is set but the file does not exist (e.g. the
            # Electron main process wrote it after we spawned). Mirror the
            # Electron loadOrCreateIdentity approach: generate a random password
            # on first run and persist it so restarts use the same identity.
            try:
                identity_path = Path(self.AIC_IDENTITY_FILE)
                identity_path.parent.mkdir(parents=True, exist_ok=True)
                self.IDENTITY_USERNAME = "admin"
                self.IDENTITY_PASSWORD = secrets.token_hex(16)
                identity_path.write_text(
                    json.dumps({"username": self.IDENTITY_USERNAME, "password": self.IDENTITY_PASSWORD}),
                    encoding="utf-8",
                )
                try:
                    os.chmod(identity_path, 0o600)
                except OSError:
                    pass
            except OSError as e:
                logger.warning(f"Could not persist generated identity file {self.AIC_IDENTITY_FILE}: {e}")
                self.IDENTITY_USERNAME = self.DEFAULT_IDENTITY_USERNAME
                self.IDENTITY_PASSWORD = self.DEFAULT_IDENTITY_PASSWORD
        else:
            # No AIC_IDENTITY_FILE and no AIC_IDENTITY_* env vars (standalone/
            # dev/tests). The default credentials are a known fallback — fail
            # startup completely to prevent insecure operation.
            raise ValueError(
                "AIC_IDENTITY_FILE is not set and no AIC_IDENTITY_USERNAME / "
                "AIC_IDENTITY_PASSWORD env vars are present. Set AIC_IDENTITY_FILE "
                "(or run via the Electron app) before starting the application."
            )


settings = Settings()
settings.ensure_dirs()
