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
    thumbnails_dir: Path = field(default_factory=lambda: BASE_DIR / "data" / "cache" / "thumbnails")

    @property
    def thumbnail_dir(self) -> Path:
        return self.thumbnails_dir

    # Telegram Credentials
    api_id: Optional[int] = None
    api_hash: Optional[str] = None
    session_name: str = "telegram_user"

    # Application Settings
    app_name: str = "Telegram File Explorer"
    app_version: str = "0.1.0"
    log_level: str = "INFO"
    app_theme: str = "dark"
    max_concurrent_downloads: int = 3

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

        # Load local settings if .env did not supply credentials
        self._load_local_config()

    def ensure_directories(self) -> None:
        """Create required runtime directories if they do not exist."""
        for path in [self.data_dir, self.download_dir, self.logs_dir, self.sessions_dir]:
            path.mkdir(parents=True, exist_ok=True)

    @property
    def local_config_path(self) -> Path:
        """Path to local user configuration file (kept strictly on local device)."""
        return self.data_dir / "config.json"

    def _load_local_config(self) -> None:
        """Load API credentials and preferences from local config.json if available."""
        if not self.local_config_path.exists():
            return

        try:
            import json
            with open(self.local_config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if "api_id" in data and data["api_id"]:
                try:
                    self.api_id = int(data["api_id"])
                except (ValueError, TypeError):
                    pass

            if "api_hash" in data and data["api_hash"]:
                self.api_hash = str(data["api_hash"]).strip() or None

            if "session_name" in data and data["session_name"]:
                self.session_name = str(data["session_name"]).strip()

            if "download_dir" in data and data["download_dir"]:
                self.download_dir = Path(data["download_dir"]).resolve()

        except Exception:
            pass

    def save_local_credentials(self, api_id: int, api_hash: str) -> bool:
        """Save API credentials locally into data/config.json (100% on user's machine)."""
        import json
        self.api_id = int(api_id)
        self.api_hash = str(api_hash).strip()
        self.ensure_directories()

        data = {
            "api_id": self.api_id,
            "api_hash": self.api_hash,
            "session_name": self.session_name,
            "download_dir": str(self.download_dir),
        }

        try:
            with open(self.local_config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            harden_file_permissions(self.local_config_path)
            return True
        except Exception:
            return False

    def clear_local_credentials(self) -> None:
        """Clear credentials from memory and local file."""
        self.api_id = None
        self.api_hash = None
        if self.local_config_path.exists():
            try:
                self.local_config_path.unlink()
            except Exception:
                pass

    def wipe_local_credentials_and_sessions(self) -> dict:
        """Securely wipe all local session files, credentials, and databases."""
        deleted = {"config": False, "sessions": 0, "databases": 0}
        self.clear_local_credentials()
        deleted["config"] = True

        # Wipe session files
        if self.sessions_dir.exists():
            for f in self.sessions_dir.glob(f"{self.session_name}*"):
                try:
                    f.unlink()
                    deleted["sessions"] += 1
                except Exception:
                    pass

        # Wipe database files
        if self.data_dir.exists():
            for f in self.data_dir.glob("*.db*"):
                try:
                    f.unlink()
                    deleted["databases"] += 1
                except Exception:
                    pass

        return deleted

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


def harden_file_permissions(path: Path) -> None:
    """Ensure sensitive local secrets or session files have restricted read/write permissions."""
    if not path.exists():
        return
    try:
        if os.name != "nt":
            os.chmod(path, 0o600)
    except Exception:
        pass


# Singleton instance
settings = Settings()
