"""File preview service and thumbnail caching management."""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from ..core.config import settings
from ..core.logger import get_logger
from ..database.models import IndexedFileModel
from ..telegram.client import TelegramClientManager

logger = get_logger("services.preview")


class PreviewService:
    """Manages file thumbnails, media metadata inspection, and external file launch."""

    def __init__(self, client_manager: TelegramClientManager):
        self.manager = client_manager
        self.thumbnails_dir: Path = settings.data_dir / "cache" / "thumbnails"
        self.thumbnails_dir.mkdir(parents=True, exist_ok=True)

    def get_thumbnail_path(self, file_id: str) -> Path:
        """Return the local file path for a cached thumbnail."""
        clean_name = "".join(c for c in file_id if c.isalnum() or c in ("-", "_"))
        return self.thumbnails_dir / f"{clean_name}.jpg"

    def has_cached_thumbnail(self, file_id: str) -> bool:
        """Check if thumbnail is already cached locally."""
        thumb = self.get_thumbnail_path(file_id)
        return thumb.exists() and thumb.stat().st_size > 0

    async def fetch_thumbnail(self, chat_id: int, message_id: int, file_id: str) -> Optional[str]:
        """Download only the small embedded thumbnail for a message without downloading full media."""
        thumb_path = self.get_thumbnail_path(file_id)
        if thumb_path.exists() and thumb_path.stat().st_size > 0:
            return str(thumb_path)

        client = self.manager.client
        if not client or not client.is_connected():
            return None

        try:
            message = await client.get_messages(chat_id, ids=message_id)
            if not message or not message.media:
                return None

            # Download thumbnail only using Telethon thumb parameter
            res = await client.download_media(message, file=str(thumb_path), thumb=-1)
            if res and Path(res).exists():
                logger.debug("Cached thumbnail for %s at %s", file_id, res)
                return str(res)
        except Exception as e:
            logger.debug("Failed fetching thumbnail for message %d: %s", message_id, e)

        return None

    @staticmethod
    def open_in_system_viewer(file_path: str) -> bool:
        """Open a local file in the system default application (e.g. PDF viewer, photo viewer)."""
        if not file_path or not Path(file_path).exists():
            return False

        try:
            # Use Qt QDesktopServices for platform-independent opening
            url = QUrl.fromLocalFile(os.path.abspath(file_path))
            success = QDesktopServices.openUrl(url)
            if not success and sys.platform == "win32":
                os.startfile(file_path)
                success = True
            return success
        except Exception as e:
            logger.error("Failed opening file %s: %s", file_path, e)
            return False
