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
