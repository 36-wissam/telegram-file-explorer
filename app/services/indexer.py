"""Telegram media indexing engine with resumable SQLite storage."""

import asyncio
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional, Tuple
from telethon.errors import FloodWaitError

from ..core.config import settings
from ..core.logger import get_logger
from ..telegram.client import TelegramClientManager
from .media_parser import MediaFileMetadata, MediaType, parse_message_media

logger = get_logger("services.indexer")


class MediaIndexerService:
    """Scans accessible Telegram messages and indexes media metadata into SQLite."""

    def __init__(self, client_manager: TelegramClientManager, db_path: Optional[Path] = None):
        self.manager = client_manager
        self.db_path = db_path or settings.database_path
        self._init_sqlite()

    def _get_connection(self) -> sqlite3.Connection:
        """Create a sqlite3 connection with WAL mode, 64MB cache, and row factory."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA cache_size=-64000;")
        conn.execute("PRAGMA temp_store=MEMORY;")
        conn.execute("PRAGMA mmap_size=268435456;")
        return conn

    def _init_sqlite(self) -> None:
        """Initialize SQLite tables and indexes."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Files metadata table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS indexed_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id TEXT UNIQUE NOT NULL,
                    message_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    chat_title TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    extension TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    media_type TEXT NOT NULL,
                    message_date TEXT NOT NULL,
                    has_thumbnail INTEGER NOT NULL DEFAULT 0,
                    thumbnail_path TEXT,
                    caption TEXT,
                    sender_id INTEGER,
                    indexed_at TEXT NOT NULL
                );
                """
            )

            # Indexes for fast querying & deduplication
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_chat ON indexed_files (chat_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_type ON indexed_files (media_type);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_date ON indexed_files (message_date);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_msg ON indexed_files (chat_id, message_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_chat_type_date ON indexed_files (chat_id, media_type, message_date);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_size_date ON indexed_files (file_size, message_date);")

            # Resumable indexing state table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS indexing_state (
                    chat_id INTEGER PRIMARY KEY,
                    chat_title TEXT NOT NULL,
                    last_indexed_message_id INTEGER NOT NULL DEFAULT 0,
                    total_files_indexed INTEGER NOT NULL DEFAULT 0,
                    is_completed INTEGER NOT NULL DEFAULT 0,
                    last_updated_at TEXT NOT NULL
                );
                """
            )
            conn.commit()
            logger.debug("SQLite indexing tables initialized successfully.")

    def get_indexing_state(self, chat_id: int) -> Tuple[int, int, bool]:
        """Get (last_indexed_message_id, total_files_indexed, is_completed)."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT last_indexed_message_id, total_files_indexed, is_completed FROM indexing_state WHERE chat_id = ?;",
                (chat_id,),
            ).fetchone()
            if row:
                return row["last_indexed_message_id"], row["total_files_indexed"], bool(row["is_completed"])
            return 0, 0, False

    def save_file_metadata(self, meta: MediaFileMetadata) -> bool:
        """Insert or replace a single file's metadata."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO indexed_files (
                    file_id, message_id, chat_id, chat_title, filename,
                    extension, mime_type, file_size, media_type, message_date,
                    has_thumbnail, thumbnail_path, caption, sender_id, indexed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(file_id) DO UPDATE SET
                    filename=excluded.filename,
                    file_size=excluded.file_size,
                    caption=excluded.caption,
                    has_thumbnail=excluded.has_thumbnail,
                    indexed_at=excluded.indexed_at;
                """,
                (
                    meta.file_id,
                    meta.message_id,
                    meta.chat_id,
                    meta.chat_title,
                    meta.filename,
                    meta.extension,
                    meta.mime_type,
                    meta.file_size,
                    meta.media_type.value,
                    meta.message_date.isoformat() if isinstance(meta.message_date, datetime) else str(meta.message_date),
                    1 if meta.has_thumbnail else 0,
                    meta.thumbnail_path,
                    meta.caption,
                    meta.sender_id,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()
            return True

    def save_batch_files(self, batch: List[MediaFileMetadata]) -> int:
        """Insert a batch of media files within a single transaction."""
        if not batch:
            return 0

        now_str = datetime.now(timezone.utc).isoformat()
        rows = [
            (
                m.file_id,
                m.message_id,
                m.chat_id,
                m.chat_title,
                m.filename,
                m.extension,
                m.mime_type,
                m.file_size,
                m.media_type.value,
                m.message_date.isoformat() if isinstance(m.message_date, datetime) else str(m.message_date),
                1 if m.has_thumbnail else 0,
                m.thumbnail_path,
                m.caption,
                m.sender_id,
                now_str,
            )
            for m in batch
        ]

        with self._get_connection() as conn:
            conn.executemany(
                """
                INSERT INTO indexed_files (
                    file_id, message_id, chat_id, chat_title, filename,
                    extension, mime_type, file_size, media_type, message_date,
                    has_thumbnail, thumbnail_path, caption, sender_id, indexed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(file_id) DO UPDATE SET
                    filename=excluded.filename,
                    file_size=excluded.file_size,
                    caption=excluded.caption,
                    has_thumbnail=excluded.has_thumbnail,
                    indexed_at=excluded.indexed_at;
                """,
                rows,
            )
            conn.commit()
        return len(batch)

    def update_indexing_state(self, chat_id: int, chat_title: str, last_msg_id: int, new_files_count: int, is_completed: bool = False) -> None:
        """Update resumable indexing checkpoint in SQLite."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO indexing_state (chat_id, chat_title, last_indexed_message_id, total_files_indexed, is_completed, last_updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    chat_title=excluded.chat_title,
                    last_indexed_message_id=excluded.last_indexed_message_id,
                    total_files_indexed = total_files_indexed + excluded.total_files_indexed,
                    is_completed=excluded.is_completed,
                    last_updated_at=excluded.last_updated_at;
                """,
                (
                    chat_id,
                    chat_title,
                    last_msg_id,
                    new_files_count,
                    1 if is_completed else 0,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()

    def reset_indexing_state(self, chat_id: Optional[int] = None) -> None:
        """Reset resumable indexing checkpoint for a single chat or all chats."""
        with self._get_connection() as conn:
            if chat_id is not None:
                conn.execute(
                    "UPDATE indexing_state SET last_indexed_message_id = 0, is_completed = 0 WHERE chat_id = ?;",
                    (chat_id,),
                )
            else:
                conn.execute("UPDATE indexing_state SET last_indexed_message_id = 0, is_completed = 0;")
            conn.commit()

    async def index_chat(
        self,
        chat_id: int,
        chat_title: str,
        limit: int = 500,
        batch_size: int = 50,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        batch_discovered_callback: Optional[Callable[[List[MediaFileMetadata]], None]] = None,
        pause_event: Optional[asyncio.Event] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> int:
        """Scan messages in a chat from the last checkpoint and index media metadata.

        Supports safe resumption, pause/resume, and cooperative cancellation.
        Does NOT download files.
        """
        client = self.manager.client
        if not client or not client.is_connected():
            raise RuntimeError("Telegram client is not connected.")

        last_id, total_indexed_before, _ = self.get_indexing_state(chat_id)
        logger.info(
            "Starting indexing for '%s' (chat_id=%d) from message_id=%d...",
            chat_title,
            chat_id,
            last_id,
        )

        current_batch: List[MediaFileMetadata] = []
        newly_indexed = 0
        latest_scanned_id = last_id
        messages_scanned = 0

        # iter_messages with min_id=last_id and reverse=True indexes chronological forward from last checkpoint
        try:
            async for message in client.iter_messages(chat_id, min_id=last_id, limit=limit, reverse=True):
                if cancel_check and cancel_check():
                    logger.info("Indexing cancelled by user for chat %s", chat_title)
                    break

                if pause_event:
                    await pause_event.wait()

                messages_scanned += 1
                if message.id > latest_scanned_id:
                    latest_scanned_id = message.id

                meta = parse_message_media(message, chat_id, chat_title)
                if meta:
                    current_batch.append(meta)
                    newly_indexed += 1

                    if len(current_batch) >= batch_size:
                        self.save_batch_files(current_batch)
                        self.update_indexing_state(chat_id, chat_title, latest_scanned_id, len(current_batch), is_completed=False)
                        if batch_discovered_callback:
                            batch_discovered_callback(list(current_batch))
                        current_batch.clear()

                        if progress_callback:
                            progress_callback(newly_indexed, messages_scanned)
        except FloodWaitError as fwe:
            logger.warning("FloodWait encountered for '%s': must wait %d seconds.", chat_title, fwe.seconds)
            if current_batch:
                self.save_batch_files(current_batch)
                self.update_indexing_state(chat_id, chat_title, latest_scanned_id, len(current_batch), is_completed=False)
                if batch_discovered_callback:
                    batch_discovered_callback(list(current_batch))
                current_batch.clear()

            if fwe.seconds <= 30:
                logger.info("Automatically waiting %d seconds for flood backoff...", fwe.seconds + 1)
                await asyncio.sleep(fwe.seconds + 1)
            else:
                raise

        # Flush remaining batch
        if current_batch:
            self.save_batch_files(current_batch)
            self.update_indexing_state(chat_id, chat_title, latest_scanned_id, len(current_batch), is_completed=False)
            if batch_discovered_callback:
                batch_discovered_callback(list(current_batch))
            current_batch.clear()

        # Mark completed if scan was not cancelled and covered limit or exhausted messages
        was_cancelled = cancel_check() if cancel_check else False
        is_done = (not was_cancelled) and (messages_scanned < limit)
        self.update_indexing_state(chat_id, chat_title, latest_scanned_id, 0, is_completed=is_done)

        logger.info(
            "Indexing completed for '%s': scanned %d messages, indexed %d files.",
            chat_title,
            messages_scanned,
            newly_indexed,
        )
        return newly_indexed

    def get_indexed_files(
        self,
        chat_id: Optional[int] = None,
        media_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[dict]:
        """Query indexed file records."""
        query = "SELECT * FROM indexed_files WHERE 1=1"
        params = []

        if chat_id is not None:
            query += " AND chat_id = ?"
            params.append(chat_id)

        if media_type is not None:
            query += " AND media_type = ?"
            params.append(media_type.upper())

        query += " ORDER BY message_date DESC LIMIT ? OFFSET ?;"
        params.extend([limit, offset])

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def get_total_indexed_count(self, chat_id: Optional[int] = None) -> int:
        """Return total number of indexed files."""
        query = "SELECT COUNT(*) as cnt FROM indexed_files"
        params = []
        if chat_id is not None:
            query += " WHERE chat_id = ?"
            params.append(chat_id)

        with self._get_connection() as conn:
            row = conn.execute(query, params).fetchone()
            return row["cnt"] if row else 0
