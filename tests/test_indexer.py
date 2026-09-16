"""Unit tests for Stage 5: Telegram Media Indexing."""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from pathlib import Path

from app.core.config import Settings
from app.services.media_parser import (
    MediaType,
    classify_media_type,
    parse_message_media,
    MediaFileMetadata,
)
from app.services.indexer import MediaIndexerService
from telethon.tl.types import (
    Document,
    DocumentAttributeAudio,
    DocumentAttributeFilename,
    DocumentAttributeVideo,
    MessageMediaDocument,
    MessageMediaPhoto,
    Photo,
    PhotoSize,
)


def test_classify_media_type():
    """Verify classification logic across file extensions and MIME types."""
    assert classify_media_type("project.zip", "application/zip")[0] == MediaType.ARCHIVE
    assert classify_media_type("report.pdf", "application/pdf")[0] == MediaType.DOCUMENT
    assert classify_media_type("song.mp3", "audio/mpeg")[0] == MediaType.AUDIO
    assert classify_media_type("clip.mp4", "video/mp4")[0] == MediaType.VIDEO
    assert classify_media_type("photo.png", "image/png")[0] == MediaType.IMAGE
    assert classify_media_type("voice_note.ogg", "audio/ogg", is_voice=True)[0] == MediaType.VOICE
    assert classify_media_type("archive.tar.gz", "application/x-tar")[0] == MediaType.ARCHIVE


def test_parse_photo_message():
    """Verify parsing photo message extracts image metadata."""
    msg = MagicMock()
    msg.id = 42
    msg.date = datetime(2026, 9, 1, 10, 0)
    msg.message = "Beautiful sunset"
    msg.sender_id = 111

    photo = MagicMock(spec=Photo)
    photo.id = 999888777
    size_variant = MagicMock(spec=PhotoSize)
    size_variant.size = 204800
    photo.sizes = [size_variant]

    msg.media = MagicMock(spec=MessageMediaPhoto)
    msg.media.photo = photo

    meta = parse_message_media(msg, chat_id=-100123, chat_title="Nature Channel")
    assert meta is not None
    assert meta.file_id == "photo_999888777"
    assert meta.message_id == 42
    assert meta.chat_id == -100123
    assert meta.chat_title == "Nature Channel"
    assert meta.media_type == MediaType.IMAGE
    assert meta.extension == ".jpg"
    assert meta.file_size == 204800
    assert meta.caption == "Beautiful sunset"


def test_parse_document_message():
    """Verify parsing document message with filename attribute."""
    msg = MagicMock()
    msg.id = 105
    msg.date = datetime(2026, 9, 5, 14, 20)
    msg.message = "Attached presentation"
    msg.sender_id = 222

    doc = MagicMock(spec=Document)
    doc.id = 555666
    doc.size = 10485760  # 10 MB
    doc.mime_type = "application/pdf"
    doc.thumbs = [MagicMock()]

    attr_filename = MagicMock(spec=DocumentAttributeFilename)
    attr_filename.file_name = "quarterly_results.pdf"
    doc.attributes = [attr_filename]

    msg.media = MagicMock(spec=MessageMediaDocument)
    msg.media.document = doc

    meta = parse_message_media(msg, chat_id=-100456, chat_title="Finance Group")
    assert meta is not None
    assert meta.file_id == "doc_555666"
    assert meta.filename == "quarterly_results.pdf"
    assert meta.media_type == MediaType.DOCUMENT
    assert meta.extension == ".pdf"
    assert meta.file_size == 10485760
    assert meta.has_thumbnail is True


def test_indexer_sqlite_storage_and_resumability(tmp_path):
    """Verify MediaIndexerService creates tables, saves metadata, and manages state."""
    db_path = tmp_path / "test_indexer.db"
    manager = MagicMock()

    service = MediaIndexerService(manager, db_path=db_path)

    # Initial state should be empty
    last_id, total, is_done = service.get_indexing_state(12345)
    assert last_id == 0
    assert total == 0
    assert is_done is False

    # Save a metadata record
    meta = MediaFileMetadata(
        file_id="doc_1",
        message_id=10,
        chat_id=12345,
        chat_title="My Chat",
        filename="notes.txt",
        extension=".txt",
        mime_type="text/plain",
        file_size=1024,
        media_type=MediaType.DOCUMENT,
        message_date=datetime(2026, 9, 10, 10, 0),
    )
    service.save_file_metadata(meta)
    service.update_indexing_state(12345, "My Chat", last_msg_id=10, new_files_count=1)

    # State should update
    last_id, total, is_done = service.get_indexing_state(12345)
    assert last_id == 10
    assert total == 1

    # Query files
    files = service.get_indexed_files(chat_id=12345)
    assert len(files) == 1
    assert files[0]["filename"] == "notes.txt"
    assert files[0]["file_size"] == 1024


def test_index_chat_mocked_scan(tmp_path):
    """Verify index_chat iterates messages, extracts media, and resumes from checkpoint."""
    db_path = tmp_path / "scan_test.db"
    manager = MagicMock()
    client = MagicMock()
    client.is_connected.return_value = True

    # Generate 3 messages: 2 with media, 1 text-only
    m1 = MagicMock()
    m1.id = 1
    m1.date = datetime(2026, 9, 1, 10, 0)
    m1.message = "Text only message"
    m1.media = None

    m2 = MagicMock()
    m2.id = 2
    m2.date = datetime(2026, 9, 1, 10, 5)
    m2.message = "Here is photo"
    photo = MagicMock(spec=Photo)
    photo.id = 200
    photo.sizes = [MagicMock(spec=PhotoSize, size=5000)]
    m2.media = MagicMock(spec=MessageMediaPhoto, photo=photo)

    m3 = MagicMock()
    m3.id = 3
    m3.date = datetime(2026, 9, 1, 10, 10)
    m3.message = "Here is archive"
    doc = MagicMock(spec=Document)
    doc.id = 300
    doc.size = 25000
    doc.mime_type = "application/zip"
    doc.thumbs = None
    attr = MagicMock(spec=DocumentAttributeFilename, file_name="backup.zip")
    doc.attributes = [attr]
    m3.media = MagicMock(spec=MessageMediaDocument, document=doc)

    async def mock_iter_messages(chat_id, min_id=0, limit=100, reverse=True):
        for msg in [m1, m2, m3]:
            if msg.id > min_id:
                yield msg

    client.iter_messages = mock_iter_messages
    manager.client = client

    service = MediaIndexerService(manager, db_path=db_path)

    # First run: indexes m2 and m3 (2 files)
    indexed_count = asyncio.run(service.index_chat(chat_id=999, chat_title="Test Chat", limit=10))
    assert indexed_count == 2
    assert service.get_total_indexed_count(chat_id=999) == 2

    last_id, total, _ = service.get_indexing_state(999)
    assert last_id == 3
    assert total == 2

    # Second run: min_id=3 -> no new messages, returns 0 cleanly without re-indexing
    indexed_again = asyncio.run(service.index_chat(chat_id=999, chat_title="Test Chat", limit=10))
    assert indexed_again == 0
    assert service.get_total_indexed_count(chat_id=999) == 2
