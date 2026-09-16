"""SQLAlchemy models for Telegram File Explorer."""

from datetime import datetime, timezone
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from .connection import Base


def utcnow():
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


class ChatModel(Base):
    """Stores discovered Telegram chats, groups, and channels."""

    __tablename__ = "chats"

    id = Column(BigInteger, primary_key=True, autoincrement=False)
    title = Column(String(255), nullable=False, index=True)
    username = Column(String(128), nullable=True, index=True)
    chat_type = Column(String(64), nullable=False, index=True)
    unread_count = Column(Integer, default=0, nullable=False)
    avatar_path = Column(String(512), nullable=True)
    last_message_date = Column(DateTime, nullable=True)
    pinned = Column(Boolean, default=False, nullable=False)
    is_archived = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    files = relationship(
        "IndexedFileModel",
        back_populates="chat",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    indexing_state = relationship(
        "IndexingStateModel",
        back_populates="chat",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "username": self.username,
            "chat_type": self.chat_type,
            "unread_count": self.unread_count,
            "avatar_path": self.avatar_path,
            "last_message_date": self.last_message_date.isoformat() if self.last_message_date else None,
            "pinned": self.pinned,
            "is_archived": self.is_archived,
        }


class IndexedFileModel(Base):
    """Stores indexed media and file metadata from Telegram messages."""

    __tablename__ = "indexed_files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(String(128), unique=True, nullable=False, index=True)
    message_id = Column(BigInteger, nullable=False, index=True)
    chat_id = Column(BigInteger, ForeignKey("chats.id", ondelete="CASCADE"), nullable=False, index=True)
    chat_title = Column(String(255), nullable=False)
    filename = Column(String(512), nullable=False, index=True)
    extension = Column(String(32), nullable=False, index=True)
    mime_type = Column(String(128), nullable=False, index=True)
    file_size = Column(BigInteger, nullable=False, index=True)
    media_type = Column(String(32), nullable=False, index=True)
    message_date = Column(DateTime, nullable=False, index=True)
    has_thumbnail = Column(Boolean, default=False, nullable=False)
    thumbnail_path = Column(String(512), nullable=True)
    caption = Column(Text, nullable=True)
    sender_id = Column(BigInteger, nullable=True)
    indexed_at = Column(DateTime, default=utcnow, nullable=False)

    # Relationship
    chat = relationship("ChatModel", back_populates="files")

    # Composite indexes for high-speed faceted search & ordering
    __table_args__ = (
        Index("idx_files_chat_msg", "chat_id", "message_id"),
        Index("idx_files_type_date", "media_type", "message_date"),
        Index("idx_files_ext_size", "extension", "file_size"),
        Index("idx_files_search", "filename", "media_type", "chat_id"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "file_id": self.file_id,
            "message_id": self.message_id,
            "chat_id": self.chat_id,
            "chat_title": self.chat_title,
            "filename": self.filename,
            "extension": self.extension,
            "mime_type": self.mime_type,
            "file_size": self.file_size,
            "media_type": self.media_type,
            "message_date": self.message_date.isoformat() if self.message_date else None,
            "has_thumbnail": self.has_thumbnail,
            "thumbnail_path": self.thumbnail_path,
            "caption": self.caption,
            "sender_id": self.sender_id,
            "indexed_at": self.indexed_at.isoformat() if self.indexed_at else None,
        }


class IndexingStateModel(Base):
    """Tracks resumable indexing checkpoints per chat."""

    __tablename__ = "indexing_state"

    chat_id = Column(BigInteger, ForeignKey("chats.id", ondelete="CASCADE"), primary_key=True)
    chat_title = Column(String(255), nullable=False)
    last_indexed_message_id = Column(BigInteger, default=0, nullable=False, index=True)
    total_files_indexed = Column(Integer, default=0, nullable=False)
    is_completed = Column(Boolean, default=False, nullable=False)
    last_updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    # Relationship
    chat = relationship("ChatModel", back_populates="indexing_state")

    def to_dict(self):
        return {
            "chat_id": self.chat_id,
            "chat_title": self.chat_title,
            "last_indexed_message_id": self.last_indexed_message_id,
            "total_files_indexed": self.total_files_indexed,
            "is_completed": self.is_completed,
            "last_updated_at": self.last_updated_at.isoformat() if self.last_updated_at else None,
        }


class AppSettingModel(Base):
    """Key-value application settings stored in SQLite."""

    __tablename__ = "app_settings"

    key = Column(String(128), primary_key=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    def to_dict(self):
        return {
            "key": self.key,
            "value": self.value,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
