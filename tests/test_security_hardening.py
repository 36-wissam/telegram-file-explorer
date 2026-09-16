"""Tests for Stage 14: Security Review, Local Credential Hardening & Privacy."""

import logging
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import pytest

from app.core.config import Settings, harden_file_permissions
from app.core.logger import SensitiveDataFormatter
from app.telegram.auth import TelegramAuthService


def test_sensitive_data_formatter_redactions():
    """Verify SensitiveDataFormatter redacts phone numbers, passwords, hashes, and tokens."""
    formatter = SensitiveDataFormatter("%(message)s")

    # Test Phone Number Masking
    record_phone = logging.LogRecord("test", logging.INFO, "", 0, "User phone: +12025550199 registered", (), None)
    output_phone = formatter.format(record_phone)
    assert "+12025550199" not in output_phone
    assert "****" in output_phone

    # Test 32-char Hex Hash Masking
    raw_hash = "a1b2c3d4e5f60718293a4b5c6d7e8f90"
    record_hash = logging.LogRecord("test", logging.INFO, "", 0, f"Validating API hash: {raw_hash}", (), None)
    output_hash = formatter.format(record_hash)
    assert raw_hash not in output_hash
    assert "************************" in output_hash

    # Test Password / Token Keyword Redaction
    record_pass = logging.LogRecord(
        "test", logging.INFO, "", 0, "Login attempt with password=UltraSecret999! and code=55443", (), None
    )
    output_pass = formatter.format(record_pass)
    assert "UltraSecret999!" not in output_pass
    assert "55443" not in output_pass
    assert "password=[REDACTED]" in output_pass
    assert "code=[REDACTED]" in output_pass


def test_gitignore_contains_critical_secrets():
    """Audit .gitignore to guarantee all session files, databases, and environments are ignored."""
    gitignore_path = Path(__file__).resolve().parent.parent / ".gitignore"
    assert gitignore_path.exists(), ".gitignore file must exist"

    content = gitignore_path.read_text(encoding="utf-8")
    critical_rules = [
        ".env",
        "*.session",
        "*.session-journal",
        "*.session-wal",
        "*.db",
        "data/",
    ]
    for rule in critical_rules:
        assert rule in content, f"Rule '{rule}' must be present in .gitignore to protect user data"


def test_wipe_local_credentials_and_sessions(tmp_path: Path):
    """Verify wipe_local_credentials_and_sessions erases all sensitive session files and databases."""
    custom_data = tmp_path / "data"
    custom_sessions = custom_data / "sessions"
    custom_sessions.mkdir(parents=True, exist_ok=True)

    settings = Settings(base_dir=tmp_path, data_dir=custom_data, sessions_dir=custom_sessions)

    # Save dummy credentials
    settings.save_local_credentials(12345, "0123456789abcdef0123456789abcdef")
    assert settings.local_config_path.exists()
    assert settings.is_telegram_configured

    # Create dummy session file and database file
    dummy_session = custom_sessions / f"{settings.session_name}.session"
    dummy_session.write_text("dummy-session-bytes", encoding="utf-8")
    dummy_db = custom_data / "explorer.db"
    dummy_db.write_text("dummy-db-bytes", encoding="utf-8")

    assert dummy_session.exists()
    assert dummy_db.exists()

    # Perform complete wipe
    summary = settings.wipe_local_credentials_and_sessions()
    assert summary["config"] is True
    assert summary["sessions"] >= 1
    assert summary["databases"] >= 1

    # Verify files no longer exist
    assert not settings.local_config_path.exists()
    assert not dummy_session.exists()
    assert not dummy_db.exists()
    assert not settings.is_telegram_configured
    assert settings.api_id is None
    assert settings.api_hash is None


def test_harden_file_permissions(tmp_path: Path):
    """Verify harden_file_permissions executes cleanly without exceptions."""
    test_file = tmp_path / "secret_key.pem"
    test_file.write_text("secret", encoding="utf-8")
    harden_file_permissions(test_file)
    assert test_file.exists()


@pytest.mark.anyio
async def test_in_memory_2fa_password_isolation(tmp_path: Path):
    """Verify 2FA cloud password is not written to disk or stored on auth service."""
    mock_mgr = MagicMock()
    mock_client = MagicMock()
    mock_client.is_connected.return_value = True

    mock_user = MagicMock()
    mock_user.id = 998877
    mock_user.first_name = "Alice"
    mock_user.last_name = "Smith"
    mock_user.username = "alicesmith"
    mock_user.phone = "+12025550199"
    mock_client.sign_in = AsyncMock(return_value=mock_user)
    mock_mgr.client = mock_client

    auth = TelegramAuthService(mock_mgr)
    secret_pass = "MySuperSecretCloudPassword2026!"

    res = await auth.sign_in_with_password(secret_pass)
    assert res["id"] == 998877
    mock_client.sign_in.assert_called_once_with(password=secret_pass)

    # Verify password is not saved anywhere on auth service object
    assert not hasattr(auth, "password")
    assert secret_pass not in str(auth.__dict__)
