"""Database repository for CRUD and querying operations using SQLAlchemy."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional, Tuple
from sqlalchemy import desc, asc, select, func
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from .connection import get_session, session_scope, init_db
from .models import ChatModel, IndexedFileModel, IndexingStateModel, AppSettingModel
from ..telegram.chats import TelegramChat, ChatType
from ..services.media_parser import MediaFileMetadata, MediaType
from ..core.logger import get_logger

logger = get_logger("database.repository")


class DatabaseRepository:
    """Repository providing data access methods across SQLAlchemy models."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path
        init_db(self.db_path)

    # --- Chat Operations ---
    def upsert_chat(self, chat: TelegramChat) -> None:
        """Insert or update a single Telegram chat."""
        with session_scope(self.db_path) as session:
            stmt = sqlite_insert(ChatModel).values(
                id=chat.id,
                title=chat.title,
                username=chat.username,
                chat_type=chat.chat_type.value,
                unread_count=chat.unread_count,
                avatar_path=chat.avatar_path,
                last_message_date=chat.last_message_date,
                pinned=chat.pinned,
                is_archived=chat.is_archived,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=[ChatModel.id],
                set_={
                    "title": stmt.excluded.title,
                    "username": stmt.excluded.username,
                    "chat_type": stmt.excluded.chat_type,
                    "unread_count": stmt.excluded.unread_count,
                    "avatar_path": stmt.excluded.avatar_path,
                    "last_message_date": stmt.excluded.last_message_date,
                    "pinned": stmt.excluded.pinned,
                    "is_archived": stmt.excluded.is_archived,
                    "updated_at": stmt.excluded.updated_at,
                },
            )
            session.execute(stmt)

    def upsert_chats(self, chats: List[TelegramChat]) -> int:
        """Bulk upsert list of discovered chats."""
        if not chats:
            return 0
        now = datetime.now(timezone.utc)
        with session_scope(self.db_path) as session:
            for chat in chats:
                stmt = sqlite_insert(ChatModel).values(
                    id=chat.id,
                    title=chat.title,
                    username=chat.username,
                    chat_type=chat.chat_type.value,
                    unread_count=chat.unread_count,
                    avatar_path=chat.avatar_path,
                    last_message_date=chat.last_message_date,
                    pinned=chat.pinned,
                    is_archived=chat.is_archived,
                    created_at=now,
                    updated_at=now,
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=[ChatModel.id],
                    set_={
                        "title": stmt.excluded.title,
                        "username": stmt.excluded.username,
                        "chat_type": stmt.excluded.chat_type,
                        "unread_count": stmt.excluded.unread_count,
                        "avatar_path": stmt.excluded.avatar_path,
                        "last_message_date": stmt.excluded.last_message_date,
                        "pinned": stmt.excluded.pinned,
                        "is_archived": stmt.excluded.is_archived,
                        "updated_at": stmt.excluded.updated_at,
                    },
                )
                session.execute(stmt)
        return len(chats)

    def get_chats(self, chat_type: Optional[str] = None) -> List[ChatModel]:
        """Fetch chats ordered by pinned and last activity."""
        session = get_session(self.db_path)
        try:
            query = session.query(ChatModel)
            if chat_type:
                query = query.filter(ChatModel.chat_type == chat_type)
            return query.order_by(desc(ChatModel.pinned), desc(ChatModel.last_message_date)).all()
        finally:
            session.close()

    def get_chat_by_id(self, chat_id: int) -> Optional[ChatModel]:
        """Fetch chat by ID."""
        session = get_session(self.db_path)
        try:
            return session.query(ChatModel).filter(ChatModel.id == chat_id).first()
        finally:
            session.close()

    # --- File & Media Operations ---
    def save_file(self, meta: MediaFileMetadata) -> None:
        """Insert or update a single file metadata entry."""
        with session_scope(self.db_path) as session:
            self._ensure_chat_exists(session, meta.chat_id, meta.chat_title)
            now = datetime.now(timezone.utc)
            stmt = sqlite_insert(IndexedFileModel).values(
                file_id=meta.file_id,
                message_id=meta.message_id,
                chat_id=meta.chat_id,
                chat_title=meta.chat_title,
                filename=meta.filename,
                extension=meta.extension,
                mime_type=meta.mime_type,
                file_size=meta.file_size,
                media_type=meta.media_type.value,
                message_date=meta.message_date,
                has_thumbnail=meta.has_thumbnail,
                thumbnail_path=meta.thumbnail_path,
                caption=meta.caption,
                sender_id=meta.sender_id,
                indexed_at=now,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=[IndexedFileModel.file_id],
                set_={
                    "filename": stmt.excluded.filename,
                    "file_size": stmt.excluded.file_size,
                    "caption": stmt.excluded.caption,
                    "has_thumbnail": stmt.excluded.has_thumbnail,
                    "indexed_at": stmt.excluded.indexed_at,
                },
            )
            session.execute(stmt)

    def save_files_batch(self, batch: List[MediaFileMetadata]) -> int:
        """Insert or update a batch of file records in a single transaction."""
        if not batch:
            return 0

        now = datetime.now(timezone.utc)
        with session_scope(self.db_path) as session:
            # Ensure parent chats exist to satisfy FK constraint
            chat_map = {}
            for item in batch:
                if item.chat_id not in chat_map:
                    chat_map[item.chat_id] = item.chat_title

            for cid, ctitle in chat_map.items():
                self._ensure_chat_exists(session, cid, ctitle)

            for meta in batch:
                stmt = sqlite_insert(IndexedFileModel).values(
                    file_id=meta.file_id,
                    message_id=meta.message_id,
                    chat_id=meta.chat_id,
                    chat_title=meta.chat_title,
                    filename=meta.filename,
                    extension=meta.extension,
                    mime_type=meta.mime_type,
                    file_size=meta.file_size,
                    media_type=meta.media_type.value if hasattr(meta.media_type, "value") else str(meta.media_type),
                    message_date=meta.message_date,
                    has_thumbnail=bool(getattr(meta, "has_thumbnail", False)),
                    thumbnail_path=meta.thumbnail_path,
                    caption=meta.caption,
                    sender_id=meta.sender_id,
                    indexed_at=now,
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=[IndexedFileModel.file_id],
                    set_={
                        "filename": stmt.excluded.filename,
                        "file_size": stmt.excluded.file_size,
                        "caption": stmt.excluded.caption,
                        "has_thumbnail": stmt.excluded.has_thumbnail,
                        "indexed_at": stmt.excluded.indexed_at,
                    },
                )
                session.execute(stmt)
        return len(batch)

    def _ensure_chat_exists(self, session, chat_id: int, chat_title: str) -> None:
        """Ensure parent chat row exists to satisfy foreign keys."""
        existing = session.query(ChatModel).filter(ChatModel.id == chat_id).first()
        if not existing:
            new_chat = ChatModel(
                id=chat_id,
                title=chat_title or f"Chat {chat_id}",
                chat_type="Unknown",
                unread_count=0,
            )
            session.add(new_chat)
            session.flush()

    def get_files_by_chat(
        self,
        chat_id: int,
        category: Optional[str] = None,
        sort_by: str = "date",
        sort_desc: bool = True,
        limit: int = 10000,
    ) -> List[IndexedFileModel]:
        """Fetch files for a specific chat with optional media category filtering."""
        return self.get_files(
            chat_id=chat_id,
            media_type=category,
            sort_by=sort_by,
            sort_desc=sort_desc,
            limit=limit,
        )

    def get_files(
        self,
        chat_id: Optional[int] = None,
        media_type: Optional[str] = None,
        search_query: Optional[str] = None,
        extension: Optional[str] = None,
        min_size: Optional[int] = None,
        max_size: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
        sort_by: str = "date",
        sort_desc: bool = True,
    ) -> List[IndexedFileModel]:
        """Fetch indexed files with faceted filtering, sorting, and pagination."""
        session = get_session(self.db_path)
        try:
            query = session.query(IndexedFileModel)

            if chat_id is not None:
                query = query.filter(IndexedFileModel.chat_id == chat_id)

            if media_type is not None:
                query = query.filter(IndexedFileModel.media_type == media_type.upper())

            if extension:
                clean_ext = extension if extension.startswith(".") else f".{extension}"
                query = query.filter(IndexedFileModel.extension == clean_ext.lower())

            if min_size is not None:
                query = query.filter(IndexedFileModel.file_size >= min_size)

            if max_size is not None:
                query = query.filter(IndexedFileModel.file_size <= max_size)

            if start_date is not None:
                query = query.filter(IndexedFileModel.message_date >= start_date)

            if end_date is not None:
                query = query.filter(IndexedFileModel.message_date <= end_date)

            if search_query:
                like_pattern = f"%{search_query.strip()}%"
                query = query.filter(
                    (IndexedFileModel.filename.ilike(like_pattern))
                    | (IndexedFileModel.caption.ilike(like_pattern))
                    | (IndexedFileModel.chat_title.ilike(like_pattern))
                )

            # Sorting
            sort_column = IndexedFileModel.message_date
            if sort_by == "name":
                sort_column = IndexedFileModel.filename
            elif sort_by == "size":
                sort_column = IndexedFileModel.file_size

            order_func = desc if sort_desc else asc
            query = query.order_by(order_func(sort_column))

            return query.limit(limit).offset(offset).all()
        finally:
            session.close()

    def get_files_count(
        self,
        chat_id: Optional[int] = None,
        media_type: Optional[str] = None,
        search_query: Optional[str] = None,
        extension: Optional[str] = None,
        min_size: Optional[int] = None,
        max_size: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> int:
        """Count total files matching filter criteria."""
        session = get_session(self.db_path)
        try:
            query = session.query(func.count(IndexedFileModel.id))

            if chat_id is not None:
                query = query.filter(IndexedFileModel.chat_id == chat_id)

            if media_type is not None:
                query = query.filter(IndexedFileModel.media_type == media_type.upper())

            if extension:
                clean_ext = extension if extension.startswith(".") else f".{extension}"
                query = query.filter(IndexedFileModel.extension == clean_ext.lower())

            if min_size is not None:
                query = query.filter(IndexedFileModel.file_size >= min_size)

            if max_size is not None:
                query = query.filter(IndexedFileModel.file_size <= max_size)

            if start_date is not None:
                query = query.filter(IndexedFileModel.message_date >= start_date)

            if end_date is not None:
                query = query.filter(IndexedFileModel.message_date <= end_date)

            if search_query:
                like_pattern = f"%{search_query.strip()}%"
                query = query.filter(
                    (IndexedFileModel.filename.ilike(like_pattern))
                    | (IndexedFileModel.caption.ilike(like_pattern))
                    | (IndexedFileModel.chat_title.ilike(like_pattern))
                )

            return query.scalar() or 0
        finally:
            session.close()

    # --- Resumable Indexing State ---
    def get_indexing_state(self, chat_id: int) -> Tuple[int, int, bool]:
        """Return (last_indexed_message_id, total_files_indexed, is_completed)."""
        session = get_session(self.db_path)
        try:
            state = session.query(IndexingStateModel).filter(IndexingStateModel.chat_id == chat_id).first()
            if state:
                return state.last_indexed_message_id, state.total_files_indexed, state.is_completed
            return 0, 0, False
        finally:
            session.close()

    def update_indexing_state(
        self,
        chat_id: int,
        chat_title: str,
        last_msg_id: int,
        new_files_count: int,
        is_completed: bool = False,
    ) -> None:
        """Update or insert indexing progress state for resumable scanning."""
        with session_scope(self.db_path) as session:
            self._ensure_chat_exists(session, chat_id, chat_title)
            now = datetime.now(timezone.utc)
            stmt = sqlite_insert(IndexingStateModel).values(
                chat_id=chat_id,
                chat_title=chat_title,
                last_indexed_message_id=last_msg_id,
                total_files_indexed=new_files_count,
                is_completed=is_completed,
                last_updated_at=now,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=[IndexingStateModel.chat_id],
                set_={
                    "chat_title": stmt.excluded.chat_title,
                    "last_indexed_message_id": stmt.excluded.last_indexed_message_id,
                    "total_files_indexed": IndexingStateModel.total_files_indexed + stmt.excluded.total_files_indexed,
                    "is_completed": stmt.excluded.is_completed,
                    "last_updated_at": stmt.excluded.last_updated_at,
                },
            )
            session.execute(stmt)

    # --- Application Settings ---
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Fetch setting value by key."""
        session = get_session(self.db_path)
        try:
            setting = session.query(AppSettingModel).filter(AppSettingModel.key == key).first()
            return setting.value if setting else default
        finally:
            session.close()

    def set_setting(self, key: str, value: Any) -> None:
        """Persist key-value setting."""
        with session_scope(self.db_path) as session:
            now = datetime.now(timezone.utc)
            stmt = sqlite_insert(AppSettingModel).values(
                key=key,
                value=str(value),
                updated_at=now,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=[AppSettingModel.key],
                set_={
                    "value": stmt.excluded.value,
                    "updated_at": stmt.excluded.updated_at,
                },
            )
            session.execute(stmt)
