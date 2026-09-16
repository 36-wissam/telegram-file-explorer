"""Unit tests for Stage 6: Database Layer using SQLAlchemy."""

import pytest
from datetime import datetime, timezone
from pathlib import Path

from app.database import (
    init_db,
    ChatModel,
    IndexedFileModel,
    IndexingStateModel,
    AppSettingModel,
    DatabaseRepository,
)
from app.telegram.chats import ChatType, TelegramChat
from app.services.media_parser import MediaType, MediaFileMetadata


@pytest.fixture
def repo(tmp_path):
    """Fixture providing a DatabaseRepository with isolated SQLite DB."""
    db_file = tmp_path / "test_media.db"
    return DatabaseRepository(db_path=db_file)


def test_init_db(repo):
    """Verify database tables and indexes are created successfully."""
    # init_db is called in DatabaseRepository constructor
    assert repo.db_path.exists()


def test_upsert_chat_and_query(repo):
    """Verify upserting chats and querying them."""
    chat1 = TelegramChat(
        id=-10012345,
        title="Python Hub",
        chat_type=ChatType.CHANNEL,
        username="pythonhub",
        unread_count=3,
        pinned=True,
    )
    repo.upsert_chat(chat1)

    chats = repo.get_chats()
    assert len(chats) == 1
    assert chats[0].id == -10012345
    assert chats[0].title == "Python Hub"
    assert chats[0].pinned is True

    # Update chat with new unread count
    chat1_updated = TelegramChat(
        id=-10012345,
        title="Python Hub (Official)",
        chat_type=ChatType.CHANNEL,
        username="pythonhub",
        unread_count=0,
        pinned=False,
    )
    repo.upsert_chat(chat1_updated)

    chats_after = repo.get_chats()
    assert len(chats_after) == 1
    assert chats_after[0].title == "Python Hub (Official)"
    assert chats_after[0].unread_count == 0


def test_save_files_batch_and_filtering(repo):
    """Verify saving file batch and querying with filters and sorting."""
    # Create files
    now = datetime.now(timezone.utc)
    f1 = MediaFileMetadata(
        file_id="photo_100",
        message_id=1,
        chat_id=-10012345,
        chat_title="Media Hub",
        filename="sunset.jpg",
        extension=".jpg",
        mime_type="image/jpeg",
        file_size=50000,
        media_type=MediaType.IMAGE,
        message_date=now,
    )
    f2 = MediaFileMetadata(
        file_id="doc_200",
        message_id=2,
        chat_id=-10012345,
        chat_title="Media Hub",
        filename="specs.pdf",
        extension=".pdf",
        mime_type="application/pdf",
        file_size=2000000,
        media_type=MediaType.DOCUMENT,
        message_date=now,
    )
    f3 = MediaFileMetadata(
        file_id="video_300",
        message_id=3,
        chat_id=-10012345,
        chat_title="Media Hub",
        filename="tutorial.mp4",
        extension=".mp4",
        mime_type="video/mp4",
        file_size=15000000,
        media_type=MediaType.VIDEO,
        message_date=now,
    )

    count = repo.save_files_batch([f1, f2, f3])
    assert count == 3
    assert repo.get_files_count() == 3

    # Filter by media_type
    images = repo.get_files(media_type="IMAGE")
    assert len(images) == 1
    assert images[0].filename == "sunset.jpg"

    docs = repo.get_files(media_type="DOCUMENT")
    assert len(docs) == 1
    assert docs[0].filename == "specs.pdf"

    # Filter by search query
    search_res = repo.get_files(search_query="tutorial")
    assert len(search_res) == 1
    assert search_res[0].filename == "tutorial.mp4"

    # Filter by size range
    small_files = repo.get_files(max_size=100000)
    assert len(small_files) == 1
    assert small_files[0].filename == "sunset.jpg"

    # Sorting by size descending
    sorted_size = repo.get_files(sort_by="size", sort_desc=True)
    assert sorted_size[0].file_size == 15000000
    assert sorted_size[-1].file_size == 50000


def test_indexing_state_resumability(repo):
    """Verify IndexingStateModel tracks last_indexed_message_id and accumulates total files."""
    state = repo.get_indexing_state(9999)
    assert state == (0, 0, False)

    # First batch
    repo.update_indexing_state(
        chat_id=9999,
        chat_title="Testing Chat",
        last_msg_id=50,
        new_files_count=10,
        is_completed=False,
    )
    last_id, total, is_done = repo.get_indexing_state(9999)
    assert last_id == 50
    assert total == 10
    assert is_done is False

    # Second batch (resumed from message 50)
    repo.update_indexing_state(
        chat_id=9999,
        chat_title="Testing Chat",
        last_msg_id=120,
        new_files_count=15,
        is_completed=True,
    )
    last_id, total, is_done = repo.get_indexing_state(9999)
    assert last_id == 120
    assert total == 25
    assert is_done is True


def test_app_settings(repo):
    """Verify key-value AppSettingModel persistence."""
    assert repo.get_setting("custom_download_path") is None
    assert repo.get_setting("custom_download_path", default="/downloads") == "/downloads"

    repo.set_setting("custom_download_path", "C:/User/Downloads")
    assert repo.get_setting("custom_download_path") == "C:/User/Downloads"
