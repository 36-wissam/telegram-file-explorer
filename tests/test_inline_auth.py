"""Unit tests for InlineAuthWidget embedded authentication."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from PySide6.QtWidgets import QApplication
from telethon.errors import SessionPasswordNeededError

from app.telegram.auth import AuthState, TelegramAuthService
from app.ui.inline_auth import InlineAuthWidget


@pytest.fixture
def app():
    app_instance = QApplication.instance()
    if not app_instance:
        app_instance = QApplication([])
    return app_instance


def test_inline_auth_widget_initial_steps(app):
    """Verify initial step determination and breadcrumbs."""
    auth_service = MagicMock(spec=TelegramAuthService)
    auth_service.manager = MagicMock()
    auth_service.manager.is_configured = True

    widget = InlineAuthWidget(auth_service)
    assert widget.stack.count() == 4
    assert len(widget.step_labels) == 4

    # Test set_step
    widget.set_step(0, "🔑 API", "Config")
    assert widget.stack.currentIndex() == 0
    assert "🔑 API" in widget.step_title.text()

    widget.set_step(1, "📱 Phone", "Phone")
    assert widget.stack.currentIndex() == 1

    widget.set_step(2, "✉️ Code", "Code")
    assert widget.stack.currentIndex() == 2

    widget.set_step(3, "🔒 2FA", "2FA")
    assert widget.stack.currentIndex() == 3


def test_inline_auth_2fa_step_transition_on_session_password_needed(app):
    """Verify entering code when 2FA is enabled safely transitions to step 3."""
    auth_service = MagicMock(spec=TelegramAuthService)
    auth_service.manager = MagicMock()
    auth_service.phone_number = "+1234567890"
    auth_service.phone_code_hash = "hash123"

    widget = InlineAuthWidget(auth_service)
    widget.code_input.setText("12345")

    # Mock sign_in_with_code raising SessionPasswordNeededError
    async def fake_sign_in(code):
        raise SessionPasswordNeededError(request=None)

    auth_service.sign_in_with_code = fake_sign_in

    with patch("app.core.async_runner.async_runner.run_coroutine_async") as mock_run:
        def call_error(coro, callback=None, error_callback=None):
            error_callback(SessionPasswordNeededError(request=None))
        mock_run.side_effect = call_error

        widget._on_submit_code()

        # Should transition to Step 3 (2FA) without crash
        assert widget.stack.currentIndex() == 3
        assert "Two-Step Verification" in widget.step_title.text()


def test_inline_auth_successful_2fa_emits_authenticated(app):
    """Verify submitting 2FA password emits authenticated signal."""
    auth_service = MagicMock(spec=TelegramAuthService)
    widget = InlineAuthWidget(auth_service)
    widget.password_input.setText("secret2fa")

    received_user = []
    widget.authenticated.connect(lambda u: received_user.append(u))

    with patch("app.core.async_runner.async_runner.run_coroutine_async") as mock_run:
        def call_success(coro, callback=None, error_callback=None):
            callback({"id": 999, "first_name": "Bob"})
        mock_run.side_effect = call_success

        widget._on_submit_password()

        assert len(received_user) == 1
        assert received_user[0]["first_name"] == "Bob"
        assert widget.password_input.text() == ""
