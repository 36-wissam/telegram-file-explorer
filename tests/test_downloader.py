"""Unit tests for Stage 10: File Download Manager."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
from PySide6.QtWidgets import QApplication

from app.services.downloader import DownloadManager, DownloadStatus, DownloadTask
from app.ui.download_manager import DownloadManagerDialog, DownloadRowWidget


def test_download_task_properties(tmp_path):
    """Verify DownloadTask metadata and formatting properties."""
    task = DownloadTask(
        task_id="test_task_1",
        file_id="doc_999",
        chat_id=-1001,
        message_id=45,
        filename="big_archive.zip",
        destination_path=tmp_path / "big_archive.zip",
        total_bytes=104857600,  # 100MB
        downloaded_bytes=52428800,  # 50MB
        speed_bytes_per_sec=5242880,  # 5MB/s
        progress_percent=50.0,
        status=DownloadStatus.DOWNLOADING,
    )

    assert task.human_downloaded == "50.0 MB"
    assert task.human_total == "100.0 MB"
    assert "5.0 MB/s" in task.human_speed
    assert task.status == DownloadStatus.DOWNLOADING


def test_download_manager_start_and_cancel(tmp_path):
    """Verify starting and cancelling a download task."""
    client_manager = MagicMock()
    client = MagicMock()
    client.is_connected.return_value = True
    client.get_messages = AsyncMock()
    
    async def fake_download(*args, **kwargs):
        await asyncio.sleep(0.5)
        return str(tmp_path / "test_file.pdf")
    client.download_media = AsyncMock(side_effect=fake_download)
    client_manager.client = client

    manager = DownloadManager(client_manager)

    task = manager.start_download(
        chat_id=-1001,
        message_id=10,
        file_id="doc_10",
        filename="test_file.pdf",
        destination_dir=tmp_path,
        total_size=10240,
    )

    assert task.task_id == "-1001_10_doc_10"
    assert len(manager.get_all_tasks()) == 1

    # Cancel task
    cancelled = manager.cancel_download(task.task_id)
    assert cancelled is True
    assert task.status == DownloadStatus.CANCELLED


def test_download_manager_retry(tmp_path):
    """Verify retrying a failed or cancelled task."""
    client_manager = MagicMock()
    manager = DownloadManager(client_manager)

    task = DownloadTask(
        task_id="task_fail",
        file_id="doc_fail",
        chat_id=1,
        message_id=2,
        filename="fail.bin",
        destination_path=tmp_path / "fail.bin",
        status=DownloadStatus.FAILED,
        error_message="Connection timed out",
    )
    manager.tasks[task.task_id] = task

    with patch("app.services.downloader.async_runner.run_coroutine_async"):
        success = manager.retry_download(task.task_id)
        assert success is True
        assert task.status == DownloadStatus.QUEUED
        assert task.error_message is None


def test_download_dialog_ui(qapp, tmp_path):
    """Verify DownloadManagerDialog renders active tasks."""
    client_manager = MagicMock()
    manager = DownloadManager(client_manager)

    task = DownloadTask(
        task_id="t1",
        file_id="f1",
        chat_id=-1001,
        message_id=10,
        filename="report.pdf",
        destination_path=tmp_path / "report.pdf",
        total_bytes=2048,
        downloaded_bytes=1024,
        progress_percent=50.0,
        status=DownloadStatus.DOWNLOADING,
    )
    manager.tasks[task.task_id] = task

    dialog = DownloadManagerDialog(manager)
    dialog.show()

    assert dialog.list_widget.count() == 1
    assert "1 downloading" in dialog.status_summary.text()

    dialog.close()
