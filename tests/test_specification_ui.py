"""Comprehensive tests for specification UI components, automatic loading, icons, lightbox, and zero emoji constraint."""

import re
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from PySide6.QtCore import Qt

from app.database.models import IndexedFileModel
from app.database.repository import DatabaseRepository
from app.telegram.chats import ChatType, TelegramChat
from app.ui.icons import get_icon, get_pixmap, SVG_ICONS
from app.ui.lightbox import ImageLightboxDialog
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


@pytest.fixture
def sample_image_file():
    return IndexedFileModel(
        id=2,
        file_id="spec_102",
        message_id=15,
        chat_id=-1001234567890,
        chat_title="Product Design",
        filename="mockup.png",
        extension=".png",
        mime_type="image/png",
        file_size=1048576,  # 1 MB
        media_type="IMAGE",
        message_date=datetime(2026, 9, 17, 11, 0, tzinfo=timezone.utc),
    )


def test_svg_icon_provider():
    """Verify SVG icon provider generates non-null pixmaps and icons."""
    for icon_name in SVG_ICONS.keys():
        pix = get_pixmap(icon_name, color="#229ED9", size=24)
        assert pix is not None
        assert not pix.isNull()
        assert pix.width() == 24
        assert pix.height() == 24

        icon = get_icon(icon_name, color="#FFFFFF", size=16)
        assert icon is not None
        assert not icon.isNull()


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

    # Select chat with 64-bit ID matching sample_file
    chat = TelegramChat(
        id=sample_file.chat_id,
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


def test_image_lightbox_navigation_and_zoom(qapp, sample_image_file):
    """Verify Image Lightbox dialog displays image and responds to zoom and navigation."""
    lightbox = ImageLightboxDialog([sample_image_file], current_index=0)
    lightbox.show()

    assert lightbox.title_label.text() == "mockup.png"
    assert lightbox.counter_label.text() == "1 of 1"

    # Zoom in / out
    initial_zoom = lightbox.zoom_factor
    lightbox._zoom_in()
    assert lightbox.zoom_factor > initial_zoom
    lightbox._zoom_out()
    lightbox._zoom_reset()
    assert lightbox.zoom_factor == 1.0


def test_settings_dialog_tabs(qapp, tmp_path):
    """Verify SettingsDialog tabs and structure."""
    db_file = tmp_path / "settings_test.db"
    repo = DatabaseRepository(db_path=db_file)
    dialog = SettingsDialog(repo=repo)
    dialog.show()

    assert dialog.tabs.count() == 5
    assert dialog.tabs.tabText(0) == "Account"
    assert dialog.tabs.tabText(1) == "Appearance"
    assert dialog.tabs.tabText(2) == "Downloads"
    assert dialog.tabs.tabText(3) == "Storage"
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


def test_media_card_selected_state(qapp, sample_file):
    """Verify MediaCardWidget selected state styling and toggle."""
    card = MediaCardWidget(sample_file)
    assert card._selected is False
    card.set_selected(True)
    assert card._selected is True
    assert "2px solid #229ED9" in card.styleSheet()
    card.set_selected(False)
    assert card._selected is False
    card.close()


def test_skeleton_card_placeholder(qapp):
    """Verify SkeletonCard placeholder rendering and animation."""
    from app.ui.media_browser import SkeletonCard
    skeleton = SkeletonCard()
    skeleton.show()
    assert skeleton._animating is True
    assert skeleton.width() == 200
    skeleton.close()


def test_preview_panel_close_signal(qapp, sample_file):
    """Verify PreviewPanel close_requested signal and inspector header."""
    panel = PreviewPanel()
    panel.show()
    panel.set_file(sample_file)
    assert panel.name_label.text() == "system_architecture.pdf"

    closed = []
    panel.close_requested.connect(lambda: closed.append(True))
    panel._request_close()
    assert len(closed) == 1
    panel.close()


def test_indexer_update_thumbnail_paths(tmp_path):
    """Verify MediaIndexerService update_thumbnail_paths updates SQLite correctly."""
    from app.services.indexer import MediaIndexerService
    from app.services.media_parser import MediaFileMetadata, MediaType

    db_path = tmp_path / "indexer_test.db"
    manager = MagicMock()
    indexer = MediaIndexerService(client_manager=manager, db_path=db_path)

    now = datetime.now(timezone.utc)
    meta = MediaFileMetadata(
        file_id="thumb_test_1",
        message_id=10,
        chat_id=-1005,
        chat_title="Test Chat",
        filename="photo.jpg",
        extension=".jpg",
        mime_type="image/jpeg",
        file_size=1024,
        media_type=MediaType.IMAGE,
        message_date=now,
        has_thumbnail=True,
    )
    indexer.save_file_metadata(meta)

    files = indexer.get_indexed_files(chat_id=-1005)
    assert len(files) == 1
    assert files[0]["thumbnail_path"] is None

    indexer.update_thumbnail_paths({"thumb_test_1": "/cached/thumb_test_1.jpg"})
    files = indexer.get_indexed_files(chat_id=-1005)
    assert files[0]["thumbnail_path"] == "/cached/thumb_test_1.jpg"

