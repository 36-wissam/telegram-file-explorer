"""Unit tests for Part 1 Anti-Freeze Performance Architecture and Part 2 Obsidian Design System."""

from datetime import datetime, timezone
from unittest.mock import MagicMock
from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QImage, QPixmap

from app.database.models import IndexedFileModel
from app.services.image_loader import AsyncThumbnailManager, thumbnail_manager
from app.ui.media_model import MediaListModel, FileIdRole, FilenameRole, SizeRole, ThumbnailPathRole
from app.ui.theme_manager import ThemeManager, DARK_TOKENS, LIGHT_TOKENS, theme_manager


def test_media_list_model_basic_and_roles():
    """Verify MediaListModel correctly exposes custom roles without widget instantiation."""
    model = MediaListModel()
    assert model.rowCount() == 0

    now = datetime.now(timezone.utc)
    file1 = IndexedFileModel(
        id=1,
        file_id="doc_100",
        message_id=10,
        chat_id=-1001,
        chat_title="Dev Lab",
        filename="contract.pdf",
        extension=".pdf",
        mime_type="application/pdf",
        file_size=204800,
        media_type="DOCUMENT",
        message_date=now,
    )
    file2 = IndexedFileModel(
        id=2,
        file_id="photo_200",
        message_id=20,
        chat_id=-1001,
        chat_title="Dev Lab",
        filename="screenshot.png",
        extension=".png",
        mime_type="image/png",
        file_size=1048576,
        media_type="IMAGE",
        message_date=now,
    )

    model.set_files([file1, file2])
    assert model.rowCount() == 2

    # Check custom roles
    idx0 = model.index(0, 0)
    assert model.data(idx0, Qt.DisplayRole) == "contract.pdf"
    assert model.data(idx0, FileIdRole) == "doc_100"
    assert model.data(idx0, SizeRole) == 204800
    assert model.data(idx0, FilenameRole) == "contract.pdf"

    idx1 = model.index(1, 0)
    assert model.data(idx1, FileIdRole) == "photo_200"

    # Fast row lookup
    assert model.get_row_by_file_id("doc_100") == 0
    assert model.get_row_by_file_id("photo_200") == 1
    assert model.get_row_by_file_id("unknown") == -1


def test_media_list_model_append_without_reset():
    """Verify appending files avoids view reset and scroll jump."""
    model = MediaListModel()
    now = datetime.now(timezone.utc)
    initial_files = [
        IndexedFileModel(
            id=i,
            file_id=f"file_{i}",
            message_id=i,
            chat_id=-1001,
            chat_title="Chat",
            filename=f"file_{i}.txt",
            extension=".txt",
            mime_type="text/plain",
            file_size=1000 * i,
            media_type="DOCUMENT",
            message_date=now,
        )
        for i in range(1, 5)
    ]
    model.set_files(initial_files)
    assert model.rowCount() == 4

    new_files = [
        IndexedFileModel(
            id=i,
            file_id=f"file_{i}",
            message_id=i,
            chat_id=-1001,
            chat_title="Chat",
            filename=f"file_{i}.txt",
            extension=".txt",
            mime_type="text/plain",
            file_size=1000 * i,
            media_type="DOCUMENT",
            message_date=now,
        )
        for i in range(5, 8)
    ]
    # Append new batch
    model.append_files(new_files)
    assert model.rowCount() == 7

    # Appending duplicates does not inflate rowCount
    model.append_files(new_files)
    assert model.rowCount() == 7


def test_media_list_model_thumbnail_path_update():
    """Verify updating a thumbnail path updates model data in place."""
    model = MediaListModel()
    now = datetime.now(timezone.utc)
    file_item = IndexedFileModel(
        id=1,
        file_id="photo_999",
        message_id=50,
        chat_id=-1001,
        chat_title="Chat",
        filename="photo_999.jpg",
        extension=".jpg",
        mime_type="image/jpeg",
        file_size=50000,
        media_type="IMAGE",
        message_date=now,
    )
    model.set_files([file_item])
    idx0 = model.index(0, 0)
    assert model.data(idx0, ThumbnailPathRole) is None

    model.update_thumbnail_path("photo_999", "/cache/photo_999.jpg")
    assert model.data(idx0, ThumbnailPathRole) == "/cache/photo_999.jpg"


def test_thumbnail_manager_lru_eviction(qapp):
    """Verify AsyncThumbnailManager LRU in-memory cache strictly caps at max size."""
    manager = AsyncThumbnailManager(max_lru_size=5, max_threads=2)

    # Populate 5 dummy pixmaps
    for i in range(5):
        img = QImage(32, 32, QImage.Format_RGB32)
        img.fill(0xFF000000 + i)
        manager._on_worker_decoded(request_id=1, file_id=f"f_{i}", image=img)

    assert len(manager._lru_cache) == 5
    assert manager.get_cached_pixmap("f_0") is not None

    # Adding 6th item should evict oldest (f_1 since f_0 was accessed)
    img_new = QImage(32, 32, QImage.Format_RGB32)
    img_new.fill(0xFF0000FF)
    manager._on_worker_decoded(request_id=1, file_id="f_5", image=img_new)

    assert len(manager._lru_cache) == 5
    assert manager.get_cached_pixmap("f_1") is None
    assert manager.get_cached_pixmap("f_0") is not None
    assert manager.get_cached_pixmap("f_5") is not None


def test_obsidian_theme_tokens_and_generation(qapp):
    """Verify ThemeManager generates Obsidian QSS using token dicts."""
    tm = ThemeManager()
    assert tm.get_tokens("dark") == DARK_TOKENS
    assert tm.get_tokens("light") == LIGHT_TOKENS

    dark_qss = tm.generate_qss(DARK_TOKENS)
    assert "#0B0D10" in dark_qss  # --bg-base
    assert "#14171C" in dark_qss  # --bg-surface
    assert "#5C8DFF" in dark_qss  # --accent
    assert "Inter" in dark_qss

    light_qss = tm.generate_qss(LIGHT_TOKENS)
    assert "#F7F8FA" in light_qss  # --bg-base
    assert "#FFFFFF" in light_qss  # --bg-surface
    assert "#3D6FE0" in light_qss  # --accent


def test_stale_request_id_cancellation(tmp_path):
    """Verify ChatMediaBrowserWidget increments request_id on chat switch to cancel stale background jobs."""
    from app.database.repository import DatabaseRepository
    from app.ui.media_browser import ChatMediaBrowserWidget
    from app.telegram.chats import ChatType, TelegramChat

    db_file = tmp_path / "cancel_test.db"
    repo = DatabaseRepository(db_path=db_file)
    indexer = MagicMock()
    async def fake_index(*args, **kwargs):
        return {"indexed": 0}
    indexer.index_chat.side_effect = fake_index

    browser = ChatMediaBrowserWidget(repo=repo, indexer_service=indexer)
    assert browser._current_request_id == 0

    chat1 = TelegramChat(id=1, title="Chat 1", chat_type=ChatType.GROUP)
    chat2 = TelegramChat(id=2, title="Chat 2", chat_type=ChatType.CHANNEL)

    browser.set_chat(chat1)
    req1 = browser._current_request_id
    assert req1 == 1
    assert browser.grid_delegate.current_request_id == 1

    # Quickly switch to chat 2
    browser.set_chat(chat2)
    req2 = browser._current_request_id
    assert req2 == 2
    assert browser.grid_delegate.current_request_id == 2
    assert req2 > req1
