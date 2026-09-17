"""Indexing manager coordinating background media scanning, pause/resume, and UI progress reporting."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Callable, List, Optional
from PySide6.QtCore import QObject, Signal

from ..core.async_runner import async_runner
from ..core.config import settings
from ..core.logger import get_logger
from ..telegram.chats import TelegramChat
from ..telegram.client import TelegramClientManager
from .indexer import MediaIndexerService

logger = get_logger("services.indexing_manager")


class IndexingStatus(str, Enum):
    """Lifecycle states of the indexing engine."""
    IDLE = "Idle"
    RUNNING = "Running"
    PAUSED = "Paused"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"
    FAILED = "Failed"


@dataclass
class IndexingProgress:
    """Snapshot of current indexing operation progress."""
    status: IndexingStatus = IndexingStatus.IDLE
    current_chat_title: str = ""
    current_chat_id: Optional[int] = None
    chat_index: int = 0
    total_chats: int = 0
    chat_files_indexed: int = 0
    total_files_indexed: int = 0
    messages_scanned: int = 0
    status_message: str = "Ready"
    error_message: Optional[str] = None


class IndexingManager(QObject):
    """Manages chat indexing processes with full start/pause/resume/cancel controls and Qt signals."""

    status_changed = Signal(str)            # Emits IndexingStatus value
    progress_updated = Signal(object)       # Emits IndexingProgress
    chat_started = Signal(str, object, object) # Emits (chat_title, chat_index, total_chats)
    chat_completed = Signal(str, object)    # Emits (chat_title, files_indexed)
    batch_discovered = Signal(object, object) # Emits (chat_id, List[MediaFileMetadata])
    log_emitted = Signal(str)               # Emits timestamped activity message
    indexing_finished = Signal(object, bool) # Emits (total_files_indexed, is_cancelled)

    def __init__(self, client_manager: TelegramClientManager, db_path: Optional[Path] = None):
        super().__init__()
        self.client_manager = client_manager
        self.db_path = db_path or settings.database_path
        self.indexer = MediaIndexerService(self.client_manager, db_path=self.db_path)

        self.status = IndexingStatus.IDLE
        self.progress = IndexingProgress()

        self._pause_event: Optional[asyncio.Event] = None
        self._is_cancelled = False
        self._is_running = False

    @property
    def is_running(self) -> bool:
        """Check if indexing is actively running."""
        return self.status == IndexingStatus.RUNNING

    @property
    def is_paused(self) -> bool:
        """Check if indexing is paused."""
        return self.status == IndexingStatus.PAUSED

    def start_indexing(
        self,
        chats: List[TelegramChat],
        limit_per_chat: int = 500,
        reindex: bool = False,
    ) -> bool:
        """Start or resume background indexing for the provided chats."""
        if self.is_running:
            logger.warning("Indexing is already running.")
            return False

        if not chats:
            self._log("No chats provided for indexing.")
            return False

        self._is_cancelled = False
        self._is_running = True
        self.status = IndexingStatus.RUNNING
        self._pause_event = asyncio.Event()
        self._pause_event.set()
        self.status_changed.emit(self.status.value)

        self.progress = IndexingProgress(
            status=IndexingStatus.RUNNING,
            total_chats=len(chats),
            status_message=f"Starting indexing of {len(chats)} chats...",
        )
        self.progress_updated.emit(self.progress)
        self._log(f"Started indexing job ({len(chats)} chats, limit={limit_per_chat}, reindex={reindex}).")

        # Submit background task
        async_runner.run_coroutine_async(
            self._execute_indexing(chats, limit_per_chat, reindex),
            callback=self._on_indexing_done,
            error_callback=self._on_indexing_error,
        )
        return True

    def pause_indexing(self) -> bool:
        """Pause running indexing."""
        if self.status != IndexingStatus.RUNNING:
            return False

        if not self._pause_event:
            self._pause_event = asyncio.Event()

        self._pause_event.clear()
        self.status = IndexingStatus.PAUSED
        self.progress.status = self.status
        self.progress.status_message = "Indexing paused."
        self.status_changed.emit(self.status.value)
        self.progress_updated.emit(self.progress)
        self._log("Indexing paused.")
        return True

    def resume_indexing(self) -> bool:
        """Resume paused indexing."""
        if self.status != IndexingStatus.PAUSED:
            return False

        if not self._pause_event:
            self._pause_event = asyncio.Event()

        self._pause_event.set()
        self.status = IndexingStatus.RUNNING
        self.progress.status = self.status
        self.progress.status_message = "Indexing resumed."
        self.status_changed.emit(self.status.value)
        self.progress_updated.emit(self.progress)
        self._log("Indexing resumed.")
        return True

    def cancel_indexing(self) -> bool:
        """Cooperatively cancel the current indexing operation."""
        if self.status not in (IndexingStatus.RUNNING, IndexingStatus.PAUSED):
            return False

        self._is_cancelled = True
        if self._pause_event:
            self._pause_event.set()  # Unblock paused loop so it can exit

        self.status = IndexingStatus.CANCELLED
        self.progress.status = self.status
        self.progress.status_message = "Cancelling indexing..."
        self.status_changed.emit(self.status.value)
        self.progress_updated.emit(self.progress)
        self._log("Indexing cancellation requested.")
        return True

    def reset_chat(self, chat_id: int) -> None:
        """Reset indexing state for a specific chat."""
        self.indexer.reset_indexing_state(chat_id)
        self._log(f"Reset indexing state for chat_id={chat_id}.")

    def reset_all_chats(self) -> None:
        """Reset indexing state for all chats."""
        self.indexer.reset_indexing_state(None)
        self._log("Reset indexing state for all chats.")

    async def _execute_indexing(
        self,
        chats: List[TelegramChat],
        limit_per_chat: int,
        reindex: bool,
    ) -> int:
        """Async worker iterating through target chats."""
        self._pause_event = asyncio.Event()
        self._pause_event.set()

        total_files = 0
        total_scanned = 0

        if reindex:
            for c in chats:
                self.indexer.reset_indexing_state(c.id)

        for idx, chat in enumerate(chats, 1):
            if self._is_cancelled:
                self._log("Indexing halted: user cancelled.")
                break

            await self._pause_event.wait()

            self.progress.current_chat_title = chat.title
            self.progress.current_chat_id = chat.id
            self.progress.chat_index = idx
            self.progress.chat_files_indexed = 0
            self.progress.status_message = f"Indexing '{chat.title}' ({idx}/{len(chats)})..."
            self.progress_updated.emit(self.progress)
            self.chat_started.emit(chat.title, idx, len(chats))
            self._log(f"Scanning chat [{idx}/{len(chats)}]: {chat.title} (ID: {chat.id})")

            def on_chat_progress(new_files: int, scanned_msgs: int):
                self.progress.chat_files_indexed = new_files
                self.progress.messages_scanned = total_scanned + scanned_msgs
                self.progress.status_message = (
                    f"Indexing '{chat.title}': {new_files} files found, {scanned_msgs} messages checked"
                )
                self.progress_updated.emit(self.progress)

            try:
                chat_files = await self.indexer.index_chat(
                    chat_id=chat.id,
                    chat_title=chat.title,
                    limit=limit_per_chat,
                    progress_callback=on_chat_progress,
                    pause_event=self._pause_event,
                    cancel_check=lambda: self._is_cancelled,
                )
                total_files += chat_files
                self.progress.total_files_indexed = total_files
                self.chat_completed.emit(chat.title, chat_files)
                self._log(f"Finished '{chat.title}': {chat_files} new files indexed.")
            except Exception as exc:
                self._log(f"Error scanning '{chat.title}': {exc}")
                logger.error("Error scanning chat %s: %s", chat.title, exc)

        return total_files

    def _on_indexing_done(self, total_files: int):
        """Callback when async indexing completes."""
        self._is_running = False
        if self._is_cancelled:
            self.status = IndexingStatus.CANCELLED
            self.progress.status = IndexingStatus.CANCELLED
            self.progress.status_message = f"Indexing cancelled. Total files indexed: {total_files}."
        else:
            self.status = IndexingStatus.COMPLETED
            self.progress.status = IndexingStatus.COMPLETED
            self.progress.status_message = f"Indexing finished successfully! {total_files} files indexed."

        self.status_changed.emit(self.status.value)
        self.progress_updated.emit(self.progress)
        self.indexing_finished.emit(total_files, self._is_cancelled)
        self._log(f"Indexing job finished: {total_files} files total (Cancelled: {self._is_cancelled}).")

    def _on_indexing_error(self, exc: Exception):
        """Callback on unhandled indexing worker error."""
        self._is_running = False
        self.status = IndexingStatus.FAILED
        self.progress.status = IndexingStatus.FAILED
        self.progress.error_message = str(exc)
        self.progress.status_message = f"Indexing failed: {exc}"
        self.status_changed.emit(self.status.value)
        self.progress_updated.emit(self.progress)
        self._log(f"Indexing error: {exc}")

    def _log(self, text: str):
        """Format and emit timestamped log message."""
        now_str = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{now_str}] {text}"
        logger.info(formatted)
        self.log_emitted.emit(formatted)
