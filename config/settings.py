"""CareerOS configuration management.

Loads settings from environment variables and .env file.
All settings have sensible defaults for local development.
Never hard-codes secrets or machine-specific paths.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

# Project root is one level up from config/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _env_int(key: str, default: int = 0) -> int:
    val = os.environ.get(key)
    if val is None:
        return default
    try:
        return int(val)
    except ValueError:
        return default


def _env_float(key: str, default: float = 0.0) -> float:
    val = os.environ.get(key)
    if val is None:
        return default
    try:
        return float(val)
    except ValueError:
        return default


def _env_bool(key: str, default: bool = False) -> bool:
    val = os.environ.get(key)
    if val is None:
        return default
    return val.lower() in ("true", "1", "yes")


@dataclass
class DatabaseSettings:
    """SQLite database configuration."""
    path: str = ""

    def __post_init__(self):
        if not self.path:
            self.path = str(PROJECT_ROOT / "data" / "careeros.db")


@dataclass
class AISettings:
    """AI provider configuration. AI is disabled when provider or key is empty."""
    provider: str = ""          # 'openai' or 'google'
    api_key: str = ""
    model: str = "gpt-4o-mini"
    max_tokens: int = 4096
    monthly_budget: float = 10.0

    @property
    def enabled(self) -> bool:
        return bool(self.provider and self.api_key)


@dataclass
class APISettings:
    """Local API settings for Chrome extension communication."""
    host: str = "127.0.0.1"
    port: int = 8400
    secret: str = ""


@dataclass
class LoggingSettings:
    """Logging configuration."""
    level: str = "INFO"
    log_file: str = ""

    def __post_init__(self):
        if not self.log_file:
            self.log_file = str(PROJECT_ROOT / "logs" / "careeros.log")


@dataclass
class Settings:
    """Root application settings. Created once via Settings.load()."""

    project_root: Path = field(default_factory=lambda: PROJECT_ROOT)
    data_dir: str = ""
    uploads_dir: str = ""
    exports_dir: str = ""
    backups_dir: str = ""

    database: DatabaseSettings = field(default_factory=DatabaseSettings)
    ai: AISettings = field(default_factory=AISettings)
    api: APISettings = field(default_factory=APISettings)
    logging: LoggingSettings = field(default_factory=LoggingSettings)

    def __post_init__(self):
        if not self.data_dir:
            self.data_dir = str(PROJECT_ROOT / "data")

        self.uploads_dir = os.path.join(self.data_dir, "uploads")
        self.exports_dir = os.path.join(self.data_dir, "exports")
        self.backups_dir = os.path.join(self.data_dir, "backups")

        # Ensure directories exist
        for dir_path in (self.data_dir, self.uploads_dir, self.exports_dir,
                         self.backups_dir):
            os.makedirs(dir_path, exist_ok=True)

        log_dir = os.path.dirname(self.logging.log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

    @classmethod
    def load(cls) -> "Settings":
        """Load settings from environment variables."""
        return cls(
            data_dir=_env("CAREEROS_DATA_DIR"),
            database=DatabaseSettings(path=_env("CAREEROS_DB_PATH")),
            ai=AISettings(
                provider=_env("CAREEROS_AI_PROVIDER"),
                api_key=_env("CAREEROS_AI_API_KEY"),
                model=_env("CAREEROS_AI_MODEL", "gpt-4o-mini"),
                max_tokens=_env_int("CAREEROS_AI_MAX_TOKENS", 4096),
                monthly_budget=_env_float("CAREEROS_AI_MONTHLY_BUDGET", 10.0),
            ),
            api=APISettings(
                host=_env("CAREEROS_API_HOST", "127.0.0.1"),
                port=_env_int("CAREEROS_API_PORT", 8400),
                secret=_env("CAREEROS_API_SECRET"),
            ),
            logging=LoggingSettings(
                level=_env("CAREEROS_LOG_LEVEL", "INFO"),
                log_file=_env("CAREEROS_LOG_FILE"),
            ),
        )


# ── Global singleton ─────────────────────────────────────────
settings = Settings.load()
