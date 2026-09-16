"""Unit tests for Stage 7: File Explorer UI."""

from datetime import datetime, timezone
import pytest
from pathlib import Path
from PySide6.QtWidgets import QApplication

from app.database.repository import DatabaseRepository
from app.services.media_parser import MediaType, MediaFileMetadata
from app.ui.file_explorer import FileExplorerWidget, format_bytes


@pytest.fixture
def explorer_repo(tmp_path):
    """Fixture with pre-seeded database for file explorer testing."""
    db_file = tmp_path / "explorer_ui.db"
    repo = DatabaseRepository(db_path=db_file)

    now = datetime.now(timezone.utc)
    # Seed 5 diverse files
    files = [
        MediaFileMetadata(
            file_id=f"file_{i}",
            message_id=i,
            chat_id=-1001,
            chat_title="Channel Alpha",
            filename=f"document_{i}.pdf",
            extension=".pdf",
            mime_type="application/pdf",
            file_size=1024 * (i + 1),
            media_type=MediaType.DOCUMENT,
            message_date=now,
        )
        for i in range(1, 4)
    ]
    files.append(
        MediaFileMetadata(
            file_id="photo_99",
            message_id=99,
            chat_id=-1001,
            chat_title="Channel Alpha",
            filename="vacation.png",
            extension=".png",
            mime_type="image/png",
            file_size=4096000,
            media_type=MediaType.IMAGE,
            message_date=now,
        )
    )
    repo.save_files_batch(files)
    return repo


def test_format_bytes():
    """Verify human-readable byte formatting."""
    assert format_bytes(500) == "500 B"
    assert format_bytes(1024) == "1.0 KB"
    assert format_bytes(1048576) == "1.0 MB"
    assert format_bytes(1073741824) == "1.0 GB"


def test_file_explorer_initialization(qapp, explorer_repo):
    """Verify FileExplorerWidget loads initial data."""
    explorer = FileExplorerWidget(explorer_repo)
    explorer.show()

    assert explorer.table.rowCount() == 4
    assert "4 of 4 files" in explorer.summary_label.text()
    explorer.close()


def test_file_explorer_category_filtering(qapp, explorer_repo):
    """Verify clicking category filter reloads matching files."""
    explorer = FileExplorerWidget(explorer_repo)
    explorer.show()

    # Filter to Images
    explorer._current_category = "IMAGE"
    explorer.reload_files()
    assert explorer.table.rowCount() == 1
    first_item = explorer.table.item(0, 0)
    assert "vacation.png" in first_item.text()

    # Filter to Documents
    explorer._current_category = "DOCUMENT"
    explorer.reload_files()
    assert explorer.table.rowCount() == 3

    # Filter to Videos (0 items)
    explorer._current_category = "VIDEO"
    explorer.reload_files()
    assert explorer.table.rowCount() == 0

    explorer.close()


def test_file_explorer_search_filtering(qapp, explorer_repo):
    """Verify typing in search input filters results."""
    explorer = FileExplorerWidget(explorer_repo)
    explorer.show()

    explorer.search_input.setText("vacation")
    assert explorer.table.rowCount() == 1
    assert "vacation.png" in explorer.table.item(0, 0).text()

    explorer.search_input.setText("non_existent_file")
    assert explorer.table.rowCount() == 0

    explorer.close()


def test_file_explorer_sorting(qapp, explorer_repo):
    """Verify sorting changes item ordering in table."""
    explorer = FileExplorerWidget(explorer_repo)
    explorer.show()

    # Sort by Size (Largest First)
    explorer.sort_combo.setCurrentIndex(2)  # Size (Largest First)
    assert explorer.table.rowCount() == 4
    # vacation.png is 4MB, largest
    assert "vacation.png" in explorer.table.item(0, 0).text()

    # Sort by Size (Smallest First)
    explorer.sort_combo.setCurrentIndex(3)  # Size (Smallest First)
    # document_1.pdf is 2KB, smallest
    assert "document_1.pdf" in explorer.table.item(0, 0).text()

    explorer.close()
