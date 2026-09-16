"""Unit tests for Stage 8: SQLite FTS5 Full Text File Search."""

from datetime import datetime, timezone
import pytest
from pathlib import Path

from app.database.repository import DatabaseRepository
from app.database.search import sanitize_fts5_query
from app.services.media_parser import MediaType, MediaFileMetadata
from app.services.search import SearchEngineService


@pytest.fixture
def search_service(tmp_path):
    """Fixture providing SearchEngineService with seeded SQLite database."""
    db_file = tmp_path / "test_fts5.db"
    repo = DatabaseRepository(db_path=db_file)

    now = datetime.now(timezone.utc)
    files = [
        MediaFileMetadata(
            file_id="doc_1",
            message_id=1,
            chat_id=-1001,
            chat_title="Architecture & Design",
            filename="system_architecture_diagram.pdf",
            extension=".pdf",
            mime_type="application/pdf",
            file_size=2048000,
            media_type=MediaType.DOCUMENT,
            message_date=now,
            caption="Blueprints and core database schema",
        ),
        MediaFileMetadata(
            file_id="photo_2",
            message_id=2,
            chat_id=-1001,
            chat_title="Architecture & Design",
            filename="office_blueprints.jpg",
            extension=".jpg",
            mime_type="image/jpeg",
            file_size=512000,
            media_type=MediaType.IMAGE,
            message_date=now,
            caption="Floor plan sketch",
        ),
        MediaFileMetadata(
            file_id="archive_3",
            message_id=3,
            chat_id=-1002,
            chat_title="DevOps Releases",
            filename="release_v2.4_final.tar.gz",
            extension=".tar.gz",
            mime_type="application/gzip",
            file_size=83886080,  # 80MB
            media_type=MediaType.ARCHIVE,
            message_date=now,
            caption="Production deployment artifacts",
        ),
        MediaFileMetadata(
            file_id="video_4",
            message_id=4,
            chat_id=-1002,
            chat_title="DevOps Releases",
            filename="demo_walkthrough.mp4",
            extension=".mp4",
            mime_type="video/mp4",
            file_size=104857600,  # 100MB
            media_type=MediaType.VIDEO,
            message_date=now,
            caption="Video recording of the new UI features",
        ),
    ]
    repo.save_files_batch(files)
    return SearchEngineService(repo, db_path=db_file)


def test_sanitize_fts5_query():
    """Verify query sanitizer formats safe prefix-match queries."""
    assert sanitize_fts5_query("") == ""
    assert sanitize_fts5_query("report") == '"report"*'
    assert sanitize_fts5_query("sales report 2026") == '"sales"* "report"* "2026"*'
    # Test special characters and keywords
    assert sanitize_fts5_query('test "hello" * AND OR') == '"test"* "hello"*'


def test_search_exact_filename(search_service):
    """Verify search finds exact filename match."""
    files, count = search_service.search_files(query_text="system_architecture_diagram.pdf")
    assert count == 1
    assert len(files) == 1
    assert files[0].filename == "system_architecture_diagram.pdf"


def test_search_partial_filename(search_service):
    """Verify partial filename search via FTS5 prefix matching."""
    files, count = search_service.search_files(query_text="blueprints")
    assert count == 2
    filenames = [f.filename for f in files]
    assert "office_blueprints.jpg" in filenames
    # caption of system_architecture_diagram.pdf also contains "Blueprints"
    assert "system_architecture_diagram.pdf" in filenames


def test_search_by_source_chat(search_service):
    """Verify searching for chat title returns files from that chat."""
    files, count = search_service.search_files(query_text="DevOps")
    assert count == 2
    for f in files:
        assert f.chat_title == "DevOps Releases"


def test_search_combined_with_category_filter(search_service):
    """Verify FTS5 search combines seamlessly with category filter."""
    # Searching 'blueprints' with category 'IMAGE' should only return the JPG
    files, count = search_service.search_files(query_text="blueprints", media_type="IMAGE")
    assert count == 1
    assert files[0].filename == "office_blueprints.jpg"

    # Searching 'blueprints' with category 'DOCUMENT' should only return the PDF
    files, count = search_service.search_files(query_text="blueprints", media_type="DOCUMENT")
    assert count == 1
    assert files[0].filename == "system_architecture_diagram.pdf"


def test_search_sorting(search_service):
    """Verify search results sort by size and date."""
    files, count = search_service.search_files(query_text="Releases", sort_by="size", sort_desc=True)
    assert count == 2
    # demo_walkthrough (100MB) > release_v2.4 (80MB)
    assert files[0].filename == "demo_walkthrough.mp4"
    assert files[1].filename == "release_v2.4_final.tar.gz"
