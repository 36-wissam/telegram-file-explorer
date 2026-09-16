"""Unit tests for Stage 2: Telegram API Configuration."""

import pytest
from pathlib import Path
from app.core.config import Settings
from app.telegram import (
    TelegramClientManager,
    validate_api_credentials,
    MissingCredentialsError,
    InvalidApiIdError,
    InvalidApiHashError,
)

VALID_API_ID = 12345678
VALID_API_HASH = "0123456789abcdef0123456789abcdef"


def test_missing_credentials_validation():
    """Verify MissingCredentialsError is raised when credentials are missing."""
    with pytest.raises(MissingCredentialsError) as exc_info:
        validate_api_credentials(None, None)
    assert "https://my.telegram.org" in str(exc_info.value)

    with pytest.raises(MissingCredentialsError):
        validate_api_credentials(VALID_API_ID, None)

    with pytest.raises(MissingCredentialsError):
        validate_api_credentials(None, VALID_API_HASH)


def test_invalid_api_id_validation():
    """Verify InvalidApiIdError is raised for non-positive or malformed IDs."""
    with pytest.raises(InvalidApiIdError):
        validate_api_credentials(-1, VALID_API_HASH)

    with pytest.raises(InvalidApiIdError):
        validate_api_credentials(0, VALID_API_HASH)

    with pytest.raises(InvalidApiIdError):
        validate_api_credentials("not_a_number", VALID_API_HASH)


def test_invalid_api_hash_validation():
    """Verify InvalidApiHashError is raised for non-32-hex strings."""
    # Too short
    with pytest.raises(InvalidApiHashError):
        validate_api_credentials(VALID_API_ID, "abc123")

    # Non-hex characters
    with pytest.raises(InvalidApiHashError):
        validate_api_credentials(VALID_API_ID, "0123456789abcdef0123456789abcdeg")

    # Empty string
    with pytest.raises(InvalidApiHashError):
        validate_api_credentials(VALID_API_ID, "   ")


def test_valid_credentials_validation():
    """Verify valid credentials pass validation."""
    api_id, api_hash = validate_api_credentials(VALID_API_ID, VALID_API_HASH)
    assert api_id == VALID_API_ID
    assert api_hash == VALID_API_HASH


def test_client_initialization_with_credentials(tmp_path):
    """Verify TelegramClient initializes with secure local session storage."""
    settings = Settings()
    settings.data_dir = tmp_path
    settings.sessions_dir = tmp_path / "sessions"
    settings.session_name = "test_user_session"
    settings.ensure_directories()

    manager = TelegramClientManager(settings)
    client = manager.initialize_client(api_id=VALID_API_ID, api_hash=VALID_API_HASH)

    assert client is not None
    assert manager.is_initialized is True
    assert manager.session_file_path == tmp_path / "sessions" / "test_user_session.session"
    assert client.api_id == VALID_API_ID
    assert client.api_hash == VALID_API_HASH


def test_client_initialization_from_settings(tmp_path):
    """Verify TelegramClient initializes directly from configured Settings."""
    settings = Settings()
    settings.data_dir = tmp_path
    settings.sessions_dir = tmp_path / "sessions"
    settings.api_id = VALID_API_ID
    settings.api_hash = VALID_API_HASH
    settings.ensure_directories()

    manager = TelegramClientManager(settings)
    client = manager.initialize_client()

    assert client is not None
    assert manager.is_initialized is True
