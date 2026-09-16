"""Asynchronous Telegram file download manager with progress and speed tracking."""

import asyncio
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Dict, List, Optional
from PySide6.QtCore import QObject, Signal

from ..core.async_runner import async_runner
from ..core.config import settings
from ..core.logger import get_logger
from ..telegram.client import TelegramClientManager

logger = get_logger("services.downloader")


class DownloadStatus(str, Enum):
    """Status states of a download task."""
    QUEUED = "Queued"
    DOWNLOADING = "Downloading"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"
    FAILED = "Failed"


@dataclass
class DownloadTask:
    """Represents an active or finished download task."""
    task_id: str
    file_id: str
    chat_id: int
    message_id: int
    filename: str
    destination_path: Path
    total_bytes: int = 0
    downloaded_bytes: int = 0
    speed_bytes_per_sec: float = 0.0
    progress_percent: float = 0.0
    status: DownloadStatus = DownloadStatus.QUEUED
    error_message: Optional[str] = None
    start_time: Optional[float] = None
    last_update_time: Optional[float] = None
    last_downloaded_bytes: int = 0
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)

    @property
    def human_downloaded(self) -> str:
        from ..ui.file_explorer import format_bytes
        return format_bytes(self.downloaded_bytes)

    @property
    def human_total(self) -> str:
        from ..ui.file_explorer import format_bytes
        return format_bytes(self.total_bytes)

    @property
    def human_speed(self) -> str:
        from ..ui.file_explorer import format_bytes
        return f"{format_bytes(int(self.speed_bytes_per_sec))}/s"


class DownloadManager(QObject):
    """Coordinates asynchronous file downloads from Telegram with Qt Signal reporting."""

    task_added = Signal(object)      # Emits DownloadTask
    task_updated = Signal(object)    # Emits DownloadTask
    task_completed = Signal(object)  # Emits DownloadTask
    task_failed = Signal(object)     # Emits DownloadTask

    def __init__(self, client_manager: TelegramClientManager):
        super().__init__()
        self.client_manager = client_manager
        self.tasks: Dict[str, DownloadTask] = {}

    def get_all_tasks(self) -> List[DownloadTask]:
        """Return list of all registered download tasks."""
        return list(self.tasks.values())

    def start_download(
        self,
        chat_id: int,
        message_id: int,
        file_id: str,
        filename: str,
        destination_dir: Optional[Path] = None,
        total_size: int = 0,
    ) -> DownloadTask:
        """Create and begin an asynchronous download task."""
        target_dir = destination_dir or settings.download_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        dest_file = target_dir / filename

        task_id = f"{chat_id}_{message_id}_{file_id}"
        task = DownloadTask(
            task_id=task_id,
            file_id=file_id,
            chat_id=chat_id,
            message_id=message_id,
            filename=filename,
            destination_path=dest_file,
            total_bytes=total_size,
            status=DownloadStatus.QUEUED,
        )

        self.tasks[task_id] = task
        self.task_added.emit(task)

        # Launch download in background async loop
        async_runner.run_coroutine_async(self._execute_download(task))
        return task

    def cancel_download(self, task_id: str) -> bool:
        """Cancel a running or queued download task."""
        task = self.tasks.get(task_id)
        if task and task.status in (DownloadStatus.QUEUED, DownloadStatus.DOWNLOADING):
            task.cancel_event.set()
            task.status = DownloadStatus.CANCELLED
            self.task_updated.emit(task)
            logger.info("Cancelled download task %s", task_id)
            return True
        return False

    def retry_download(self, task_id: str) -> bool:
        """Retry a failed or cancelled download task."""
        task = self.tasks.get(task_id)
        if task and task.status in (DownloadStatus.FAILED, DownloadStatus.CANCELLED):
            task.cancel_event = asyncio.Event()
            task.status = DownloadStatus.QUEUED
            task.error_message = None
            task.downloaded_bytes = 0
            task.progress_percent = 0.0
            task.speed_bytes_per_sec = 0.0
            self.task_updated.emit(task)
            async_runner.run_coroutine_async(self._execute_download(task))
            return True
        return False

    async def _execute_download(self, task: DownloadTask):
        """Asynchronously perform the download via Telethon."""
        client = self.client_manager.client
        if not client or not client.is_connected():
            task.status = DownloadStatus.FAILED
            task.error_message = "Telegram client is not connected."
            self.task_failed.emit(task)
            return

        task.status = DownloadStatus.DOWNLOADING
        task.start_time = time.time()
        task.last_update_time = task.start_time
        task.last_downloaded_bytes = 0
        self.task_updated.emit(task)

        def telethon_progress_callback(received_bytes: int, total: int):
            if task.cancel_event.is_set():
                raise asyncio.CancelledError("User requested cancellation.")

            now = time.time()
            task.downloaded_bytes = received_bytes
            task.total_bytes = total or task.total_bytes

            if task.total_bytes > 0:
                task.progress_percent = (received_bytes / task.total_bytes) * 100.0

            # Calculate speed every 0.5 seconds
            delta_time = now - (task.last_update_time or now)
            if delta_time >= 0.5:
                bytes_diff = received_bytes - task.last_downloaded_bytes
                task.speed_bytes_per_sec = max(0.0, bytes_diff / delta_time)
                task.last_update_time = now
                task.last_downloaded_bytes = received_bytes
                self.task_updated.emit(task)

        try:
            message = await client.get_messages(task.chat_id, ids=task.message_id)
            if not message or not message.media:
                raise ValueError("Message does not contain media to download.")

            logger.info("Starting download for %s -> %s", task.filename, task.destination_path)
            res = await client.download_media(
                message,
                file=str(task.destination_path),
                progress_callback=telethon_progress_callback,
            )

            if res and Path(res).exists():
                task.status = DownloadStatus.COMPLETED
                task.downloaded_bytes = task.total_bytes
                task.progress_percent = 100.0
                task.speed_bytes_per_sec = 0.0
                logger.info("Successfully downloaded %s", task.destination_path)
                self.task_completed.emit(task)
                self.task_updated.emit(task)
            else:
                raise IOError("Downloaded file could not be verified on disk.")

        except asyncio.CancelledError:
            task.status = DownloadStatus.CANCELLED
            # Remove partial download file if cancelled
            if task.destination_path.exists():
                try:
                    task.destination_path.unlink()
                except Exception:
                    pass
            self.task_updated.emit(task)

        except Exception as e:
            logger.error("Download failed for %s: %s", task.filename, e)
            task.status = DownloadStatus.FAILED
            task.error_message = str(e)
            self.task_failed.emit(task)
            self.task_updated.emit(task)
