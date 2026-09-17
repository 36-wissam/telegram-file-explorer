"""Login and authentication dialog for Telegram MTProto."""

from PySide6.QtCore import Qt, Signal, QRegularExpression
from PySide6.QtGui import QFont, QRegularExpressionValidator
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from telethon.errors import SessionPasswordNeededError

from ..core.async_runner import async_runner
from ..core.config import settings
from ..core.logger import get_logger
from ..telegram.auth import AuthError, AuthState, TelegramAuthService
from ..telegram.client import validate_api_credentials
from ..telegram.exceptions import ConfigurationError

logger = get_logger("ui.login_dialog")


class LoginDialog(QDialog):
    """Modern stepped dialog for Telegram MTProto user authentication."""

    # Signal emitted when user successfully logs in
    authenticated = Signal(dict)

    def __init__(self, auth_service: TelegramAuthService, parent=None):
        super().__init__(parent)
        self.auth_service = auth_service
        self.setWindowTitle("Sign in to Telegram")
        self.setMinimumSize(480, 520)
        self.resize(500, 550)
        self.setModal(True)

        self._init_ui()
        self._determine_initial_step()

    def _init_ui(self):
        """Construct stacked dialog UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(18)

        # Header Title
        self.title_label = QLabel("Telegram Sign In")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_label)

        # Subtitle / Step description
        self.subtitle_label = QLabel("Connect your Telegram account securely.")
        self.subtitle_label.setAlignment(Qt.AlignCenter)
        self.subtitle_label.setStyleSheet("color: #949ba4; font-size: 13px;")
        layout.addWidget(self.subtitle_label)

        # Stacked Pages
        self.stack = QStackedWidget(self)
        layout.addWidget(self.stack)

        # Create pages
        self.page_api = self._create_api_page()
        self.page_phone = self._create_phone_page()
        self.page_code = self._create_code_page()
        self.page_2fa = self._create_2fa_page()

        self.stack.addWidget(self.page_api)    # Index 0
        self.stack.addWidget(self.page_phone)  # Index 1
        self.stack.addWidget(self.page_code)   # Index 2
        self.stack.addWidget(self.page_2fa)    # Index 3

        # Global Error / Status Banner
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("font-size: 12px; color: #ed4245; min-height: 24px;")
        layout.addWidget(self.status_label)

    def _determine_initial_step(self):
        """Pick initial page based on whether credentials exist."""
        cfg = getattr(self.auth_service.manager, "settings", settings)
        if not cfg.is_telegram_configured:
            self.set_step(0, "Configure Telegram API", "Enter your API credentials from my.telegram.org")
        else:
            self.set_step(1, "Enter Phone Number", "We will send a login code via Telegram or SMS")


    def set_step(self, index: int, title: str, subtitle: str):
        """Switch active page and update headers."""
        self.stack.setCurrentIndex(index)
        self.title_label.setText(title)
        self.subtitle_label.setText(subtitle)
        self.clear_status()

    def show_error(self, message: str):
        """Display error message."""
        self.status_label.setStyleSheet("font-size: 12px; color: #ed4245; min-height: 24px;")
        self.status_label.setText(message)

    def show_info(self, message: str):
        """Display info message."""
        self.status_label.setStyleSheet("font-size: 12px; color: #5865f2; min-height: 24px;")
        self.status_label.setText(message)

    def clear_status(self):
        """Clear error/status message."""
        self.status_label.setText("")

    # --- Page 0: API Credentials ---
    def _create_api_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(14)
        layout.setAlignment(Qt.AlignTop)

        info_box = QLabel(
            "To use your own Telegram account, obtain an <b>API ID</b> and <b>API Hash</b> "
            "from <a href='https://my.telegram.org' style='color: #5865f2;'>my.telegram.org</a>.<br>"
            "<small style='color: #949ba4;'>All credentials stay 100% local on this computer.</small>"
        )
        info_box.setOpenExternalLinks(True)
        info_box.setWordWrap(True)
        info_box.setStyleSheet("background-color: #2b2d31; padding: 12px; border-radius: 8px;")
        layout.addWidget(info_box)

        layout.addWidget(QLabel("Telegram API ID:"))
        self.api_id_input = QLineEdit()
        self.api_id_input.setPlaceholderText("e.g. 12345678")
        if settings.api_id:
            self.api_id_input.setText(str(settings.api_id))
        layout.addWidget(self.api_id_input)

        layout.addWidget(QLabel("Telegram API Hash:"))
        self.api_hash_input = QLineEdit()
        self.api_hash_input.setPlaceholderText("e.g. 0123456789abcdef0123456789abcdef")
        if settings.api_hash:
            self.api_hash_input.setText(settings.api_hash)
        layout.addWidget(self.api_hash_input)

        layout.addSpacing(10)
        self.btn_save_api = QPushButton("Save & Continue")
        self.btn_save_api.setObjectName("primaryButton")
        self.btn_save_api.clicked.connect(self._on_save_api)
        layout.addWidget(self.btn_save_api)

        layout.addStretch()
        return widget

    def _on_save_api(self):
        """Validate and save API credentials locally."""
        raw_id = self.api_id_input.text().strip()
        raw_hash = self.api_hash_input.text().strip()

        try:
            val_id, val_hash = validate_api_credentials(raw_id, raw_hash)
            settings.save_local_credentials(val_id, val_hash)
            self.auth_service.manager.initialize_client(val_id, val_hash)
            self.set_step(1, "Enter Phone Number", "We will send a login code via Telegram or SMS")
        except ConfigurationError as e:
            self.show_error(str(e))
        except Exception as e:
            self.show_error(f"Error initializing client: {e}")

    # --- Page 1: Phone Number ---
    def _create_phone_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(14)
        layout.setAlignment(Qt.AlignTop)

        layout.addWidget(QLabel("Phone Number (with country code):"))
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("+1234567890")
        self.phone_input.returnPressed.connect(self._on_send_code)
        layout.addWidget(self.phone_input)

        hint = QLabel("Include your international country code (e.g. +1 for US/CA, +44 for UK).")
        hint.setStyleSheet("color: #949ba4; font-size: 11px;")
        layout.addWidget(hint)

        layout.addSpacing(10)
        self.btn_send_code = QPushButton("Send Login Code")
        self.btn_send_code.setObjectName("primaryButton")
        self.btn_send_code.clicked.connect(self._on_send_code)
        layout.addWidget(self.btn_send_code)

        btn_edit_api = QPushButton("Edit API Credentials")
        btn_edit_api.clicked.connect(lambda: self.set_step(0, "Configure Telegram API", "Edit local API ID and Hash"))
        layout.addWidget(btn_edit_api)

        layout.addStretch()
        return widget

    def _on_send_code(self):
        """Trigger sending code request via Telethon."""
        phone = self.phone_input.text().strip()
        if not phone:
            self.show_error("Please enter a valid phone number.")
            return

        self.btn_send_code.setEnabled(False)
        self.show_info("Sending verification code...")

        def on_success(_hash):
            self.btn_send_code.setEnabled(True)
            self.set_step(2, "Enter Verification Code", f"Code sent to {phone}")

        def on_error(exc):
            self.btn_send_code.setEnabled(True)
            self.show_error(str(exc))

        async_runner.run_coroutine_async(
            self.auth_service.send_code(phone),
            callback=on_success,
            error_callback=on_error,
        )

    # --- Page 2: Verification Code ---
    def _create_code_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(14)
        layout.setAlignment(Qt.AlignTop)

        layout.addWidget(QLabel("Verification Code:"))
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("Enter OTP code")
        code_font = QFont()
        code_font.setPointSize(16)
        code_font.setLetterSpacing(QFont.AbsoluteSpacing, 4)
        self.code_input.setFont(code_font)
        self.code_input.setAlignment(Qt.AlignCenter)
        self.code_input.returnPressed.connect(self._on_submit_code)
        layout.addWidget(self.code_input)

        layout.addSpacing(10)
        self.btn_submit_code = QPushButton("Verify Code")
        self.btn_submit_code.setObjectName("primaryButton")
        self.btn_submit_code.clicked.connect(self._on_submit_code)
        layout.addWidget(self.btn_submit_code)

        btn_back_phone = QPushButton("Change Phone Number")
        btn_back_phone.clicked.connect(lambda: self.set_step(1, "Enter Phone Number", "Re-enter phone number"))
        layout.addWidget(btn_back_phone)

        layout.addStretch()
        return widget

    def _on_submit_code(self):
        """Submit OTP code."""
        code = self.code_input.text().strip()
        if not code:
            self.show_error("Please enter the verification code.")
            return

        self.btn_submit_code.setEnabled(False)
        self.show_info("Verifying code...")

        def on_success(user_dict):
            self.btn_submit_code.setEnabled(True)
            self.authenticated.emit(user_dict)
            self.accept()

        def on_error(exc):
            self.btn_submit_code.setEnabled(True)
            if (
                isinstance(exc, SessionPasswordNeededError)
                or "SessionPasswordNeededError" in type(exc).__name__
                or "Two-steps verification is enabled" in str(exc)
                or "password is required" in str(exc).lower()
            ):
                self.set_step(3, "Two-Step Verification", "Enter your Telegram 2FA cloud password")
            else:
                self.show_error(str(exc))

        async_runner.run_coroutine_async(
            self.auth_service.sign_in_with_code(code),
            callback=on_success,
            error_callback=on_error,
        )

    # --- Page 3: 2FA Password ---
    def _create_2fa_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(14)
        layout.setAlignment(Qt.AlignTop)

        info_box = QLabel(
            "Your Telegram account is protected with a 2FA Cloud Password.<br>"
            "<small style='color: #949ba4;'>Your password is verified via MTProto SRP and never saved anywhere.</small>"
        )
        info_box.setWordWrap(True)
        info_box.setStyleSheet("background-color: #2b2d31; padding: 12px; border-radius: 8px;")
        layout.addWidget(info_box)

        layout.addWidget(QLabel("Password:"))
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Enter your 2FA password")
        self.password_input.returnPressed.connect(self._on_submit_password)
        layout.addWidget(self.password_input)

        layout.addSpacing(10)
        self.btn_submit_2fa = QPushButton("Unlock Account")
        self.btn_submit_2fa.setObjectName("primaryButton")
        self.btn_submit_2fa.clicked.connect(self._on_submit_password)
        layout.addWidget(self.btn_submit_2fa)

        btn_back = QPushButton("Back")
        btn_back.clicked.connect(lambda: self.set_step(2, "Enter Verification Code", "Back to code step"))
        layout.addWidget(btn_back)

        layout.addStretch()
        return widget

    def _on_submit_password(self):
        """Submit 2FA password."""
        password = self.password_input.text()
        if not password:
            self.show_error("Please enter your password.")
            return

        self.btn_submit_2fa.setEnabled(False)
        self.show_info("Verifying 2FA password...")

        def on_success(user_dict):
            # Clear input immediately
            self.password_input.clear()
            self.btn_submit_2fa.setEnabled(True)
            self.authenticated.emit(user_dict)
            self.accept()

        def on_error(exc):
            self.password_input.clear()
            self.btn_submit_2fa.setEnabled(True)
            self.show_error(str(exc))

        async_runner.run_coroutine_async(
            self.auth_service.sign_in_with_password(password),
            callback=on_success,
            error_callback=on_error,
        )
