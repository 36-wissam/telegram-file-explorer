"""Inline authentication widget for embedding directly into the main window."""

from typing import Dict, Any, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from telethon.errors import SessionPasswordNeededError, PasswordHashInvalidError

from ..core.async_runner import async_runner
from ..core.config import settings
from ..telegram.client import validate_api_credentials
from ..telegram.exceptions import ConfigurationError
from ..core.logger import get_logger
from ..telegram.auth import AuthState, TelegramAuthService

logger = get_logger("ui.inline_auth")


class InlineAuthWidget(QWidget):
    """Modern, multi-step authentication widget embedded directly on the welcome screen."""

    authenticated = Signal(dict)

    def __init__(self, auth_service: TelegramAuthService, parent=None):
        super().__init__(parent)
        self.auth_service = auth_service
        self._current_phone: str = ""
        self._init_ui()
        self._set_initial_state()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(16)

        # Step Breadcrumb Indicator
        self.breadcrumb_layout = QHBoxLayout()
        self.breadcrumb_layout.setSpacing(8)
        self.breadcrumb_layout.setAlignment(Qt.AlignCenter)

        self.step_labels = []
        steps = [
            ("🔑 1. API", "Configure Telegram MTProto API"),
            ("📱 2. Phone", "Enter Telegram phone number"),
            ("✉️ 3. Code", "Enter verification code"),
            ("🔒 4. 2FA", "Two-step verification"),
        ]

        for idx, (label_text, tooltip) in enumerate(steps):
            lbl = QLabel(label_text)
            lbl.setToolTip(tooltip)
            lbl.setAlignment(Qt.AlignCenter)
            self.step_labels.append(lbl)
            self.breadcrumb_layout.addWidget(lbl)
            if idx < len(steps) - 1:
                arrow = QLabel("➔")
                arrow.setStyleSheet("color: #4e5058; font-size: 11px;")
                self.breadcrumb_layout.addWidget(arrow)

        main_layout.addLayout(self.breadcrumb_layout)

        # Step Header (Title + Subtitle)
        self.step_title = QLabel("Sign in to Telegram")
        self.step_title.setAlignment(Qt.AlignCenter)
        self.step_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff;")
        main_layout.addWidget(self.step_title)

        self.step_subtitle = QLabel("")
        self.step_subtitle.setAlignment(Qt.AlignCenter)
        self.step_subtitle.setStyleSheet("font-size: 12px; color: #949ba4;")
        self.step_subtitle.setWordWrap(True)
        main_layout.addWidget(self.step_subtitle)

        # Message / Error Banner
        self.banner = QLabel()
        self.banner.setAlignment(Qt.AlignCenter)
        self.banner.setWordWrap(True)
        self.banner.setVisible(False)
        main_layout.addWidget(self.banner)

        # Stacked Pages
        self.stack = QStackedWidget()
        self.page_api = self._create_api_page()
        self.page_phone = self._create_phone_page()
        self.page_code = self._create_code_page()
        self.page_2fa = self._create_2fa_page()

        self.stack.addWidget(self.page_api)    # 0
        self.stack.addWidget(self.page_phone)  # 1
        self.stack.addWidget(self.page_code)   # 2
        self.stack.addWidget(self.page_2fa)    # 3

        main_layout.addWidget(self.stack)

    # --- Page 0: API Configuration ---
    def _create_api_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)
        layout.setContentsMargins(0, 0, 0, 0)

        info = QLabel(
            "Get your API credentials from <a href='https://my.telegram.org' style='color: #00aff4;'>my.telegram.org</a>.<br>"
            "<small style='color: #949ba4;'>Credentials are stored strictly on your local PC in <code>data/.env</code>.</small>"
        )
        info.setOpenExternalLinks(True)
        info.setWordWrap(True)
        info.setStyleSheet("background-color: #2b2d31; padding: 10px; border-radius: 6px; font-size: 12px;")
        layout.addWidget(info)

        layout.addWidget(QLabel("🔑 API ID:"))
        self.api_id_input = QLineEdit()
        self.api_id_input.setPlaceholderText("e.g. 12345678")
        if settings.api_id:
            self.api_id_input.setText(str(settings.api_id))
        layout.addWidget(self.api_id_input)

        layout.addWidget(QLabel("🗝️ API Hash:"))
        self.api_hash_input = QLineEdit()
        self.api_hash_input.setPlaceholderText("e.g. 0123456789abcdef0123456789abcdef")
        if settings.api_hash:
            self.api_hash_input.setText(settings.api_hash)
        layout.addWidget(self.api_hash_input)

        layout.addSpacing(6)
        self.btn_save_api = QPushButton("💾 Save & Continue ➔")
        self.btn_save_api.setObjectName("primaryButton")
        self.btn_save_api.clicked.connect(self._on_save_api)
        layout.addWidget(self.btn_save_api)

        return widget

    def _on_save_api(self):
        """Validate and save API credentials locally."""
        raw_id = self.api_id_input.text().strip()
        raw_hash = self.api_hash_input.text().strip()

        try:
            val_id, val_hash = validate_api_credentials(raw_id, raw_hash)
            settings.save_local_credentials(val_id, val_hash)
            self.auth_service.manager.initialize_client(val_id, val_hash)
            self.clear_banner()
            self.set_step(1, "📱 Enter Phone Number", "We will send a login code to your Telegram app or SMS")
        except ConfigurationError as e:
            self.show_error(f"❌ {e}")
        except Exception as e:
            self.show_error(f"❌ Error initializing client: {e}")

    # --- Page 1: Phone Number ---
    def _create_phone_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(QLabel("📱 Phone Number (with international country code):"))
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("+1234567890")
        self.phone_input.returnPressed.connect(self._on_send_code)
        layout.addWidget(self.phone_input)

        hint = QLabel("💡 Include country code (e.g. +1 for US/CA, +44 for UK, +964 for Iraq).")
        hint.setStyleSheet("color: #949ba4; font-size: 11px;")
        layout.addWidget(hint)

        layout.addSpacing(6)
        self.btn_send_code = QPushButton("📨 Send Login Code ➔")
        self.btn_send_code.setObjectName("primaryButton")
        self.btn_send_code.clicked.connect(self._on_send_code)
        layout.addWidget(self.btn_send_code)

        self.btn_edit_api = QPushButton("⚙️ Edit API Credentials")
        self.btn_edit_api.clicked.connect(lambda: self.set_step(0, "🔑 Configure Telegram API", "Edit local API ID and Hash"))
        layout.addWidget(self.btn_edit_api)

        return widget

    def _on_send_code(self):
        """Send verification code request."""
        phone = self.phone_input.text().strip()
        if not phone:
            self.show_error("❌ Please enter a valid phone number.")
            return

        self.btn_send_code.setEnabled(False)
        self.show_info("⏳ Sending verification code from Telegram...")

        def on_success(_hash):
            self.btn_send_code.setEnabled(True)
            self._current_phone = phone
            self.clear_banner()
            self.set_step(2, "✉️ Enter Verification Code", f"Verification code sent to {phone}")
            self.code_input.setFocus()

        def on_error(exc):
            self.btn_send_code.setEnabled(True)
            self.show_error(f"❌ {exc}")

        async_runner.run_coroutine_async(
            self.auth_service.send_code(phone),
            callback=on_success,
            error_callback=on_error,
        )

    # --- Page 2: Verification Code ---
    def _create_code_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(QLabel("✉️ Verification Code:"))
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("OTP code")
        code_font = QFont()
        code_font.setPointSize(16)
        code_font.setLetterSpacing(QFont.AbsoluteSpacing, 4)
        self.code_input.setFont(code_font)
        self.code_input.setAlignment(Qt.AlignCenter)
        self.code_input.returnPressed.connect(self._on_submit_code)
        layout.addWidget(self.code_input)

        layout.addSpacing(6)
        self.btn_submit_code = QPushButton("✅ Verify Code & Sign In")
        self.btn_submit_code.setObjectName("primaryButton")
        self.btn_submit_code.clicked.connect(self._on_submit_code)
        layout.addWidget(self.btn_submit_code)

        actions_layout = QHBoxLayout()
        self.btn_back_phone = QPushButton("◀ Change Phone")
        self.btn_back_phone.clicked.connect(lambda: self.set_step(1, "📱 Enter Phone Number", "Re-enter phone number"))
        actions_layout.addWidget(self.btn_back_phone)

        self.btn_resend_code = QPushButton("🔄 Resend Code")
        self.btn_resend_code.clicked.connect(self._on_send_code)
        actions_layout.addWidget(self.btn_resend_code)
        layout.addLayout(actions_layout)

        return widget

    def _on_submit_code(self):
        """Submit OTP code."""
        code = self.code_input.text().strip()
        if not code:
            self.show_error("❌ Please enter the verification code.")
            return

        self.btn_submit_code.setEnabled(False)
        self.show_info("⏳ Verifying code...")

        def on_success(user_dict):
            self.btn_submit_code.setEnabled(True)
            self.clear_banner()
            self.authenticated.emit(user_dict)

        def on_error(exc):
            self.btn_submit_code.setEnabled(True)
            # Check if 2FA password is required
            if (
                isinstance(exc, SessionPasswordNeededError)
                or "SessionPasswordNeededError" in type(exc).__name__
                or "Two-steps verification is enabled" in str(exc)
                or "password is required" in str(exc).lower()
            ):
                self.clear_banner()
                self.set_step(3, "🔒 Two-Step Verification", "Enter your Telegram 2FA cloud password")
                self.password_input.setFocus()
            else:
                self.show_error(f"❌ {exc}")

        async_runner.run_coroutine_async(
            self.auth_service.sign_in_with_code(code),
            callback=on_success,
            error_callback=on_error,
        )

    # --- Page 3: 2FA Password ---
    def _create_2fa_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)
        layout.setContentsMargins(0, 0, 0, 0)

        info_box = QLabel(
            "🛡️ <b>Two-Step Verification Enabled</b><br>"
            "<small style='color: #949ba4;'>Your cloud password is verified locally via MTProto SRP and never saved to disk.</small>"
        )
        info_box.setWordWrap(True)
        info_box.setStyleSheet("background-color: #2b2d31; padding: 10px; border-radius: 6px; font-size: 12px;")
        layout.addWidget(info_box)

        layout.addWidget(QLabel("🔒 Cloud Password:"))
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Enter your 2FA password")
        self.password_input.returnPressed.connect(self._on_submit_password)
        layout.addWidget(self.password_input)

        layout.addSpacing(6)
        self.btn_submit_2fa = QPushButton("🔓 Unlock Account & Sign In")
        self.btn_submit_2fa.setObjectName("primaryButton")
        self.btn_submit_2fa.clicked.connect(self._on_submit_password)
        layout.addWidget(self.btn_submit_2fa)

        self.btn_back_to_code = QPushButton("◀ Back to Code")
        self.btn_back_to_code.clicked.connect(lambda: self.set_step(2, "✉️ Enter Verification Code", "Back to code step"))
        layout.addWidget(self.btn_back_to_code)

        return widget

    def _on_submit_password(self):
        """Submit 2FA password."""
        password = self.password_input.text()
        if not password:
            self.show_error("❌ Please enter your 2FA password.")
            return

        self.btn_submit_2fa.setEnabled(False)
        self.show_info("⏳ Verifying 2FA password...")

        def on_success(user_dict):
            self.password_input.clear()
            self.btn_submit_2fa.setEnabled(True)
            self.clear_banner()
            self.authenticated.emit(user_dict)

        def on_error(exc):
            self.password_input.clear()
            self.btn_submit_2fa.setEnabled(True)
            if (
                isinstance(exc, PasswordHashInvalidError)
                or "PasswordHashInvalidError" in type(exc).__name__
                or "password is invalid" in str(exc).lower()
            ):
                self.show_error("❌ Invalid 2FA password. Please check your password and try again.")
            else:
                self.show_error(f"❌ 2FA verification error: {exc}")

        async_runner.run_coroutine_async(
            self.auth_service.sign_in_with_password(password),
            callback=on_success,
            error_callback=on_error,
        )

    # --- State Management & UI Helpers ---
    def set_step(self, step_idx: int, title: str, subtitle: str):
        """Switch current step and update breadcrumbs and titles."""
        self.stack.setCurrentIndex(step_idx)
        self.step_title.setText(title)
        self.step_subtitle.setText(subtitle)

        # Update breadcrumbs
        for idx, lbl in enumerate(self.step_labels):
            if idx == step_idx:
                lbl.setStyleSheet(
                    "background-color: #5865f2; color: #ffffff; border-radius: 10px; "
                    "padding: 4px 10px; font-weight: bold; font-size: 11px;"
                )
            elif idx < step_idx:
                lbl.setStyleSheet(
                    "background-color: #248046; color: #ffffff; border-radius: 10px; "
                    "padding: 4px 10px; font-size: 11px;"
                )
            else:
                lbl.setStyleSheet(
                    "background-color: #2b2d31; color: #949ba4; border-radius: 10px; "
                    "padding: 4px 10px; font-size: 11px;"
                )

    def show_error(self, message: str):
        """Display an error message banner with icon."""
        self.banner.setText(message)
        self.banner.setStyleSheet(
            "background-color: #421d24; color: #f23f43; border: 1px solid #da373c; "
            "border-radius: 6px; padding: 10px; font-size: 12px; font-weight: 500;"
        )
        self.banner.setVisible(True)

    def show_info(self, message: str):
        """Display an info or progress banner with icon."""
        self.banner.setText(message)
        self.banner.setStyleSheet(
            "background-color: #1e293b; color: #38bdf8; border: 1px solid #0284c7; "
            "border-radius: 6px; padding: 10px; font-size: 12px; font-weight: 500;"
        )
        self.banner.setVisible(True)

    def clear_banner(self):
        """Hide the notification banner."""
        self.banner.setText("")
        self.banner.setVisible(False)

    def _set_initial_state(self):
        """Determine initial step based on configuration state."""
        if settings.is_telegram_configured:
            self.set_step(1, "📱 Enter Phone Number", "Sign in with your Telegram account")
        else:
            self.set_step(0, "🔑 Configure Telegram API", "Configure your API ID and Hash locally")

    def reset_to_initial(self):
        """Reset form inputs and return to starting step."""
        self.clear_banner()
        self.code_input.clear()
        self.password_input.clear()
        self._set_initial_state()
