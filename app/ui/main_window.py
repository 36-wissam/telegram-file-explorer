"""Main application window for Telegram File Explorer."""

from typing import List, Optional
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
        from ..services.downloader import DownloadManager
        self.download_manager = DownloadManager(self.client_manager)
        from ..services.indexing_manager import IndexingManager
        self.indexing_manager = IndexingManager(self.client_manager, db_path=self.repo.db_path)
        self.indexing_manager.indexing_finished.connect(self._on_indexing_finished)

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
        exit_action.setStatusTip("Exit the application")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Edit Menu
        edit_menu = menu_bar.addMenu("&Edit")
        self.action_find_files = QAction("&Find Files...", self)
        self.action_find_files.setShortcut("Ctrl+F")
        self.action_find_files.setStatusTip("Search and filter indexed Telegram files")
        self.action_find_files.triggered.connect(self._on_find_files)
        edit_menu.addAction(self.action_find_files)

        self.action_refresh_all = QAction("&Refresh All", self)
        self.action_refresh_all.setShortcut("F5")
        self.action_refresh_all.setStatusTip("Refresh chats and indexed files")
        self.action_refresh_all.triggered.connect(self._on_refresh_all)
        edit_menu.addAction(self.action_refresh_all)

        # Account Menu
        self.account_menu = menu_bar.addMenu("&Account")
        self.action_login = QAction("Sign &In...", self)
        self.action_login.setShortcut("Ctrl+L")
        self.action_login.setStatusTip("Sign in with your Telegram account")
        self.action_login.triggered.connect(self.open_login_dialog)
        self.account_menu.addAction(self.action_login)

        self.action_refresh_chats = QAction("&Refresh Chats", self)
        self.action_refresh_chats.triggered.connect(self.refresh_chats)
        self.action_refresh_chats.setEnabled(False)
        self.account_menu.addAction(self.action_refresh_chats)

        self.action_logout = QAction("Sign &Out", self)
        self.action_logout.setStatusTip("Sign out and clear local session")
        self.action_logout.triggered.connect(self._on_logout)
        self.action_logout.setEnabled(False)
        self.account_menu.addAction(self.action_logout)

        # Downloads Menu
        downloads_menu = menu_bar.addMenu("&Downloads")
        self.action_view_downloads = QAction("View &Downloads...", self)
        self.action_view_downloads.setShortcut("Ctrl+J")
        self.action_view_downloads.setStatusTip("View active and completed downloads")
        self.action_view_downloads.triggered.connect(self.open_download_manager)
        downloads_menu.addAction(self.action_view_downloads)

        # Tools Menu
        tools_menu = menu_bar.addMenu("&Tools")
        self.action_index_manager = QAction("⚡ &Indexing Manager...", self)
        self.action_index_manager.setShortcut("Ctrl+I")
        self.action_index_manager.setStatusTip("Scan and index Telegram files in background")
        self.action_index_manager.triggered.connect(lambda: self.open_indexing_manager())
        tools_menu.addAction(self.action_index_manager)

        # Help Menu
        help_menu = menu_bar.addMenu("&Help")
        about_action = QAction("&About Telegram File Explorer", self)
        about_action.setShortcut("F1")
        about_action.setStatusTip("View application version and system information")
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
        """Create landing / authentication page with inline multi-step sign in."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        self.card = QFrame(page)
        self.card.setMaximumWidth(560)
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
            "Local-first Telegram MTProto file manager, full-text search, and downloader."
        )
        subtitle_label.setAlignment(Qt.AlignCenter)
        subtitle_label.setStyleSheet("color: #949ba4; font-size: 13px;")
        card_layout.addWidget(subtitle_label)

        privacy_badge = QLabel("🛡️ 100% Local-First: Credentials & sessions never leave this PC")
        privacy_badge.setAlignment(Qt.AlignCenter)
        privacy_badge.setStyleSheet(
            "background-color: #232428; color: #57f287; border-radius: 6px; "
            "padding: 6px 12px; font-size: 11px; font-weight: 500;"
        )
        card_layout.addWidget(privacy_badge)

        # Embedded Inline Authentication Widget
        from .inline_auth import InlineAuthWidget
        self.auth_widget = InlineAuthWidget(self.auth_service, parent=self)
        self.auth_widget.authenticated.connect(self._on_login_success)
        card_layout.addWidget(self.auth_widget)

        layout.addStretch()
        layout.addWidget(self.card, alignment=Qt.AlignCenter)
        layout.addStretch()
        return page

    def _create_explorer_page(self) -> QWidget:
        """Create split-pane chat discovery and file explorer page matching SaaS layout."""
        from .activity_rail import ActivityRailWidget

        page = QWidget()
        page.setStyleSheet("background-color: #13141f;")
        root_h_layout = QHBoxLayout(page)
        root_h_layout.setContentsMargins(0, 0, 0, 0)
        root_h_layout.setSpacing(0)

        # 1. Leftmost Activity Icon Rail (~56px)
        self.activity_rail = ActivityRailWidget(self)
        self.activity_rail.nav_changed.connect(self._on_rail_nav)
        self.activity_rail.profile_clicked.connect(self.open_login_dialog)
        self.activity_rail.activity_clicked.connect(self.open_download_manager)
        root_h_layout.addWidget(self.activity_rail)

        # 2. Main Body Container (Header + Views)
        body_widget = QWidget()
        body_widget.setStyleSheet("background-color: #13141f;")
        body_layout = QVBoxLayout(body_widget)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        # Top Breadcrumb & Action Header Bar
        top_header = QFrame()
        top_header.setFixedHeight(52)
        top_header.setStyleSheet(
            """
            QFrame {
                background-color: #1a1c29;
                border-bottom: 1px solid #1e202e;
                padding: 4px 16px;
            }
            """
        )
        th_layout = QHBoxLayout(top_header)
        th_layout.setContentsMargins(16, 4, 16, 4)
        th_layout.setSpacing(12)

        # Hamburger toggle
        self.btn_hamburger = QPushButton("☰")
        self.btn_hamburger.setFixedSize(32, 32)
        self.btn_hamburger.setStyleSheet(
            """
            QPushButton {
                background: transparent;
                color: #94a3b8;
                border: none;
                font-size: 16px;
                padding: 0;
            }
            QPushButton:hover {
                color: #ffffff;
            }
            """
        )
        self.btn_hamburger.clicked.connect(lambda: self._switch_main_view(0 if self.view_stack.currentIndex() == 1 else 1))
        th_layout.addWidget(self.btn_hamburger)

        # Breadcrumbs
        self.breadcrumb_label = QLabel("<b>All Chats</b>  ›  <b>Workspace</b>  ›  Media ▾")
        self.breadcrumb_label.setStyleSheet("color: #94a3b8; font-size: 13px;")
        th_layout.addWidget(self.breadcrumb_label)

        th_layout.addStretch()

        # View Mode Switchers for backwards compatibility
        self.btn_nav_chats = QPushButton("💬 Chats")
        self.btn_nav_chats.setObjectName("darkPillButton")
        self.btn_nav_chats.clicked.connect(lambda: self._switch_main_view(0))
        th_layout.addWidget(self.btn_nav_chats)

        self.btn_nav_files = QPushButton("📂 Files")
        self.btn_nav_files.setObjectName("darkPillButton")
        self.btn_nav_files.clicked.connect(lambda: self._switch_main_view(1))
        th_layout.addWidget(self.btn_nav_files)

        # Avatar group stack
        avatars_label = QLabel("👥")
        avatars_label.setStyleSheet("font-size: 16px; color: #94a3b8; padding: 0 4px;")
        avatars_label.setToolTip("Active Session")
        th_layout.addWidget(avatars_label)

        # Search icon button
        self.btn_quick_search = QPushButton("🔍")
        self.btn_quick_search.setFixedSize(32, 32)
        self.btn_quick_search.setStyleSheet(
            """
            QPushButton {
                background-color: #24273b;
                color: #94a3b8;
                border: 1px solid #2e3248;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #2f334d;
                color: #ffffff;
            }
            """
        )
        self.btn_quick_search.clicked.connect(self._on_find_files)
        th_layout.addWidget(self.btn_quick_search)

        # Primary Action Button: ⚡ Index Media / Upload (Royal Blue)
        self.btn_open_indexer = QPushButton("⚡ Index Media")
        self.btn_open_indexer.setObjectName("primaryButton")
        self.btn_open_indexer.clicked.connect(lambda: self.open_indexing_manager())
        th_layout.addWidget(self.btn_open_indexer)

        body_layout.addWidget(top_header)

        # View Stack
        self.view_stack = QStackedWidget()

        # View 0: Chats & Chat Detail Splitter
        chat_splitter = QSplitter(Qt.Horizontal)
        chat_splitter.setStyleSheet("QSplitter::handle { background-color: #1e202e; width: 1px; }")

        self.chat_list_widget = ChatListWidget()
        self.chat_list_widget.setMinimumWidth(300)
        self.chat_list_widget.setMaximumWidth(400)
        self.chat_list_widget.chat_selected.connect(self._on_chat_selected)
        self.chat_list_widget.refresh_requested.connect(self.refresh_chats)
        chat_splitter.addWidget(self.chat_list_widget)

        self.chat_detail_widget = ChatDetailWidget()
        self.chat_detail_widget.index_chat_requested.connect(lambda cid: self.open_indexing_manager(preselected_chat_id=cid))
        chat_splitter.addWidget(self.chat_detail_widget)
        chat_splitter.setStretchFactor(0, 0)
        chat_splitter.setStretchFactor(1, 1)
        self.view_stack.addWidget(chat_splitter)

        # View 1: Main File Explorer
        self.file_explorer_widget = FileExplorerWidget(self.repo)
        self.file_explorer_widget.preview_panel.download_requested.connect(self._on_download_file)
        self.view_stack.addWidget(self.file_explorer_widget)

        body_layout.addWidget(self.view_stack)
        root_h_layout.addWidget(body_widget)
        return page

    def _on_rail_nav(self, index: int):
        """Handle activity rail navigation clicks."""
        if index == 0:
            self._switch_main_view(0)
        elif index == 1:
            self._switch_main_view(1)
        elif index == 2:
            self.open_indexing_manager()
        elif index == 3:
            self.open_download_manager()
        elif index == 4:
            self._on_find_files()

    def open_indexing_manager(self, preselected_chat_id: Optional[int] = None):
        """Open the media indexing management dialog."""
        from .indexing_dialog import IndexingDialog
        chats = []
        if hasattr(self, "chat_list_widget"):
            chats = getattr(self.chat_list_widget, "chats", getattr(self.chat_list_widget, "_all_chats", []))
        if not chats:
            db_chats = self.repo.get_chats()
            from ..telegram.chats import ChatType, TelegramChat
            chats = [
                TelegramChat(
                    id=c.id,
                    title=c.title,
                    chat_type=ChatType(c.chat_type) if c.chat_type in [e.value for e in ChatType] else ChatType.UNKNOWN,
                )
                for c in db_chats
            ]
        dialog = IndexingDialog(
            self.indexing_manager,
            available_chats=chats,
            preselected_chat_id=preselected_chat_id,
            parent=self,
        )
        dialog.exec()

    def _on_indexing_finished(self, total_files: int, is_cancelled: bool):
        """Update file explorer and chat filter when indexing completes."""
        if hasattr(self, "file_explorer_widget"):
            self.file_explorer_widget.refresh_chats_filter()
            self.file_explorer_widget.reload_files()
        self._update_status_files_indicator()
        status_txt = (
            f"Indexing finished: {total_files} files indexed."
            if not is_cancelled
            else "Indexing cancelled."
        )
        self.statusBar().showMessage(status_txt, 6000)

    def open_download_manager(self):
        """Open the downloads inspector dialog."""
        from .download_manager import DownloadManagerDialog
        dialog = DownloadManagerDialog(self.download_manager, parent=self)
        dialog.exec()

    def _on_download_file(self, file_model):
        """Prompt destination directory and begin background download."""
        from PySide6.QtWidgets import QFileDialog
        chosen_dir = QFileDialog.getExistingDirectory(
            self,
            "Select Download Destination Folder",
            str(settings.download_dir),
        )
        if not chosen_dir:
            return

        from pathlib import Path
        dest_path = Path(chosen_dir)
        task = self.download_manager.start_download(
            chat_id=file_model.chat_id,
            message_id=file_model.message_id,
            file_id=file_model.file_id,
            filename=file_model.filename,
            destination_dir=dest_path,
            total_size=file_model.file_size,
        )

        self.status_bar.showMessage(f"Downloading {file_model.filename} to {dest_path.name}...")
        self.open_download_manager()


    def _switch_main_view(self, index: int):
        """Switch between Chats Discovery (0) and File Explorer (1)."""
        self.view_stack.setCurrentIndex(index)
        if hasattr(self, "activity_rail"):
            self.activity_rail.set_current_index(index)

        if index == 0:
            self.btn_nav_chats.setObjectName("primaryButton")
            self.btn_nav_files.setObjectName("")
            if hasattr(self, "breadcrumb_label"):
                self.breadcrumb_label.setText("<b>All Chats</b>  ›  <b>Chats Discovery</b> ▾")
        else:
            self.btn_nav_chats.setObjectName("")
            self.btn_nav_files.setObjectName("primaryButton")
            if hasattr(self, "breadcrumb_label"):
                self.breadcrumb_label.setText("<b>All Files</b>  ›  <b>File Explorer</b> ▾")
            self.file_explorer_widget.reload_files()
        self.btn_nav_chats.style().unpolish(self.btn_nav_chats)
        self.btn_nav_chats.style().polish(self.btn_nav_chats)
        self.btn_nav_files.style().unpolish(self.btn_nav_files)
        self.btn_nav_files.style().polish(self.btn_nav_files)

    def _init_status_bar(self):
        """Set up bottom status bar with permanent status indicators."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.status_files_indicator = QLabel("📁 0 files")
        self.status_files_indicator.setStyleSheet(
            "color: #94a3b8; font-size: 11px; padding: 0 10px; font-weight: 500;"
        )
        self.status_bar.addPermanentWidget(self.status_files_indicator)

        self.status_auth_indicator = QLabel("🔴 Not Signed In")
        self.status_auth_indicator.setStyleSheet(
            "color: #ed4245; font-size: 11px; padding: 0 10px; font-weight: 500;"
        )
        self.status_bar.addPermanentWidget(self.status_auth_indicator)

        self.status_bar.showMessage("Ready.")
        self._update_status_files_indicator()

    def _update_status_files_indicator(self):
        """Update the permanent status bar file count indicator."""
        try:
            count = self.repo.get_files_count()
            self.status_files_indicator.setText(f"📁 {count:,} files")
        except Exception as e:
            logger.debug("Could not update status files count: %s", e)

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

            if hasattr(self, "activity_rail"):
                self.activity_rail.set_user_info(name, True)

            self.action_login.setEnabled(False)
            self.action_logout.setEnabled(True)
            self.action_refresh_chats.setEnabled(True)

            self.status_auth_indicator.setText(f"🟢 {name}")
            self.status_auth_indicator.setStyleSheet(
                "color: #57f287; font-size: 11px; padding: 0 10px; font-weight: bold;"
            )

            self.central_stack.setCurrentIndex(1)
            self.status_bar.showMessage(f"Connected to Telegram as {name} ({username})")

        else:
            if hasattr(self, "activity_rail"):
                self.activity_rail.set_user_info("Guest", False)

            self.central_stack.setCurrentIndex(0)
            self.action_login.setEnabled(True)
            self.action_logout.setEnabled(False)
            self.action_refresh_chats.setEnabled(False)

            if state == AuthState.NOT_CONFIGURED:
                self.status_auth_indicator.setText("🟡 API Not Configured")
                self.status_auth_indicator.setStyleSheet(
                    "color: #fee75c; font-size: 11px; padding: 0 10px; font-weight: bold;"
                )
                self.status_bar.showMessage("Telegram API credentials required.")
            else:
                self.status_auth_indicator.setText("🔴 Not Signed In")
                self.status_auth_indicator.setStyleSheet(
                    "color: #ed4245; font-size: 11px; padding: 0 10px; font-weight: bold;"
                )
                self.status_bar.showMessage("Ready to sign in.")

        self._update_status_files_indicator()

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
        if hasattr(self, "breadcrumb_label"):
            self.breadcrumb_label.setText(f"<b>All Chats</b>  ›  <b>{chat.display_name}</b>  ›  Media ▾")
        self.status_bar.showMessage(f"Viewing chat: {chat.display_name} (ID: {chat.id})")

    def open_login_dialog(self):
        """Switch to welcome page and focus the inline sign-in card."""
        self.central_stack.setCurrentIndex(0)
        self.action_login.setEnabled(True)
        if hasattr(self, "auth_widget"):
            self.auth_widget.reset_to_initial()

    def _on_login_success(self, user_dict):
        """Callback when user completes login."""
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
            if hasattr(self, "auth_widget"):
                self.auth_widget.reset_to_initial()
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

    def _on_find_files(self):
        """Switch to file explorer view and focus the search box."""
        if self.central_stack.currentIndex() == 1:
            self._switch_main_view(1)
            self.file_explorer_widget.focus_search()
        else:
            self.status_bar.showMessage("Sign in to search and explore files.", 3000)

    def _on_refresh_all(self):
        """Refresh chats, indexed files, and status indicators."""
        if self.auth_service.state == AuthState.AUTHORIZED:
            self.refresh_chats()
        if hasattr(self, "file_explorer_widget"):
            self.file_explorer_widget.refresh_chats_filter()
            self.file_explorer_widget.reload_files()
        self._update_status_files_indicator()
        self.status_bar.showMessage("Refreshed chats and file index.", 3000)

    def _show_about(self):
        """Show enriched About dialog with versions and local privacy assurance."""
        import sys
        import PySide6
        import telethon

        py_ver = sys.version.split()[0]
        qt_ver = PySide6.__version__
        telethon_ver = telethon.__version__

        about_text = (
            f"<div style='font-family: sans-serif;'>"
            f"<h2 style='margin-bottom: 4px; color: #5865f2;'>📂 {settings.app_name} v{settings.app_version}</h2>"
            f"<p style='color: #949ba4; margin-top: 0;'>Desktop Telegram MTProto File Manager & Explorer</p>"
            f"<hr style='border: 0; border-top: 1px solid #2b2d31;' />"
            f"<p><b>System & Engine Information:</b></p>"
            f"<ul style='line-height: 1.5; color: #dbdee1;'>"
            f"<li><b>Python:</b> {py_ver}</li>"
            f"<li><b>PySide6 (Qt):</b> {qt_ver}</li>"
            f"<li><b>Telethon (MTProto):</b> {telethon_ver}</li>"
            f"<li><b>Database:</b> SQLite FTS5 Full-Text Search Engine</li>"
            f"</ul>"
            f"<p><b>🛡️ Local-First Privacy Guarantee:</b></p>"
            f"<p style='color: #949ba4; font-size: 12px; line-height: 1.4;'>"
            f"All credentials, session files, databases, and media downloads stay exclusively "
            f"on your computer in the <code>data/</code> folder. 2FA passwords are kept only in volatile RAM. "
            f"No data is ever transmitted to external third-party servers."
            f"</p>"
            f"<p style='color: #949ba4; font-size: 11px;'>Repository: https://github.com/36-wissam/telegram-file-explorer</p>"
            f"</div>"
        )
        QMessageBox.about(
            self,
            f"About {settings.app_name}",
            about_text,
        )

