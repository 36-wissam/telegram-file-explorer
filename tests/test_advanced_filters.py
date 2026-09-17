"""Tests for Stage 11: Advanced File Filtering."""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

os.environ["QT_QPA_PLATFORM"] = "offscreen"


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def repo(tmp_path: Path):
    from app.database.connection import init_db
    from app.database.repository import DatabaseRepository
    from app.services.media_parser import MediaFileMetadata, MediaType
    from app.telegram.chats import ChatType, TelegramChat

    db_path = tmp_path / "test_filters.db"
    init_db(db_path)
    repository = DatabaseRepository(db_path)

    # Populate dummy chats
    repository.upsert_chat(TelegramChat(id=101, title="Engineering Group", chat_type=ChatType.SUPERGROUP))
    repository.upsert_chat(TelegramChat(id=202, title="Personal Archive", chat_type=ChatType.CHANNEL))

    # Populate dummy files with distinct dates, sizes, extensions, and chats
    now = datetime.now(timezone.utc)

    files = [
        # Small recent PDF in chat 101
        MediaFileMetadata(
            file_id="f_pdf_recent",
            message_id=1,
            chat_id=101,
            chat_title="Engineering Group",
            filename="quarterly_report.pdf",
            extension=".pdf",
            mime_type="application/pdf",
            file_size=500 * 1024,  # 500 KB (< 1MB)
            media_type=MediaType.DOCUMENT,
            message_date=now - timedelta(hours=2),
            caption="Q3 Financial Overview",
        ),
        # Medium old PDF in chat 202
        MediaFileMetadata(
            file_id="f_pdf_old",
            message_id=2,
            chat_id=202,
            chat_title="Personal Archive",
            filename="archive_manual.pdf",
            extension=".pdf",
            mime_type="application/pdf",
            file_size=5 * 1024 * 1024,  # 5 MB (1MB - 10MB)
            media_type=MediaType.DOCUMENT,
            message_date=now - timedelta(days=60),
            caption="Old technical manual",
        ),
        # Large video in chat 101
        MediaFileMetadata(
            file_id="f_video_large",
            message_id=3,
            chat_id=101,
            chat_title="Engineering Group",
            filename="demo_presentation.mp4",
            extension=".mp4",
            mime_type="video/mp4",
            file_size=150 * 1024 * 1024,  # 150 MB (100MB - 1GB)
            media_type=MediaType.VIDEO,
            message_date=now - timedelta(days=5),
            caption="Full HD presentation capture",
        ),
        # Huge archive in chat 202
        MediaFileMetadata(
            file_id="f_archive_huge",
            message_id=4,
            chat_id=202,
            chat_title="Personal Archive",
            filename="backup_data.zip",
            extension=".zip",
            mime_type="application/zip",
            file_size=2 * 1024 * 1024 * 1024,  # 2 GB (> 1GB)
            media_type=MediaType.ARCHIVE,
            message_date=now - timedelta(days=2),
            caption="Complete offsite database backup",
        ),
    ]
    repository.save_files_batch(files)
    return repository


def test_filter_bar_standalone_signals(qapp):
    """Test AdvancedFilterBar UI controls emit correct filter parameters."""
    from app.ui.filter_bar import AdvancedFilterBar, AdvancedFilterCriteria

    bar = AdvancedFilterBar()
    bar.populate_chats([
        {"id": 101, "title": "Engineering"},
        {"id": 202, "title": "Archive"},
    ])

    emitted_criteria = []
    bar.filters_changed.connect(lambda c: emitted_criteria.append(c))

    # Test size filter change
    bar.combo_size.setCurrentIndex(1)  # "< 1 MB"
    assert len(emitted_criteria) >= 1
    assert emitted_criteria[-1].max_size_bytes == 1024 * 1024

    # Test extension input
    bar.input_ext.setText("pdf")
    assert emitted_criteria[-1].extension == ".pdf"

    # Test chat dropdown
    bar.combo_chat.setCurrentIndex(1)  # Engineering
    assert emitted_criteria[-1].chat_id == 101

    # Test reset button
    bar.btn_reset.click()
    assert bar.combo_size.currentIndex() == 0
    assert bar.combo_chat.currentIndex() == 0
    assert bar.input_ext.text() == ""
    assert emitted_criteria[-1].extension is None
    assert emitted_criteria[-1].chat_id is None


def test_file_explorer_toggle_filters(qapp, repo):
    """Test toggling filter bar visibility from FileExplorerWidget toolbar."""
    from app.ui.file_explorer import FileExplorerWidget

    explorer = FileExplorerWidget(repo)
    explorer.show()

    assert not explorer.filter_bar.isVisible()

    # Toggle open
    explorer.btn_toggle_filters.click()
    assert explorer.filter_bar.isVisible()
    assert "Filters" in explorer.btn_toggle_filters.text()

    # Toggle closed
    explorer.btn_toggle_filters.click()
    assert not explorer.filter_bar.isVisible()
    assert "Filters" in explorer.btn_toggle_filters.text()


def test_file_explorer_size_filtering(qapp, repo):
    """Test filtering files by size ranges in the explorer."""
    from app.ui.file_explorer import FileExplorerWidget

    explorer = FileExplorerWidget(repo)

    # Default: all 4 files visible
    assert explorer.table.rowCount() == 4

    # Filter: < 1 MB (should match quarterly_report.pdf)
    explorer.filter_bar.combo_size.setCurrentIndex(1)
    assert explorer.table.rowCount() == 1
    assert "quarterly_report.pdf" in explorer.table.item(0, 0).text()

    # Filter: > 1 GB (should match backup_data.zip)
    explorer.filter_bar.combo_size.setCurrentIndex(5)
    assert explorer.table.rowCount() == 1
    assert "backup_data.zip" in explorer.table.item(0, 0).text()

    # Reset
    explorer.filter_bar.reset_filters()
    assert explorer.table.rowCount() == 4


def test_file_explorer_extension_filtering(qapp, repo):
    """Test filtering by file extension."""
    from app.ui.file_explorer import FileExplorerWidget

    explorer = FileExplorerWidget(repo)

    # Filter by .pdf (matches 2 files)
    explorer.filter_bar.input_ext.setText(".pdf")
    assert explorer.table.rowCount() == 2

    # Filter by .mp4 (matches 1 file)
    explorer.filter_bar.input_ext.setText("mp4")
    assert explorer.table.rowCount() == 1
    assert "demo_presentation.mp4" in explorer.table.item(0, 0).text()

    # Filter by non-existent extension
    explorer.filter_bar.input_ext.setText("exe")
    assert explorer.table.rowCount() == 0


def test_file_explorer_chat_and_date_filtering(qapp, repo):
    """Test filtering by source chat and date preset."""
    from app.ui.file_explorer import FileExplorerWidget

    explorer = FileExplorerWidget(repo)

    # Engineering chat (id 101) has 2 files: quarterly_report.pdf & demo_presentation.mp4
    idx = explorer.filter_bar.combo_chat.findData(101)
    assert idx > 0
    explorer.filter_bar.combo_chat.setCurrentIndex(idx)
    assert explorer.table.rowCount() == 2

    # Further filter by Past 24 Hours (only quarterly_report.pdf is 2 hours old, presentation is 5 days old)
    explorer.filter_bar.combo_date.setCurrentIndex(1)  # Past 24 Hours
    assert explorer.table.rowCount() == 1
    assert "quarterly_report.pdf" in explorer.table.item(0, 0).text()
