"""Main application window for Telegram File Explorer."""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from ..core.async_runner import async_runner
from ..core.config import settings
from ..core.logger import get_logger
from ..telegram.auth import AuthState, TelegramAuthService
from ..telegram.client import TelegramClientManager
from .login_dialog import LoginDialog

logger = get_logger("ui.main_window")


class MainWindow(QMainWindow):
    """Main desktop application window."""

    def __init__(self, client_manager: TelegramClientManager = None, auth_service: TelegramAuthService = None):
        super().__init__()
        self.setWindowTitle(f"{settings.app_name} v{settings.app_version}")
        self.setMinimumSize(850, 580)
        self.resize(1080, 720)

        # Initialize core services
        self.client_manager = client_manager or TelegramClientManager(settings)
        self.auth_service = auth_service or TelegramAuthService(self.client_manager)

        self._init_menu_bar()
        self._init_ui()
        self._init_status_bar()

        # Trigger auto-reconnect / auth check after Qt event loop starts
        QTimer.singleShot(100, self._check_initial_auth_state)

        logger.info("MainWindow initialized successfully.")

    def _init_menu_bar(self):
        """Build top menu bar."""
        menu_bar = self.menuBar()

        # File Menu
        file_menu = menu_bar.addMenu("&File")
        exit_action = QAction("&Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Account Menu
        self.account_menu = menu_bar.addMenu("&Account")
        self.action_login = QAction("Sign &In...", self)
        self.action_login.triggered.connect(self.open_login_dialog)
        self.account_menu.addAction(self.action_login)

        self.action_logout = QAction("Sign &Out", self)
        self.action_logout.triggered.connect(self._on_logout)
        self.action_logout.setEnabled(False)
        self.account_menu.addAction(self.action_logout)

        # Help Menu
        help_menu = menu_bar.addMenu("&Help")
        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _init_ui(self):
        """Construct central widget layout."""
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(32, 32, 32, 32)
        main_layout.setSpacing(20)

        # Welcome Card Container
        self.card = QFrame(self)
        self.card.setStyleSheet(
            """
            QFrame {
                background-color: #1e1f22;
                border: 1px solid #2b2d31;
                border-radius: 12px;
                padding: 24px;
            }
            """
        )
        card_layout = QVBoxLayout(self.card)
        card_layout.setSpacing(14)
        card_layout.setAlignment(Qt.AlignCenter)

        # App Icon / Title
        title_label = QLabel(f"📂 {settings.app_name}")
        title_font = QFont()
        title_font.setPointSize(22)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color: #ffffff;")
        card_layout.addWidget(title_label)

        # Subtitle / Tagline
        subtitle_label = QLabel(
            "Browse, index, search, preview, and download files from your Telegram account."
        )
        subtitle_label.setAlignment(Qt.AlignCenter)
        subtitle_label.setStyleSheet("color: #949ba4; font-size: 14px;")
        card_layout.addWidget(subtitle_label)

        # Status badge container
        self.status_box = QFrame(self)
        self.status_box.setStyleSheet(
            """
            QFrame {
                background-color: #2b2d31;
                border-radius: 8px;
                padding: 16px;
                min-width: 460px;
                max-width: 540px;
            }
            """
        )
        self.status_box_layout = QVBoxLayout(self.status_box)
        self.status_box_layout.setSpacing(8)

        self.account_status_label = QLabel("<b>Account Status:</b> Checking session...")
        self.account_status_label.setStyleSheet("font-size: 13px;")
        self.status_box_layout.addWidget(self.account_status_label)

        self.details_label = QLabel("")
        self.details_label.setStyleSheet("font-size: 12px; color: #dbdee1;")
        self.details_label.setWordWrap(True)
        self.status_box_layout.addWidget(self.details_label)

        card_layout.addWidget(self.status_box, alignment=Qt.AlignCenter)

        # Action Buttons Container
        self.btn_layout = QHBoxLayout()
        self.btn_layout.setSpacing(12)
        self.btn_layout.setAlignment(Qt.AlignCenter)

        self.btn_auth_action = QPushButton("Sign in to Telegram")
        self.btn_auth_action.setObjectName("primaryButton")
        self.btn_auth_action.clicked.connect(self.open_login_dialog)
        self.btn_layout.addWidget(self.btn_auth_action)

        self.btn_logout = QPushButton("Sign Out")
        self.btn_logout.clicked.connect(self._on_logout)
        self.btn_logout.setVisible(False)
        self.btn_layout.addWidget(self.btn_logout)

        card_layout.addLayout(self.btn_layout)

        main_layout.addStretch()
        main_layout.addWidget(self.card)
        main_layout.addStretch()

    def _init_status_bar(self):
        """Set up bottom status bar."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready.")

    def _check_initial_auth_state(self):
        """Check if local session is already authenticated (session persistence)."""
        self.status_bar.showMessage("Connecting to Telegram MTProto...")

        def on_success(state: AuthState):
            self.update_auth_ui()

        def on_error(exc):
            logger.error("Error during initial auth check: %s", exc)
            self.update_auth_ui()

        async_runner.run_coroutine_async(
            self.auth_service.check_auth_state(),
            callback=on_success,
            error_callback=on_error,
        )

    def update_auth_ui(self):
        """Refresh UI based on current authentication state."""
        state = self.auth_service.state
        if state == AuthState.AUTHORIZED and self.auth_service.current_user:
            user = self.auth_service.current_user
            name = f"{user['first_name']} {user['last_name']}".strip()
            username = f"@{user['username']}" if user['username'] else "No username"

            self.account_status_label.setText(
                "<b>Account Status:</b> <span style='color: #57f287;'>● Logged In</span>"
            )
            self.details_label.setText(
                f"<b>Name:</b> {name}<br>"
                f"<b>Username:</b> {username}<br>"
                f"<b>Phone:</b> {user['phone']}<br>"
                f"<b>Telegram ID:</b> {user['id']}"
            )
            self.btn_auth_action.setVisible(False)
            self.btn_logout.setVisible(True)
            self.action_login.setEnabled(False)
            self.action_logout.setEnabled(True)
            self.status_bar.showMessage(f"Connected to Telegram as {name} ({username})")

        elif state == AuthState.NOT_CONFIGURED:
            self.account_status_label.setText(
                "<b>Account Status:</b> <span style='color: #fee75c;'>API Not Configured</span>"
            )
            self.details_label.setText("Configure your Telegram API ID & Hash to sign in.")
            self.btn_auth_action.setText("Configure & Sign In")
            self.btn_auth_action.setVisible(True)
            self.btn_logout.setVisible(False)
            self.action_login.setEnabled(True)
            self.action_logout.setEnabled(False)
            self.status_bar.showMessage("Telegram API credentials required.")

        else:
            self.account_status_label.setText(
                "<b>Account Status:</b> <span style='color: #ed4245;'>Not Signed In</span>"
            )
            self.details_label.setText("Sign in with your Telegram account to explore chats and files.")
            self.btn_auth_action.setText("Sign in to Telegram")
            self.btn_auth_action.setVisible(True)
            self.btn_logout.setVisible(False)
            self.action_login.setEnabled(True)
            self.action_logout.setEnabled(False)
            self.status_bar.showMessage("Ready to sign in.")

    def open_login_dialog(self):
        """Open the stepped MTProto login dialog."""
        dialog = LoginDialog(self.auth_service, parent=self)
        dialog.authenticated.connect(self._on_login_success)
        dialog.exec()

    def _on_login_success(self, user_dict):
        """Callback when user completes login in dialog."""
        logger.info("LoginDialog returned authenticated user: %s", user_dict.get("username"))
        self.update_auth_ui()

    def _on_logout(self):
        """Log out the current Telegram account and clear local session."""
        confirm = QMessageBox.question(
            self,
            "Sign Out",
            "Are you sure you want to sign out from Telegram?\n\nThis will remove your local session file from this computer.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        self.status_bar.showMessage("Logging out...")

        def on_success(_):
            self.update_auth_ui()
            self.status_bar.showMessage("Signed out successfully.")

        def on_error(exc):
            logger.error("Logout failed: %s", exc)
            self.update_auth_ui()
            self.status_bar.showMessage("Error during logout.")

        async_runner.run_coroutine_async(
            self.auth_service.log_out(),
            callback=on_success,
            error_callback=on_error,
        )

    def _show_about(self):
        """Show about message."""
        QMessageBox.about(
            self,
            f"About {settings.app_name}",
            f"<h3>{settings.app_name} v{settings.app_version}</h3>"
            "<p>A local-first desktop application to explore, search, and download your Telegram files.</p>"
            "<p>Built with Python, Telethon, PySide6, and SQLite.</p>",
        )

    def closeEvent(self, event):
        """Handle window close event and clean up resources."""
        logger.info("Closing application window...")
        super().closeEvent(event)
