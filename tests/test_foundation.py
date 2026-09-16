"""Unit tests for Stage 1: Project Foundation."""

import os
import sys
import pytest
from pathlib import Path
from PySide6.QtWidgets import QApplication

# Set headless environment for Qt tests
os.environ["QT_QPA_PLATFORM"] = "offscreen"


@pytest.fixture(scope="session")
def qapp():
    """Fixture to ensure a single QApplication exists for UI tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_settings_initialization():
    """Verify settings defaults and directory creation."""
    from app.core.config import Settings

    custom_settings = Settings()
    assert custom_settings.app_name == "Telegram File Explorer"
    assert custom_settings.app_version == "0.1.0"
    assert custom_settings.data_dir.exists()
    assert custom_settings.logs_dir.exists()
    assert custom_settings.sessions_dir.exists()
    assert custom_settings.download_dir.exists()


def test_logger_setup():
    """Verify logger configuration and log file creation."""
    from app.core.logger import setup_logging, get_logger

    logger = setup_logging("DEBUG")
    assert logger is not None
    test_child = get_logger("test")
    test_child.info("Test log entry")

    from app.core.config import settings
    log_file = settings.logs_dir / "app.log"
    assert log_file.exists()


def test_main_window_initialization(qapp):
    """Verify MainWindow initializes without errors in offscreen mode."""
    from app.ui.main_window import MainWindow

    window = MainWindow()
    assert window is not None
    assert "Telegram File Explorer" in window.windowTitle()
    assert window.centralWidget() is not None
    assert window.statusBar() is not None
    window.close()


def test_local_credentials_storage(tmp_path):
    """Verify local credentials can be saved and loaded strictly on local computer."""
    from app.core.config import Settings

    settings = Settings()
    # Use temporary data dir
    settings.data_dir = tmp_path
    settings.sessions_dir = tmp_path / "sessions"
    settings.ensure_directories()

    # Save credentials locally
    success = settings.save_local_credentials(12345678, "abcdef0123456789abcdef0123456789")
    assert success is True
    assert (tmp_path / "config.json").exists()

    # Create new instance pointing to same tmp_path
    new_settings = Settings()
    new_settings.data_dir = tmp_path
    new_settings._load_local_config()
    assert new_settings.api_id == 12345678
    assert new_settings.api_hash == "abcdef0123456789abcdef0123456789"
    assert new_settings.is_telegram_configured is True

    # Clear credentials
    new_settings.clear_local_credentials()
    assert not (tmp_path / "config.json").exists()

