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
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from ..core.async_runner import async_runner
from ..core.config import settings
from ..core.logger import get_logger
from ..telegram.auth import AuthState, TelegramAuthService
from ..telegram.chats import TelegramChat, TelegramChatService
from ..database.repository import DatabaseRepository
from ..telegram.client import TelegramClientManager
from .chat_detail import ChatDetailWidget
from .chat_list import ChatListWidget
from .file_explorer import FileExplorerWidget
from .login_dialog import LoginDialog

logger = get_logger("ui.main_window")


class MainWindow(QMainWindow):
    """Main desktop application window."""

    def __init__(
        self,
        client_manager: TelegramClientManager = None,
        auth_service: TelegramAuthService = None,
        chat_service: TelegramChatService = None,
        repo: DatabaseRepository = None,
    ):
        super().__init__()
        self.setWindowTitle(f"{settings.app_name} v{settings.app_version}")
        self.setMinimumSize(960, 640)
        self.resize(1140, 760)

        # Initialize core services
        self.client_manager = client_manager or TelegramClientManager(settings)
        self.auth_service = auth_service or TelegramAuthService(self.client_manager)
        self.chat_service = chat_service or TelegramChatService(self.client_manager)
        self.repo = repo or DatabaseRepository()


        self._init_menu_bar()
        self._init_ui()
        self._init_status_bar()

        # Check session state on start
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

        self.action_refresh_chats = QAction("&Refresh Chats", self)
        self.action_refresh_chats.setShortcut("F5")
        self.action_refresh_chats.triggered.connect(self.refresh_chats)
        self.action_refresh_chats.setEnabled(False)
        self.account_menu.addAction(self.action_refresh_chats)

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
        """Construct central stacked widget layout."""
        self.central_stack = QStackedWidget(self)
        self.setCentralWidget(self.central_stack)

        # Page 0: Welcome / Authentication Card View
        self.welcome_page = self._create_welcome_page()
        self.central_stack.addWidget(self.welcome_page)

        # Page 1: Chat Explorer Split View (Discovery sidebar + detail view)
        self.explorer_page = self._create_explorer_page()
        self.central_stack.addWidget(self.explorer_page)

    def _create_welcome_page(self) -> QWidget:
        """Create landing / authentication page."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(20)

        self.card = QFrame(page)
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

        title_label = QLabel(f"📂 {settings.app_name}")
        title_font = QFont()
        title_font.setPointSize(22)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color: #ffffff;")
        card_layout.addWidget(title_label)

        subtitle_label = QLabel(
            "Browse, index, search, preview, and download files from your Telegram account."
        )
        subtitle_label.setAlignment(Qt.AlignCenter)
        subtitle_label.setStyleSheet("color: #949ba4; font-size: 14px;")
        card_layout.addWidget(subtitle_label)

        self.status_box = QFrame(page)
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

        self.btn_auth_action = QPushButton("Sign in to Telegram")
        self.btn_auth_action.setObjectName("primaryButton")
        self.btn_auth_action.clicked.connect(self.open_login_dialog)
        card_layout.addWidget(self.btn_auth_action, alignment=Qt.AlignCenter)

        layout.addStretch()
        layout.addWidget(self.card)
        layout.addStretch()
        return page

    def _create_explorer_page(self) -> QWidget:
        """Create split-pane chat discovery and file explorer page."""
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)

        # Top Mode Switcher Bar
        mode_bar = QFrame()
        mode_bar.setStyleSheet(
            """
            QFrame {
                background-color: #18191c;
                border-bottom: 1px solid #2b2d31;
                padding: 4px 12px;
            }
            """
        )
        mb_layout = QHBoxLayout(mode_bar)
        mb_layout.setContentsMargins(12, 4, 12, 4)
        mb_layout.setSpacing(8)

        self.btn_nav_chats = QPushButton("💬 Chats Discovery")
        self.btn_nav_chats.setObjectName("primaryButton")
        self.btn_nav_chats.clicked.connect(lambda: self._switch_main_view(0))
        mb_layout.addWidget(self.btn_nav_chats)

        self.btn_nav_files = QPushButton("📂 File Explorer")
        self.btn_nav_files.clicked.connect(lambda: self._switch_main_view(1))
        mb_layout.addWidget(self.btn_nav_files)

        mb_layout.addStretch()
        page_layout.addWidget(mode_bar)

        # View Stack
        self.view_stack = QStackedWidget()

        # View 0: Chats & Chat Detail Splitter
        chat_splitter = QSplitter(Qt.Horizontal)
        chat_splitter.setStyleSheet("QSplitter::handle { background-color: #2b2d31; width: 1px; }")

        self.chat_list_widget = ChatListWidget()
        self.chat_list_widget.setMinimumWidth(320)
        self.chat_list_widget.setMaximumWidth(420)
        self.chat_list_widget.chat_selected.connect(self._on_chat_selected)
        self.chat_list_widget.refresh_requested.connect(self.refresh_chats)
        chat_splitter.addWidget(self.chat_list_widget)

        self.chat_detail_widget = ChatDetailWidget()
        chat_splitter.addWidget(self.chat_detail_widget)
        chat_splitter.setStretchFactor(0, 0)
        chat_splitter.setStretchFactor(1, 1)
        self.view_stack.addWidget(chat_splitter)

        # View 1: Main File Explorer
        self.file_explorer_widget = FileExplorerWidget(self.repo)
        self.view_stack.addWidget(self.file_explorer_widget)

        page_layout.addWidget(self.view_stack)
        return page

    def _switch_main_view(self, index: int):
        """Switch between Chats Discovery (0) and File Explorer (1)."""
        self.view_stack.setCurrentIndex(index)
        if index == 0:
            self.btn_nav_chats.setObjectName("primaryButton")
            self.btn_nav_files.setObjectName("")
        else:
            self.btn_nav_chats.setObjectName("")
            self.btn_nav_files.setObjectName("primaryButton")
            self.file_explorer_widget.reload_files()
        self.btn_nav_chats.style().unpolish(self.btn_nav_chats)
        self.btn_nav_chats.style().polish(self.btn_nav_chats)
        self.btn_nav_files.style().unpolish(self.btn_nav_files)
        self.btn_nav_files.style().polish(self.btn_nav_files)


    def _init_status_bar(self):
        """Set up bottom status bar."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready.")

    def _check_initial_auth_state(self):
        """Check if local session is already authenticated (session persistence)."""
        self.status_bar.showMessage("Checking session...")

        def on_success(state: AuthState):
            self.update_auth_ui()
            if state == AuthState.AUTHORIZED:
                self.refresh_chats()

        def on_error(exc):
            logger.error("Error checking auth state: %s", exc)
            self.update_auth_ui()

        async_runner.run_coroutine_async(
            self.auth_service.check_auth_state(),
            callback=on_success,
            error_callback=on_error,
        )

    def update_auth_ui(self):
        """Refresh UI state based on authentication."""
        state = self.auth_service.state
        if state == AuthState.AUTHORIZED and self.auth_service.current_user:
            user = self.auth_service.current_user
            name = f"{user['first_name']} {user['last_name']}".strip()
            username = f"@{user['username']}" if user['username'] else "No username"

            self.action_login.setEnabled(False)
            self.action_logout.setEnabled(True)
            self.action_refresh_chats.setEnabled(True)

            self.central_stack.setCurrentIndex(1)
            self.status_bar.showMessage(f"Connected to Telegram as {name} ({username})")

        else:
            self.central_stack.setCurrentIndex(0)
            self.action_login.setEnabled(True)
            self.action_logout.setEnabled(False)
            self.action_refresh_chats.setEnabled(False)

            if state == AuthState.NOT_CONFIGURED:
                self.account_status_label.setText(
                    "<b>Account Status:</b> <span style='color: #fee75c;'>API Not Configured</span>"
                )
                self.details_label.setText("Configure your Telegram API ID & Hash to sign in.")
                self.btn_auth_action.setText("Configure & Sign In")
                self.status_bar.showMessage("Telegram API credentials required.")
            else:
                self.account_status_label.setText(
                    "<b>Account Status:</b> <span style='color: #ed4245;'>Not Signed In</span>"
                )
                self.details_label.setText("Sign in with your Telegram account to explore chats and files.")
                self.btn_auth_action.setText("Sign in to Telegram")
                self.status_bar.showMessage("Ready to sign in.")

    def refresh_chats(self):
        """Retrieve accessible chats from Telegram MTProto in background."""
        if self.auth_service.state != AuthState.AUTHORIZED:
            return

        self.status_bar.showMessage("Discovering accessible chats & channels...")
        self.chat_list_widget.btn_refresh.setEnabled(False)

        def on_success(chats):
            self.chat_list_widget.btn_refresh.setEnabled(True)
            self.chat_list_widget.set_chats(chats)
            self.status_bar.showMessage(f"Discovered {len(chats)} chats from your account.")

        def on_error(exc):
            self.chat_list_widget.btn_refresh.setEnabled(True)
            logger.error("Failed to discover chats: %s", exc)
            self.status_bar.showMessage(f"Error loading chats: {exc}")

        async_runner.run_coroutine_async(
            self.chat_service.get_dialogs(limit=150),
            callback=on_success,
            error_callback=on_error,
        )

    def _on_chat_selected(self, chat: TelegramChat):
        """Handle chat navigation."""
        self.chat_detail_widget.set_chat(chat)
        self.status_bar.showMessage(f"Viewing chat: {chat.display_name} (ID: {chat.id})")

    def open_login_dialog(self):
        """Open the stepped MTProto login dialog."""
        dialog = LoginDialog(self.auth_service, parent=self)
        dialog.authenticated.connect(self._on_login_success)
        dialog.exec()

    def _on_login_success(self, user_dict):
        """Callback when user completes login in dialog."""
        self.update_auth_ui()
        self.refresh_chats()

    def _on_logout(self):
        """Log out and reset application state."""
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
            self.chat_list_widget.set_chats([])
            self.chat_detail_widget.set_chat(None)
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
