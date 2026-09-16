"""Telegram message media identification and metadata extraction."""

import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional
from telethon.tl.types import (
    Document,
    DocumentAttributeAudio,
    DocumentAttributeFilename,
    DocumentAttributeVideo,
    MessageMediaDocument,
    MessageMediaPhoto,
    Photo,
    PhotoSize,
    PhotoSizeProgressive,
)

from ..core.logger import get_logger

logger = get_logger("services.media_parser")


class MediaType(str, Enum):
    """Normalized media categories."""
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"
    AUDIO = "AUDIO"
    VOICE = "VOICE"
    DOCUMENT = "DOCUMENT"
    ARCHIVE = "ARCHIVE"
    OTHER = "OTHER"


# Extension sets for classification
ARCHIVE_EXTENSIONS = {
    ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso", ".tgz", ".zst"
}
DOCUMENT_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".txt", ".csv", ".rtf", ".odt", ".ods", ".odp", ".epub", ".md"
}
IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".svg", ".ico", ".heic"
}
VIDEO_EXTENSIONS = {
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".3gp", ".ts"
}
AUDIO_EXTENSIONS = {
    ".mp3", ".flac", ".wav", ".m4a", ".aac", ".ogg", ".opus", ".wma", ".alac"
}


@dataclass
class MediaFileMetadata:
    """Standardized metadata extracted from a Telegram message containing media."""
    file_id: str
    message_id: int
    chat_id: int
    chat_title: str
    filename: str
    extension: str
    mime_type: str
    file_size: int
    media_type: MediaType
    message_date: datetime
    has_thumbnail: bool = False
    thumbnail_path: Optional[str] = None
    caption: Optional[str] = None
    sender_id: Optional[int] = None

    @property
    def human_size(self) -> str:
        """Format file size into human-readable string."""
        size = float(self.file_size)
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024.0 or unit == "TB":
                return f"{size:.2f} {unit}" if unit != "B" else f"{int(size)} B"
            size /= 1024.0
        return f"{self.file_size} B"


def classify_media_type(filename: str, mime_type: str, is_voice: bool = False, is_video: bool = False, is_audio: bool = False) -> tuple[MediaType, str]:
    """Classify media category and extract lowercase file extension."""
    ext = os.path.splitext(filename)[1].lower() if filename else ""

    if is_voice:
        return MediaType.VOICE, ext or ".ogg"
    if is_video or ext in VIDEO_EXTENSIONS or mime_type.startswith("video/"):
        return MediaType.VIDEO, ext or ".mp4"
    if is_audio or ext in AUDIO_EXTENSIONS or mime_type.startswith("audio/"):
        return MediaType.AUDIO, ext or ".mp3"
    if ext in ARCHIVE_EXTENSIONS or mime_type in ("application/zip", "application/x-rar-compressed", "application/x-7z-compressed", "application/x-tar"):
        return MediaType.ARCHIVE, ext or ".zip"
    if ext in IMAGE_EXTENSIONS or mime_type.startswith("image/"):
        return MediaType.IMAGE, ext or ".jpg"
    if ext in DOCUMENT_EXTENSIONS or mime_type in ("application/pdf", "application/msword", "text/plain", "text/csv"):
        return MediaType.DOCUMENT, ext or ".doc"

    return MediaType.OTHER, ext


def parse_message_media(message, chat_id: int, chat_title: str) -> Optional[MediaFileMetadata]:
    """Extract file and media metadata from a Telethon Message object.

    Does NOT download file content. Only inspects MTProto header metadata.
    """
    if not message or not getattr(message, "media", None):
        return None

    media = message.media
    msg_id = message.id
    msg_date = message.date
    caption = getattr(message, "message", None) or ""
    raw_sender_id = getattr(message, "sender_id", None)
    try:
        sender_id = int(raw_sender_id) if raw_sender_id is not None else None
    except (ValueError, TypeError):
        sender_id = None


    # 1. Handle Native Telegram Photo
    if isinstance(media, MessageMediaPhoto) or hasattr(media, "photo") and isinstance(media.photo, Photo):
        photo = media.photo if hasattr(media, "photo") else media
        if not photo or not isinstance(photo, Photo):
            return None

        file_id = f"photo_{photo.id}"
        # Determine size from the largest available size variant
        file_size = 0
        if getattr(photo, "sizes", None):
            for s in photo.sizes:
                if isinstance(s, (PhotoSize, PhotoSizeProgressive)):
                    if getattr(s, "size", 0) > file_size:
                        file_size = s.size

        filename = f"photo_{msg_id}.jpg"
        return MediaFileMetadata(
            file_id=file_id,
            message_id=msg_id,
            chat_id=chat_id,
            chat_title=chat_title,
            filename=filename,
            extension=".jpg",
            mime_type="image/jpeg",
            file_size=file_size,
            media_type=MediaType.IMAGE,
            message_date=msg_date,
            has_thumbnail=True,
            caption=caption,
            sender_id=sender_id,
        )

    # 2. Handle Telegram Document (files, videos, audios, archives, docs)
    if isinstance(media, MessageMediaDocument) or hasattr(media, "document") and isinstance(media.document, Document):
        doc = media.document if hasattr(media, "document") else media
        if not doc or not isinstance(doc, Document):
            return None

        file_id = f"doc_{doc.id}"
        file_size = doc.size or 0
        mime_type = doc.mime_type or "application/octet-stream"

        filename = None
        is_video = False
        is_audio = False
        is_voice = False

        # Inspect document attributes for filename and media flags
        if getattr(doc, "attributes", None):
            for attr in doc.attributes:
                if isinstance(attr, DocumentAttributeFilename):
                    filename = attr.file_name
                elif isinstance(attr, DocumentAttributeVideo):
                    is_video = True
                elif isinstance(attr, DocumentAttributeAudio):
                    if getattr(attr, "voice", False):
                        is_voice = True
                    else:
                        is_audio = True

        # Fallback filename if not provided in attributes
        if not filename:
            if is_video:
                filename = f"video_{msg_id}.mp4"
            elif is_voice:
                filename = f"voice_{msg_id}.ogg"
            elif is_audio:
                filename = f"audio_{msg_id}.mp3"
            elif mime_type.startswith("image/"):
                filename = f"image_{msg_id}.jpg"
            else:
                filename = f"file_{msg_id}.bin"

        media_type, ext = classify_media_type(
            filename=filename,
            mime_type=mime_type,
            is_voice=is_voice,
            is_video=is_video,
            is_audio=is_audio,
        )

        has_thumb = bool(getattr(doc, "thumbs", None))

        return MediaFileMetadata(
            file_id=file_id,
            message_id=msg_id,
            chat_id=chat_id,
            chat_title=chat_title,
            filename=filename,
            extension=ext,
            mime_type=mime_type,
            file_size=file_size,
            media_type=media_type,
            message_date=msg_date,
            has_thumbnail=has_thumb,
            caption=caption,
            sender_id=sender_id,
        )

    return None
