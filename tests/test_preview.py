"""Unit tests for Stage 9: File Preview."""

from datetime import datetime, timezone
import pytest
from unittest.mock import MagicMock
from pathlib import Path

from app.database.models import IndexedFileModel
from app.services.preview import PreviewService
from app.ui.preview_panel import PreviewPanel, PreviewDialog


def test_preview_service_thumbnail_paths(tmp_path):
    """Verify PreviewService computes clean thumbnail paths."""
    manager = MagicMock()
    service = PreviewService(manager)
    service.thumbnails_dir = tmp_path

    thumb_path = service.get_thumbnail_path("photo_12345")
    assert thumb_path == tmp_path / "photo_12345.jpg"
    assert service.has_cached_thumbnail("photo_12345") is False

    # Create dummy thumbnail file
    thumb_path.write_bytes(b"dummy image bytes")
    assert service.has_cached_thumbnail("photo_12345") is True


def test_preview_service_open_nonexistent_file():
    """Verify opening non-existent file returns False safely."""
    res = PreviewService.open_in_system_viewer("C:/non/existent/path/file.pdf")
    assert res is False


def test_preview_panel_rendering(qapp):
    """Verify PreviewPanel displays metadata correctly."""
    panel = PreviewPanel()
    panel.show()

    # Initial state
    assert panel.btn_download.isEnabled() is False
    assert "No File Selected" in panel.thumb_label.text()

    # Set file model
    now = datetime(2026, 9, 16, 21, 0, tzinfo=timezone.utc)
    file_item = IndexedFileModel(
        id=1,
        file_id="doc_777",
        message_id=50,
        chat_id=-10055,
        chat_title="Project Alpha",
        filename="specs_v1.pdf",
        extension=".pdf",
        mime_type="application/pdf",
        file_size=2097152,  # 2 MB
        media_type="DOCUMENT",
        message_date=now,
        caption="Full project specifications document",
    )

    panel.set_file(file_item)

    assert panel.btn_download.isEnabled() is True
    assert "specs_v1.pdf" in panel.name_label.text()
    assert "2.00 MB" in panel.size_label.text()
    assert "Project Alpha" in panel.chat_label.text()
    assert ".pdf" in panel.mime_label.text()
    assert "Full project specifications document" in panel.caption_label.text()

    panel.close()


def test_preview_dialog_initialization(qapp):
    """Verify PreviewDialog renders for file inspect."""
    now = datetime.now(timezone.utc)
    file_item = IndexedFileModel(
        id=2,
        file_id="img_888",
        message_id=60,
        chat_id=-10066,
        chat_title="Photo Channel",
        filename="banner.png",
        extension=".png",
        mime_type="image/png",
        file_size=512000,
        media_type="IMAGE",
        message_date=now,
    )

    dialog = PreviewDialog(file_item)
    assert dialog is not None
    assert "banner.png" in dialog.windowTitle()
    dialog.close()
