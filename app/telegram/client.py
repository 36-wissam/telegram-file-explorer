"""Telegram client manager using Telethon."""

import re
from pathlib import Path
from typing import Optional
from telethon import TelegramClient

from ..core.config import Settings, settings as global_settings
from ..core.logger import get_logger
from .exceptions import (
    ConfigurationError,
    InvalidApiIdError,
    InvalidApiHashError,
    MissingCredentialsError,
    TelegramClientError,
)

logger = get_logger("telegram.client")

# Telegram API hash is typically a 32-character hexadecimal string
API_HASH_REGEX = re.compile(r"^[a-fA-F0-9]{32}$")


def validate_api_credentials(api_id: Optional[int], api_hash: Optional[str]) -> tuple[int, str]:
    """Validate Telegram API ID and API Hash.

    Args:
        api_id: The application ID from my.telegram.org
        api_hash: The application secret hash from my.telegram.org

    Returns:
        tuple[int, str]: Validated (api_id, api_hash)

    Raises:
        MissingCredentialsError: If either credential is empty or None
        InvalidApiIdError: If api_id is not a positive integer
        InvalidApiHashError: If api_hash is not a valid 32-character hex string
    """
    if api_id is None or api_hash is None:
        raise MissingCredentialsError()

    # Validate API ID
    try:
        validated_id = int(api_id)
        if validated_id <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        raise InvalidApiIdError(api_id)

    # Validate API Hash
    clean_hash = str(api_hash).strip()
    if not clean_hash or not API_HASH_REGEX.match(clean_hash):
        raise InvalidApiHashError(api_hash)

    return validated_id, clean_hash


class TelegramClientManager:
    """Manages Telethon MTProto client lifecycle and local session storage."""

    def __init__(self, config: Optional[Settings] = None):
        self.settings = config or global_settings
        self._client: Optional[TelegramClient] = None
        self._api_id: Optional[int] = None
        self._api_hash: Optional[str] = None

    @property
    def client(self) -> Optional[TelegramClient]:
        """Return the active Telethon client instance if initialized."""
        return self._client

    @property
    def is_initialized(self) -> bool:
        """Check if client instance has been created."""
        return self._client is not None

    @property
    def session_file_path(self) -> Path:
        """Absolute path to the local SQLite session file (.session)."""
        return self.settings.sessions_dir / f"{self.settings.session_name}.session"

    def initialize_client(
        self,
        api_id: Optional[int] = None,
        api_hash: Optional[str] = None,
        session_name: Optional[str] = None,
    ) -> TelegramClient:
        """Initialize the Telethon MTProto client with local session storage.

        Args:
            api_id: Optional override for Telegram API ID
            api_hash: Optional override for Telegram API Hash
            session_name: Optional override for session file name

        Returns:
            TelegramClient: Initialized Telethon client instance

        Raises:
            ConfigurationError: If credentials fail validation
            TelegramClientError: If client fails to instantiate
        """
        target_id = api_id if api_id is not None else self.settings.api_id
        target_hash = api_hash if api_hash is not None else self.settings.api_hash

        # Validate credentials with clear error messages
        self._api_id, self._api_hash = validate_api_credentials(target_id, target_hash)

        # Update session name if provided
        if session_name:
            self.settings.session_name = session_name

        # Ensure secure local session directory exists
        self.settings.ensure_directories()

        # Telethon uses string session path without appending extra .session
        session_target = str(self.settings.sessions_dir / self.settings.session_name)

        logger.info(
            "Initializing Telethon client with session: %s (API ID: %d)",
            self.session_file_path,
            self._api_id,
        )

        try:
            self._client = TelegramClient(
                session=session_target,
                api_id=self._api_id,
                api_hash=self._api_hash,
                device_model="Desktop",
                system_version="Windows",
                app_version=self.settings.app_version,
            )
            return self._client
        except Exception as e:
            logger.error("Failed to initialize Telethon client: %s", e)
            raise TelegramClientError(f"Telethon client initialization failed: {e}") from e

    async def is_authorized(self) -> bool:
        """Check if the current local session is authorized with Telegram."""
        if not self._client:
            return False
        if not self._client.is_connected():
            await self._client.connect()
        return await self._client.is_user_authorized()

    async def disconnect(self) -> None:
        """Safely disconnect Telethon client."""
        if self._client and self._client.is_connected():
            logger.info("Disconnecting Telethon client...")
            await self._client.disconnect()
            logger.info("Telethon client disconnected.")
