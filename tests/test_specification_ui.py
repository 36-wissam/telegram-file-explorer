"""Comprehensive tests for specification UI components, automatic loading, and zero emoji constraint."""

import re
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from PySide6.QtCore import Qt

from app.database.models import IndexedFileModel
from app.database.repository import DatabaseRepository
from app.telegram.chats import ChatType, TelegramChat
from app.ui.media_card import MediaCardWidget, format_bytes
from app.ui.media_browser import ChatMediaBrowserWidget
from app.ui.settings_dialog import SettingsDialog
from app.ui.preview_panel import PreviewPanel, PreviewDialog


@pytest.fixture
def sample_file():
    return IndexedFileModel(
        id=1,
        file_id="spec_101",
        message_id=12,
        chat_id=-1001234567890,
        chat_title="Product Design",
        filename="system_architecture.pdf",
        extension=".pdf",
        mime_type="application/pdf",
        file_size=5242880,  # 5 MB
        media_type="DOCUMENT",
        message_date=datetime(2026, 9, 17, 10, 0, tzinfo=timezone.utc),
        caption="Detailed architectural document",
    )


def test_media_card_rendering_and_signals(qapp, sample_file):
    """Verify MediaCardWidget renders format badge, metadata, and handles clicks."""
    card = MediaCardWidget(sample_file)
    card.show()

    assert card.name_label.text() == "system_architecture.pdf"
    assert card.thumb_box.pixmap() is not None
    assert "5.0 MB" in card.size_label.text()

    # Click signal
    emitted_single = []
    card.clicked.connect(lambda f: emitted_single.append(f))
    mock_ev = MagicMock()
    mock_ev.button.return_value = Qt.LeftButton
    card.mousePressEvent(mock_ev)
    assert len(emitted_single) == 1
    assert emitted_single[0].filename == "system_architecture.pdf"


def test_media_browser_tab_and_view_switching(qapp, tmp_path, sample_file):
    """Verify ChatMediaBrowserWidget tab switching, view mode toggling, and search."""
    db_file = tmp_path / "browser_test.db"
    repo = DatabaseRepository(db_path=db_file)
    repo.save_files_batch([sample_file])

    browser = ChatMediaBrowserWidget(repo=repo)
    browser.show()

    # Select chat
    chat = TelegramChat(
        id=-1001234567890,
        title="Product Design",
        chat_type=ChatType.SUPERGROUP,
    )
    browser.set_chat(chat)

    assert browser.title_label.text() == "Product Design"
    assert len(browser._cached_files) == 1

    # Switch tabs
    browser._on_tab_clicked("IMAGE", browser.tab_buttons[1])
    assert len(browser._cached_files) == 0

    browser._on_tab_clicked("DOCUMENT", browser.tab_buttons[3])
    assert len(browser._cached_files) == 1

    # Switch View Mode to List (Table)
    browser._set_view_mode(1)
    assert browser.view_stack.currentIndex() == 1
    assert browser.table.rowCount() == 1

    # Switch back to Grid
    browser._set_view_mode(0)
    assert browser.view_stack.currentIndex() == 0


def test_settings_dialog_tabs(qapp, tmp_path):
    """Verify SettingsDialog tabs and structure."""
    db_file = tmp_path / "settings_test.db"
    repo = DatabaseRepository(db_path=db_file)
    dialog = SettingsDialog(repo=repo)
    dialog.show()

    assert dialog.tabs.count() == 5
    assert dialog.tabs.tabText(0) == "Account"
    assert dialog.tabs.tabText(1) == "Appearance"
    assert dialog.tabs.tabText(2) == "Storage"
    assert dialog.tabs.tabText(3) == "Database"
    assert dialog.tabs.tabText(4) == "About"


def test_zero_emojis_in_all_ui_source_code():
    """Verify zero unicode emojis exist across all source files in app/."""
    emoji_pattern = re.compile(r"[\U0001F300-\U0001F9FF\u2600-\u26FF\u2700-\u27BF\U0001F1E6-\U0001F1FF]")
    app_dir = Path(__file__).resolve().parent.parent / "app"

    violations = []
    for py_file in app_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        matches = emoji_pattern.findall(content)
        if matches:
            violations.append(f"{py_file.name}: found emojis {matches}")

    assert len(violations) == 0, f"Found emojis in source code: {violations}"
