"""Tests for Stage 13: Performance, Database Optimizations & Telegram Reliability."""

import asyncio
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from PySide6.QtWidgets import QApplication
from sqlalchemy import text
from telethon.errors import FloodWaitError, RPCError

from app.database.connection import get_session, init_db, optimize_db, vacuum_db
from app.database.models import IndexedFileModel
from app.database.repository import DatabaseRepository
from app.services.media_parser import MediaFileMetadata, MediaType
from app.telegram.chats import ChatType, TelegramChat
from app.telegram.resilience import TelegramRateLimitError, execute_with_retry

os.environ["QT_QPA_PLATFORM"] = "offscreen"


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def repo(tmp_path: Path):
    db_path = tmp_path / "test_perf.db"
    init_db(db_path)
    repository = DatabaseRepository(db_path)
    repository.upsert_chat(TelegramChat(id=1, title="Test Group", chat_type=ChatType.GROUP))
    return repository


# --- 1. Resilience & Rate-Limit Backoff Tests ---

@pytest.mark.anyio
async def test_execute_with_retry_flood_wait_within_threshold():
    """Verify FloodWaitError under max threshold automatically sleeps and retries."""
    call_count = 0

    async def flaky_op():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            err = FloodWaitError(request=None)
            err.seconds = 2
            raise err
        return "success"

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        result = await execute_with_retry(flaky_op, max_flood_wait=10)
        assert result == "success"
        assert call_count == 2
        mock_sleep.assert_called_once_with(3)  # wait_s + 1


@pytest.mark.anyio
async def test_execute_with_retry_flood_wait_exceeds_threshold():
    """Verify FloodWaitError exceeding max threshold raises TelegramRateLimitError."""
    async def heavy_rate_limited():
        err = FloodWaitError(request=None)
        err.seconds = 300
        raise err

    with pytest.raises(TelegramRateLimitError) as exc_info:
        await execute_with_retry(heavy_rate_limited, max_flood_wait=60)
    assert exc_info.value.seconds == 300


@pytest.mark.anyio
async def test_execute_with_retry_transient_network_errors():
    """Verify exponential backoff on transient connection errors."""
    attempts = 0

    async def network_op():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ConnectionError("Network reset by peer")
        return "connected"

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        res = await execute_with_retry(network_op, max_retries=3, base_delay=0.1)
        assert res == "connected"
        assert attempts == 3
        assert mock_sleep.call_count == 2


# --- 2. Database Maintenance & Pragma Tests ---

def test_database_vacuum_and_optimize(tmp_path: Path):
    """Verify VACUUM and ANALYZE operations execute without errors."""
    db_file = tmp_path / "test_vacuum.db"
    init_db(db_file)

    # Rebuilding & optimizing database
    vacuum_db(db_file)
    optimize_db(db_file)
    assert db_file.exists()


def test_sqlite_pragmas(repo):
    """Verify SQLite WAL and performance pragmas are active."""
    session = get_session(repo.db_path)
    try:
        journal_mode = session.execute(text("PRAGMA journal_mode;")).scalar()
        assert journal_mode.lower() == "wal"

        foreign_keys = session.execute(text("PRAGMA foreign_keys;")).scalar()
        assert foreign_keys == 1
    finally:
        session.close()


# --- 3. High Throughput Batch Throughput Benchmark ---

def test_high_throughput_batch_insert(repo):
    """Verify inserting 500 files in a single transaction completes in reasonable time."""
    now = datetime.now(timezone.utc)
    batch = [
        MediaFileMetadata(
            file_id=f"doc_perf_{i}",
            message_id=i,
            chat_id=1,
            chat_title="Test Group",
            filename=f"document_{i}.pdf",
            extension=".pdf",
            mime_type="application/pdf",
            file_size=1024 * (i + 1),
            media_type=MediaType.DOCUMENT,
            message_date=now,
            caption=f"Document test #{i}",
        )
        for i in range(500)
    ]

    start_time = time.perf_counter()
    saved = repo.save_files_batch(batch)
    duration = time.perf_counter() - start_time

    assert saved == 500
    assert duration < 5.0, f"Batch insert took {duration:.2f}s, expected < 5.0s"

    # Fast multi-column query performance
    t0 = time.perf_counter()
    files = repo.get_files(chat_id=1, media_type="DOCUMENT", limit=100)
    q_duration = time.perf_counter() - t0

    assert len(files) == 100
    assert q_duration < 0.2, f"Query took {q_duration:.4f}s, expected < 0.2s"


# --- 4. UI Optimized Table Rendering ---

def test_file_explorer_fast_table_render(qapp, repo):
    """Verify FileExplorerWidget renders populated batches cleanly with disabled updates."""
    from app.ui.file_explorer import FileExplorerWidget

    # Insert 60 files so page size of 50 is filled
    now = datetime.now(timezone.utc)
    batch = [
        MediaFileMetadata(
            file_id=f"f_render_{i}",
            message_id=i,
            chat_id=1,
            chat_title="Test Group",
            filename=f"doc_render_{i}.pdf",
            extension=".pdf",
            mime_type="application/pdf",
            file_size=1024 * (i + 1),
            media_type=MediaType.DOCUMENT,
            message_date=now,
        )
        for i in range(60)
    ]
    repo.save_files_batch(batch)

    explorer = FileExplorerWidget(repo)
    explorer.show()

    # Table contains 50 items per page limit
    assert explorer.table.rowCount() == 50
    assert explorer.table.updatesEnabled()
