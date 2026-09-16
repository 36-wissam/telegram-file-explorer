"""Configuration management system for Telegram File Explorer."""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

# Base directory (project root)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load .env file from base directory if present
load_dotenv(BASE_DIR / ".env")


@dataclass
class Settings:
    """Application settings loaded from environment or defaults."""

    # Project Paths
    base_dir: Path = BASE_DIR
    data_dir: Path = field(default_factory=lambda: BASE_DIR / "data")
    download_dir: Path = field(default_factory=lambda: BASE_DIR / "downloads")
    logs_dir: Path = field(default_factory=lambda: BASE_DIR / "logs")
    sessions_dir: Path = field(default_factory=lambda: BASE_DIR / "data" / "sessions")

    # Telegram Credentials
    api_id: Optional[int] = None
    api_hash: Optional[str] = None
    session_name: str = "telegram_user"

    # Application Settings
    app_name: str = "Telegram File Explorer"
    app_version: str = "0.1.0"
    log_level: str = "INFO"
    app_theme: str = "dark"

    def __post_init__(self):
        # Override with environment variables if present
        raw_api_id = os.getenv("TELEGRAM_API_ID", "").strip()
        if raw_api_id:
            try:
                self.api_id = int(raw_api_id)
            except ValueError:
                self.api_id = None

        self.api_hash = os.getenv("TELEGRAM_API_HASH", "").strip() or None
        self.session_name = os.getenv("TELEGRAM_SESSION_NAME", self.session_name).strip()

        env_data_dir = os.getenv("DATA_DIR", "").strip()
        if env_data_dir:
            self.data_dir = (self.base_dir / env_data_dir).resolve() if not os.path.isabs(env_data_dir) else Path(env_data_dir)
            self.sessions_dir = self.data_dir / "sessions"

        env_download_dir = os.getenv("DOWNLOAD_DIR", "").strip()
        if env_download_dir:
            self.download_dir = (self.base_dir / env_download_dir).resolve() if not os.path.isabs(env_download_dir) else Path(env_download_dir)

        self.log_level = os.getenv("LOG_LEVEL", self.log_level).upper()
        self.app_theme = os.getenv("APP_THEME", self.app_theme).lower()

        # Ensure required directories exist
        self.ensure_directories()

    def ensure_directories(self) -> None:
        """Create required runtime directories if they do not exist."""
        for path in [self.data_dir, self.download_dir, self.logs_dir, self.sessions_dir]:
            path.mkdir(parents=True, exist_ok=True)

    @property
    def is_telegram_configured(self) -> bool:
        """Check if minimum Telegram API credentials are provided."""
        return bool(self.api_id and self.api_hash)

    @property
    def session_path(self) -> Path:
        """Path to Telethon session storage file."""
        return self.sessions_dir / self.session_name

    @property
    def database_path(self) -> Path:
        """Path to primary SQLite database file."""
        return self.data_dir / "explorer.db"


# Singleton instance
settings = Settings()
