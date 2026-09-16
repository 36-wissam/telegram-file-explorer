"""Telegram chat discovery service and data structures."""

import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Optional
from telethon.tl.types import Channel, Chat, User

from ..core.config import settings
from ..core.logger import get_logger
from .client import TelegramClientManager

logger = get_logger("telegram.chats")


class ChatType(str, Enum):
    """Categorized chat types."""
    USER = "User"
    BOT = "Bot"
    GROUP = "Group"
    SUPERGROUP = "Supergroup"
    CHANNEL = "Channel"
    SAVED_MESSAGES = "Saved Messages"


@dataclass
class TelegramChat:
    """Represents a discovered Telegram chat, group, or channel."""
    id: int
    title: str
    chat_type: ChatType
    unread_count: int = 0
    username: Optional[str] = None
    avatar_path: Optional[str] = None
    last_message_date: Optional[datetime] = None
    pinned: bool = False
    is_archived: bool = False

    @property
    def display_name(self) -> str:
        """Friendly display name for UI."""
        return self.title or (f"@{self.username}" if self.username else f"Chat {self.id}")


class TelegramChatService:
    """Service to discover and retrieve chats, channels, and groups."""

    def __init__(self, client_manager: TelegramClientManager):
        self.manager = client_manager
        self.avatars_dir: Path = self.manager.settings.data_dir / "cache" / "avatars"
        self.avatars_dir.mkdir(parents=True, exist_ok=True)

    @property
    def client(self):
        return self.manager.client

    def _determine_chat_type(self, entity, dialog) -> ChatType:
        """Determine specific type of chat from dialog and entity."""
        if dialog.is_user:
            if getattr(entity, "is_self", False):
                return ChatType.SAVED_MESSAGES
            if getattr(entity, "bot", False):
                return ChatType.BOT
            return ChatType.USER
        elif dialog.is_channel:
            if getattr(entity, "megagroup", False) or getattr(entity, "gigagroup", False):
                return ChatType.SUPERGROUP
            return ChatType.CHANNEL
        elif dialog.is_group:
            return ChatType.GROUP
        return ChatType.USER

    async def get_dialogs(self, limit: int = 150, download_avatars: bool = True) -> List[TelegramChat]:
        """Fetch all chats, channels, and groups accessible to the user.

        Args:
            limit: Maximum number of dialogs to fetch
            download_avatars: Whether to download profile photos to local cache

        Returns:
            List[TelegramChat]: List of discovered chat items
        """
        client = self.client
        if not client or not client.is_connected():
            raise RuntimeError("Telegram client is not connected.")

        logger.info("Fetching accessible chats from Telegram (limit=%d)...", limit)
        discovered_chats: List[TelegramChat] = []

        async for dialog in client.iter_dialogs(limit=limit):
            entity = dialog.entity
            chat_id = dialog.id
            chat_type = self._determine_chat_type(entity, dialog)

            title = dialog.name or ""
            if chat_type == ChatType.SAVED_MESSAGES:
                title = "Saved Messages"

            username = getattr(entity, "username", None)
            unread = dialog.unread_count or 0
            pinned = bool(dialog.pinned)
            is_archived = bool(dialog.archived)
            date = dialog.date

            # Avatar caching
            avatar_path = None
            if download_avatars:
                avatar_path = await self._get_or_download_avatar(entity, chat_id)

            chat = TelegramChat(
                id=chat_id,
                title=title,
                chat_type=chat_type,
                unread_count=unread,
                username=username,
                avatar_path=avatar_path,
                last_message_date=date,
                pinned=pinned,
                is_archived=is_archived,
            )
            discovered_chats.append(chat)

        logger.info("Discovered %d chats successfully.", len(discovered_chats))
        return discovered_chats

    async def _get_or_download_avatar(self, entity, chat_id: int) -> Optional[str]:
        """Retrieve cached avatar or download if not present."""
        target_file = self.avatars_dir / f"{chat_id}.jpg"
        if target_file.exists() and target_file.stat().st_size > 0:
            return str(target_file)

        try:
            # Download profile photo using Telethon's download_profile_photo
            res = await self.client.download_profile_photo(entity, file=str(target_file))
            if res and Path(res).exists():
                return str(res)
        except Exception as e:
            logger.debug("Could not download avatar for chat %s: %s", chat_id, e)

        return None
