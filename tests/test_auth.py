"""Unit tests for Stage 3: Telegram Authentication."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from app.core.config import Settings
from app.telegram.auth import AuthState, AuthError, TelegramAuthService
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PasswordHashInvalidError


@pytest.fixture
def mock_telethon_client():
    """Create a mock Telethon client."""
    client = MagicMock()
    client.is_connected = MagicMock(return_value=True)
    client.connect = AsyncMock()
    client.disconnect = AsyncMock()
    client.is_user_authorized = AsyncMock(return_value=False)
    client.log_out = AsyncMock()
    return client


@pytest.fixture
def auth_service(tmp_path, mock_telethon_client):
    """Fixture providing TelegramAuthService with mocked client manager."""
    settings = Settings()
    settings.data_dir = tmp_path
    settings.sessions_dir = tmp_path / "sessions"
    settings.api_id = 12345678
    settings.api_hash = "0123456789abcdef0123456789abcdef"
    settings.ensure_directories()

    manager = MagicMock()
    manager.settings = settings
    manager.is_initialized = True
    manager.client = mock_telethon_client
    manager.session_file_path = settings.sessions_dir / "test.session"

    service = TelegramAuthService(manager)
    return service


def test_auth_state_not_configured():
    """Verify NOT_CONFIGURED state when API credentials missing."""
    settings = Settings()
    settings.api_id = None
    settings.api_hash = None

    manager = MagicMock()
    manager.settings = settings
    manager.is_initialized = False

    service = TelegramAuthService(manager)
    state = asyncio.run(service.check_auth_state())
    assert state == AuthState.NOT_CONFIGURED


def test_auth_state_authorized(auth_service, mock_telethon_client):
    """Verify AUTHORIZED state when session is already authorized."""
    mock_telethon_client.is_user_authorized.return_value = True

    mock_user = MagicMock()
    mock_user.id = 99887766
    mock_user.first_name = "Alice"
    mock_user.last_name = "Smith"
    mock_user.username = "alicesmith"
    mock_user.phone = "+1234567890"
    mock_telethon_client.get_me = AsyncMock(return_value=mock_user)

    state = asyncio.run(auth_service.check_auth_state())
    assert state == AuthState.AUTHORIZED
    assert auth_service.current_user is not None
    assert auth_service.current_user["id"] == 99887766
    assert auth_service.current_user["username"] == "alicesmith"


def test_send_code_success(auth_service, mock_telethon_client):
    """Verify sending OTP code transitions to WAITING_FOR_CODE."""
    mock_sent_code = MagicMock()
    mock_sent_code.phone_code_hash = "fake_hash_12345"
    mock_telethon_client.send_code_request = AsyncMock(return_value=mock_sent_code)

    code_hash = asyncio.run(auth_service.send_code("+1234567890"))
    assert code_hash == "fake_hash_12345"
    assert auth_service.state == AuthState.WAITING_FOR_CODE
    assert auth_service.phone_number == "+1234567890"


def test_sign_in_with_code_success(auth_service, mock_telethon_client):
    """Verify successful sign-in with code transitions to AUTHORIZED."""
    auth_service.phone_number = "+1234567890"
    auth_service.phone_code_hash = "fake_hash_12345"

    mock_user = MagicMock()
    mock_user.id = 112233
    mock_user.first_name = "Bob"
    mock_user.last_name = ""
    mock_user.username = "bob123"
    mock_user.phone = "+1234567890"
    mock_telethon_client.sign_in = AsyncMock(return_value=mock_user)

    user = asyncio.run(auth_service.sign_in_with_code("12345"))
    assert auth_service.state == AuthState.AUTHORIZED
    assert user["username"] == "bob123"


def test_sign_in_with_code_triggers_2fa(auth_service, mock_telethon_client):
    """Verify SessionPasswordNeededError transitions state to WAITING_FOR_PASSWORD."""
    auth_service.phone_number = "+1234567890"
    auth_service.phone_code_hash = "fake_hash_12345"
    mock_telethon_client.sign_in = AsyncMock(side_effect=SessionPasswordNeededError(request=None))

    with pytest.raises(SessionPasswordNeededError):
        asyncio.run(auth_service.sign_in_with_code("12345"))

    assert auth_service.state == AuthState.WAITING_FOR_PASSWORD


def test_sign_in_with_password_success(auth_service, mock_telethon_client):
    """Verify 2FA password authentication succeeds and transitions to AUTHORIZED."""
    auth_service.state = AuthState.WAITING_FOR_PASSWORD
    mock_user = MagicMock()
    mock_user.id = 445566
    mock_user.first_name = "Charlie"
    mock_user.last_name = ""
    mock_user.username = "charlie"
    mock_user.phone = "+1234567890"
    mock_telethon_client.sign_in = AsyncMock(return_value=mock_user)

    user = asyncio.run(auth_service.sign_in_with_password("my_secret_2fa"))
    assert auth_service.state == AuthState.AUTHORIZED
    assert user["id"] == 445566


def test_logout(auth_service, mock_telethon_client):
    """Verify logout terminates session and deletes local session file."""
    session_file = auth_service.manager.session_file_path
    session_file.write_text("dummy session data")
    assert session_file.exists()

    auth_service.state = AuthState.AUTHORIZED
    auth_service.current_user = {"id": 123}

    res = asyncio.run(auth_service.log_out())
    assert res is True
    assert auth_service.state == AuthState.UNAUTHORIZED
    assert auth_service.current_user is None
    assert not session_file.exists()


def test_login_dialog_ui_initialization(qapp, auth_service):
    """Verify LoginDialog initializes properly in Qt."""
    from app.ui.login_dialog import LoginDialog

    dialog = LoginDialog(auth_service)
    assert dialog is not None
    assert dialog.stack.count() == 4
    assert dialog.stack.currentIndex() == 1
    dialog.close()
