"""Tests for Stage 12: Indexing Controls & Background Orchestration."""

import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from PySide6.QtWidgets import QApplication
from telethon.tl.types import MessageMediaPhoto, Photo, PhotoSize

from app.services.indexing_manager import IndexingManager, IndexingProgress, IndexingStatus
from app.telegram.chats import ChatType, TelegramChat

os.environ["QT_QPA_PLATFORM"] = "offscreen"


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def mock_client_manager():
    manager = MagicMock()
    client = MagicMock()
    client.is_connected.return_value = True
    manager.client = client
    return manager


@pytest.fixture
def indexing_manager(tmp_path: Path, mock_client_manager):
    db_path = tmp_path / "test_indexing_ctrl.db"
    return IndexingManager(mock_client_manager, db_path=db_path)


def test_indexing_manager_initial_state(indexing_manager):
    """Test initial idle status and progress state."""
    assert indexing_manager.status == IndexingStatus.IDLE
    assert not indexing_manager.is_running
    assert not indexing_manager.is_paused
    assert indexing_manager.progress.status == IndexingStatus.IDLE


def test_indexing_manager_empty_chats(indexing_manager):
    """Test starting indexing with empty chat list fails gracefully."""
    result = indexing_manager.start_indexing([])
    assert result is False
    assert indexing_manager.status == IndexingStatus.IDLE


def test_indexing_manager_state_transitions(indexing_manager):
    """Test start, pause, resume, and cancel state transitions."""
    chat1 = TelegramChat(id=10, title="Test Chat 1", chat_type=ChatType.GROUP)

    status_events = []
    indexing_manager.status_changed.connect(lambda s: status_events.append(s))

    with patch("app.services.indexing_manager.async_runner.run_coroutine_async") as mock_run:
        started = indexing_manager.start_indexing([chat1], limit_per_chat=100)
        assert started is True
        assert indexing_manager.status == IndexingStatus.RUNNING
        assert indexing_manager.is_running
        assert not indexing_manager.is_paused
        assert status_events[-1] == "Running"

        # Pause
        paused = indexing_manager.pause_indexing()
        assert paused is True
        assert indexing_manager.status == IndexingStatus.PAUSED
        assert indexing_manager.is_paused
        assert not indexing_manager.is_running
        assert status_events[-1] == "Paused"

        # Resume
        resumed = indexing_manager.resume_indexing()
        assert resumed is True
        assert indexing_manager.status == IndexingStatus.RUNNING
        assert indexing_manager.is_running
        assert not indexing_manager.is_paused
        assert status_events[-1] == "Running"

        # Cancel
        cancelled = indexing_manager.cancel_indexing()
        assert cancelled is True
        assert indexing_manager.status == IndexingStatus.CANCELLED
        assert status_events[-1] == "Cancelled"


def test_indexing_manager_reset_checkpoint(indexing_manager):
    """Test resetting chat indexing state."""
    # Set dummy checkpoint in db
    indexing_manager.indexer.update_indexing_state(55, "Dev Channel", 1234, 10, is_completed=True)
    last_id, files, is_done = indexing_manager.indexer.get_indexing_state(55)
    assert last_id == 1234
    assert is_done is True

    # Reset single chat
    indexing_manager.reset_chat(55)
    last_id, files, is_done = indexing_manager.indexer.get_indexing_state(55)
    assert last_id == 0
    assert is_done is False


@pytest.mark.anyio
async def test_indexing_manager_execution_async(tmp_path: Path):
    """Test async execution of indexing across multiple chats."""
    mock_mgr = MagicMock()
    mock_client = MagicMock()
    mock_client.is_connected.return_value = True

    async def mock_iter(chat_id, min_id=0, limit=500, reverse=True):
        photo = MagicMock(spec=Photo)
        photo.id = chat_id * 1000 + 1
        size_variant = MagicMock(spec=PhotoSize)
        size_variant.size = 204800
        photo.sizes = [size_variant]

        msg = MagicMock()
        msg.id = chat_id * 10 + 1
        msg.media = MagicMock(spec=MessageMediaPhoto)
        msg.media.photo = photo
        msg.date = datetime.now(timezone.utc)
        msg.message = f"Sample photo for chat {chat_id}"
        msg.sender_id = 999
        yield msg

    mock_client.iter_messages = mock_iter
    mock_mgr.client = mock_client

    db_path = tmp_path / "test_exec.db"
    manager = IndexingManager(mock_mgr, db_path=db_path)

    chats = [
        TelegramChat(id=1, title="Chat One", chat_type=ChatType.GROUP),
        TelegramChat(id=2, title="Chat Two", chat_type=ChatType.CHANNEL),
    ]

    total_files = await manager._execute_indexing(chats, limit_per_chat=10, reindex=False)
    assert total_files == 2

    # Verify files in SQLite
    assert manager.indexer.get_total_indexed_count() == 2


def test_indexing_dialog_ui(qapp, indexing_manager):
    """Test IndexingDialog UI creation, interaction, and signal updates."""
    from app.ui.indexing_dialog import IndexingDialog

    chats = [
        TelegramChat(id=1, title="Alpha Chat", chat_type=ChatType.GROUP),
        TelegramChat(id=2, title="Beta Channel", chat_type=ChatType.CHANNEL),
    ]

    dialog = IndexingDialog(indexing_manager, available_chats=chats, parent=None)
    dialog.show()

    # Initial state
    assert dialog.badge_status.text() == "IDLE"
    assert dialog.btn_start.isEnabled()
    assert not dialog.btn_pause.isEnabled()
    assert not dialog.btn_cancel.isEnabled()

    # Switch radio to single chat
    dialog.radio_selected.setChecked(True)
    assert dialog.combo_chats.isEnabled()

    # Emulate manager status changed
    indexing_manager.status_changed.emit("Running")
    assert dialog.badge_status.text() == "RUNNING"
    assert not dialog.btn_start.isEnabled()
    assert dialog.btn_pause.isEnabled()
    assert dialog.btn_cancel.isEnabled()

    # Emulate progress update
    prog = IndexingProgress(
        status=IndexingStatus.RUNNING,
        current_chat_title="Alpha Chat",
        chat_index=1,
        total_chats=2,
        chat_files_indexed=5,
        total_files_indexed=5,
        messages_scanned=20,
        status_message="Indexing Alpha Chat...",
    )
    indexing_manager.progress_updated.emit(prog)
    assert dialog.progress_bar.value() == 50
    assert "Alpha Chat" in dialog.lbl_chat_stat.text()
    assert "Files Indexed: 5" in dialog.lbl_files_stat.text()

    # Emulate log emission
    indexing_manager.log_emitted.emit("[12:00:00] Test log message")
    assert "Test log message" in dialog.text_log.toPlainText()

    # Finished
    indexing_manager.status_changed.emit("Completed")
    assert dialog.badge_status.text() == "COMPLETED"
    assert dialog.btn_start.isEnabled()
