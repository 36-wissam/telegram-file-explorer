"""Shared fixtures for pytest."""

import os
import sys
import pytest
from PySide6.QtWidgets import QApplication

os.environ["QT_QPA_PLATFORM"] = "offscreen"


@pytest.fixture(scope="session")
def qapp():
    """Ensure a single QApplication instance for UI tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app
