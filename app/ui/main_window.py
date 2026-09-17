"""Main application window for Telegram File Explorer conforming to design specifications."""

import sys
from pathlib import Path
from typing import List, Optional
from PySide6.QtCore import (
    QEasingCurve,
    QKeyCombination,
    QPropertyAnimation,
    Qt,
    QTimer,
    QVariantAnimation,
)
from PySide6.QtGui import QAction, QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
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
from ..database.models import IndexedFileModel
from ..database.repository import DatabaseRepository
from ..services.downloader import DownloadManager
from ..services.indexer import MediaIndexerService
from ..telegram.auth import AuthState, TelegramAuthService
from ..telegram.chats import TelegramChat, TelegramChatService
from ..telegram.client import TelegramClientManager
from .chat_list import ChatListWidget
from .download_manager import DownloadManagerDialog
from .icons import get_icon, get_pixmap, prewarm_icon_cache
from .inline_auth import InlineAuthWidget
from .media_browser import ChatMediaBrowserWidget
from .preview_panel import PreviewDialog, PreviewPanel
from .settings_dialog import SettingsDialog
from .settings_panel import SettingsPanel
from .theme_manager import DARK_TOKENS, LIGHT_TOKENS, theme_manager
from .styles import DARK_THEME, LIGHT_THEME

logger = get_logger("ui.main_window")


class MainWindow(QMainWindow):
    """Main desktop application window conforming to product specifications."""

    def __init__(
        self,
        client_manager: TelegramClientManager = None,
        auth_service: TelegramAuthService = None,
        chat_service: TelegramChatService = None,
        repo: DatabaseRepository = None,
    ):
        super().__init__()
        self.setWindowTitle(f"{settings.app_name} v{settings.app_version}")
        self.setMinimumSize(1100, 700)
        self.resize(1440, 900)

        # Precompute icons to eliminate theme switch lag
        prewarm_icon_cache()

        # Initialize core services
        self.client_manager = client_manager or TelegramClientManager(settings)
        self.auth_service = auth_service or TelegramAuthService(self.client_manager)
        self.chat_service = chat_service or TelegramChatService(self.client_manager)
        self.repo = repo or DatabaseRepository()
        self.download_manager = DownloadManager(self.client_manager)
        self.indexer_service = MediaIndexerService(self.client_manager, db_path=self.repo.db_path)

        self._init_menu_bar()
        self._init_ui()
        self._init_status_bar()
        self._setup_shortcuts()

        theme_manager.theme_changed.connect(self._on_theme_changed)

        # Check session state on start
        QTimer.singleShot(100, self._check_initial_auth_state)

        logger.info("MainWindow initialized successfully.")

    def _init_menu_bar(self):
        """Build actions and shortcuts, then detach native menu bar from view."""
        menu_bar = self.menuBar()

        # File Menu Actions
        file_menu = menu_bar.addMenu("&File")

        self.action_downloads = QAction("&Downloads...", self)
        self.action_downloads.setShortcut(QKeySequence("Ctrl+J"))
        self.action_downloads.setStatusTip("View download manager")
        self.action_downloads.triggered.connect(self.open_download_manager)
        self.action_view_downloads = self.action_downloads
        file_menu.addAction(self.action_downloads)

        self.action_settings = QAction("&Settings...", self)
        self.action_settings.setShortcut(QKeySequence("Ctrl+,"))
        self.action_settings.setStatusTip("Open application settings")
        self.action_settings.triggered.connect(self._toggle_settings_panel)
        file_menu.addAction(self.action_settings)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        exit_action.setStatusTip("Exit the application")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Edit Menu Actions
        edit_menu = menu_bar.addMenu("&Edit")

        self.action_find_files = QAction("&Find Files...", self)
        self.action_find_files.setShortcut(QKeySequence("Ctrl+F"))
        self.action_find_files.setStatusTip("Search media in current chat")
        self.action_find_files.triggered.connect(self._focus_chat_search)
        edit_menu.addAction(self.action_find_files)

        self.action_global_search = QAction("&Global Search...", self)
        self.action_global_search.setShortcut(QKeySequence("Ctrl+K"))
        self.action_global_search.setStatusTip("Global file search across all chats")
        self.action_global_search.triggered.connect(self._focus_global_search)
        edit_menu.addAction(self.action_global_search)

        self.action_refresh_all = QAction("&Refresh", self)
        self.action_refresh_all.setShortcut(QKeySequence("F5"))
        self.action_refresh_all.setStatusTip("Refresh chats and media")
        self.action_refresh_all.triggered.connect(self._on_refresh_all)
        edit_menu.addAction(self.action_refresh_all)

        # Account Menu Actions
        self.account_menu = menu_bar.addMenu("&Account")

        self.action_login = QAction("Sign &In...", self)
        self.action_login.setShortcut(QKeySequence("Ctrl+L"))
        self.action_login.setStatusTip("Sign in with Telegram account")
        self.action_login.triggered.connect(self.open_login_dialog)
        self.account_menu.addAction(self.action_login)

        self.action_refresh_chats = QAction("&Refresh Chats", self)
        self.action_refresh_chats.triggered.connect(self.refresh_chats)
        self.action_refresh_chats.setEnabled(False)
        self.account_menu.addAction(self.action_refresh_chats)

        self.action_logout = QAction("Sign &Out", self)
        self.action_logout.setStatusTip("Sign out and remove local session")
        self.action_logout.triggered.connect(self._on_logout)
        self.action_logout.setEnabled(False)
        self.account_menu.addAction(self.action_logout)

        # Tools Menu Actions
        tools_menu = menu_bar.addMenu("&Tools")
        self.action_index_manager = QAction("&Indexing Manager...", self)
        self.action_index_manager.setShortcut(QKeySequence("Ctrl+I"))
        self.action_index_manager.setStatusTip("Scan and index media")
        self.action_index_manager.triggered.connect(self._on_open_indexing_manager)
        tools_menu.addAction(self.action_index_manager)

        # Help Menu Actions
        help_menu = menu_bar.addMenu("&Help")
        about_action = QAction("&About Telegram File Explorer", self)
        about_action.setShortcut(QKeySequence("F1"))
        about_action.setStatusTip("View application info and version")
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

        # Detach native OS menu bar from view per specification
        self.setMenuBar(None)

    def _setup_shortcuts(self):
        """Configure keyboard accelerators."""
        shortcut_k = QShortcut(QKeySequence("Ctrl+K"), self)
        shortcut_k.activated.connect(self._focus_global_search)

        shortcut_f = QShortcut(QKeySequence("Ctrl+F"), self)
        shortcut_f.activated.connect(self._focus_chat_search)

        shortcut_r = QShortcut(QKeySequence("Ctrl+R"), self)
        shortcut_r.activated.connect(self._on_refresh_all)

        shortcut_comma = QShortcut(QKeySequence("Ctrl+,"), self)
        shortcut_comma.activated.connect(self._toggle_settings_panel)

        shortcut_j = QShortcut(QKeySequence("Ctrl+J"), self)
        shortcut_j.activated.connect(self.open_download_manager)

        shortcut_p = QShortcut(QKeySequence("Ctrl+P"), self)
        shortcut_p.activated.connect(self._toggle_preview_panel)

        shortcut_esc = QShortcut(QKeySequence("Esc"), self)
        shortcut_esc.activated.connect(self._on_escape_pressed)

    def _init_ui(self):
        """Construct central stacked widget layout with TopBar and Workspaces."""
        self.central_stack = QStackedWidget(self)
        self.setCentralWidget(self.central_stack)

        # Page 0: Welcome / Authentication Card View
        self.welcome_page = self._create_welcome_page()
        self.central_stack.addWidget(self.welcome_page)

        # Page 1: Main Application Workspace
        self.workspace_page = self._create_workspace_page()
        self.central_stack.addWidget(self.workspace_page)

    def _create_welcome_page(self) -> QWidget:
        """Create clean welcome / sign-in screen."""
        tokens = theme_manager.get_active_tokens()
        page = QWidget()
        page.setStyleSheet(f"background-color: {tokens['bg_base']};")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        self.card = QFrame(page)
        self.card.setMaximumWidth(560)
        self.card.setStyleSheet(
            f"""
            QFrame {{
                background-color: {tokens['bg_surface']};
                border: 1px solid {tokens['border']};
                border-radius: 12px;
                padding: 24px;
            }}
            """
        )
        card_layout = QVBoxLayout(self.card)
        card_layout.setSpacing(14)
        card_layout.setAlignment(Qt.AlignCenter)

        title_label = QLabel(settings.app_name)
        title_font = QFont("Inter", 20, QFont.Bold)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet(f"color: {tokens['text_primary']};")
        card_layout.addWidget(title_label)

        # Embedded Inline Authentication Widget
        self.auth_widget = InlineAuthWidget(self.auth_service, parent=self)
        self.auth_widget.authenticated.connect(self._on_login_success)
        card_layout.addWidget(self.auth_widget)

        layout.addStretch()
        layout.addWidget(self.card, alignment=Qt.AlignCenter)
        layout.addStretch()
        return page

    def _create_workspace_page(self) -> QWidget:
        """Create the primary workspace: Left Sidebar | Media Browser (stretch) | Right Dock Panels (320px)."""
        tokens = theme_manager.get_active_tokens()
        page = QWidget()
        page.setStyleSheet(f"background-color: {tokens['bg_base']};")
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)

        # 1. Top Bar Header (kept for shortcuts & programmatic access; hidden to match pixel screenshots)
        self.top_bar = self._create_top_bar()
        self.top_bar.hide()
        page_layout.addWidget(self.top_bar)

        # 2. Main Horizontal Splitter
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setStyleSheet(f"QSplitter::handle {{ background-color: {tokens['border']}; width: 1px; }}")

        # Index 0 (Left Edge): Sidebar - Chat List Widget (280px expanded / 72px rail)
        self.chat_list_widget = ChatListWidget()
        self.chat_list_widget.chat_selected.connect(self._on_chat_selected)
        self.chat_list_widget.refresh_requested.connect(self.refresh_chats)
        self.chat_list_widget.settings_clicked.connect(self._toggle_settings_panel)
        self.chat_list_widget.collapsed_changed.connect(self._on_chat_sidebar_collapsed)
        self.main_splitter.addWidget(self.chat_list_widget)

        # Index 1 (Center): Main Content - Chat Media Browser Widget (stretch)
        self.media_browser = ChatMediaBrowserWidget(
            repo=self.repo,
            indexer_service=self.indexer_service,
            parent=self,
        )
        self.media_browser.file_selected.connect(self._on_file_selected)
        self.media_browser.file_double_clicked.connect(self._on_file_double_clicked)
        self.media_browser.download_requested.connect(self._on_download_file)
        self.media_browser.open_requested.connect(self._on_open_file)
        self.media_browser.set_client_manager(self.client_manager)
        self.main_splitter.addWidget(self.media_browser)

        # Index 2 (Right Edge): Preview Panel (320px, initially hidden)
        self.preview_panel = PreviewPanel()
        self.preview_panel.download_requested.connect(self._on_download_file)
        self.preview_panel.close_requested.connect(self._hide_preview_panel)
        self.preview_panel.hide()
        self.preview_opacity = QGraphicsOpacityEffect(self.preview_panel)
        self.preview_panel.setGraphicsEffect(self.preview_opacity)
        self.preview_opacity.setOpacity(1.0)
        self.main_splitter.addWidget(self.preview_panel)

        # Index 3 (Right Edge): Settings Panel (320px, initially hidden)
        self.settings_panel = SettingsPanel(repo=self.repo, parent=self)
        self.settings_panel.close_requested.connect(self._hide_settings_panel)
        self.settings_panel.logout_requested.connect(self._on_logout)
        self.settings_panel.hide()
        self.settings_opacity = QGraphicsOpacityEffect(self.settings_panel)
        self.settings_panel.setGraphicsEffect(self.settings_opacity)
        self.settings_opacity.setOpacity(1.0)
        self.main_splitter.addWidget(self.settings_panel)

        self.file_explorer_widget = self.media_browser
        self.view_stack = self.media_browser.view_stack

        # Initial layout: Sidebar=280px, Browser=fill, Preview=0, Settings=0
        self.main_splitter.setSizes([280, 1160, 0, 0])
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setStretchFactor(2, 0)
        self.main_splitter.setStretchFactor(3, 0)

        page_layout.addWidget(self.main_splitter)
        return page

    def _create_top_bar(self) -> QWidget:
        """Create top bar header matching the design system."""
        tokens = theme_manager.get_active_tokens()
        top_bar = QFrame(self)
        top_bar.setFixedHeight(54)
        top_bar.setStyleSheet(
            f"""
            QFrame {{
                background-color: {tokens['bg_surface']};
                border-bottom: 1px solid {tokens['border']};
                padding: 4px 16px;
            }}
            """
        )
        layout = QHBoxLayout(top_bar)
        layout.setContentsMargins(16, 6, 16, 6)
        layout.setSpacing(12)

        # App Title / Brand
        brand_label = QLabel(settings.app_name)
        brand_font = QFont("Inter", 13, QFont.Bold)
        brand_label.setFont(brand_font)
        brand_label.setStyleSheet(f"color: {tokens['text_primary']};")
        layout.addWidget(brand_label)

        layout.addSpacing(16)

        # Global Search Field
        self.global_search_input = QLineEdit()
        self.global_search_input.setPlaceholderText("Search files across all chats (Ctrl+K)...")
        self.global_search_input.setClearButtonEnabled(True)
        self.global_search_input.setFixedWidth(340)
        self.global_search_input.setStyleSheet(
            f"""
            QLineEdit {{
                background-color: {tokens['bg_surface_2']};
                border: 1px solid {tokens['border']};
                border-radius: 8px;
                color: {tokens['text_primary']};
                padding: 6px 12px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border-color: {tokens['accent']};
            }}
            """
        )
        self.global_search_input.returnPressed.connect(self._on_global_search_enter)
        layout.addWidget(self.global_search_input)

        layout.addStretch()

        # Downloads Button
        self.btn_downloads = QPushButton("Downloads")
        self.btn_downloads.setObjectName("secondaryButton")
        self.btn_downloads.setIcon(get_icon("download", color=tokens["text_secondary"], size=14))
        self.btn_downloads.setToolTip("View Downloads (Ctrl+J)")
        self.btn_downloads.clicked.connect(self.open_download_manager)
        layout.addWidget(self.btn_downloads)

        # Settings Button
        self.btn_settings = QPushButton("Settings")
        self.btn_settings.setObjectName("secondaryButton")
        self.btn_settings.setIcon(get_icon("settings", color=tokens["text_secondary"], size=14))
        self.btn_settings.setToolTip("Open Settings (Ctrl+,)")
        self.btn_settings.clicked.connect(self._toggle_settings_panel)
        layout.addWidget(self.btn_settings)

        # Toggle Preview Button
        self.btn_toggle_preview = QPushButton()
        self.btn_toggle_preview.setObjectName("secondaryButton")
        self.btn_toggle_preview.setIcon(get_icon("panel_right", color=tokens["text_secondary"], size=14))
        self.btn_toggle_preview.setToolTip("Toggle Inspector Panel")
        self.btn_toggle_preview.clicked.connect(self._toggle_preview_panel)
        layout.addWidget(self.btn_toggle_preview)

        # User Profile Label
        self.lbl_user_name = QLabel("")
        self.lbl_user_name.setStyleSheet(f"color: {tokens['accent']}; font-weight: 500; font-size: 12px; padding: 0 4px;")
        layout.addWidget(self.lbl_user_name)

        return top_bar

    def _init_status_bar(self):
        """Set up bottom status bar."""
        tokens = theme_manager.get_active_tokens()
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.status_files_indicator = QLabel("0 files indexed")
        self.status_files_indicator.setStyleSheet(
            f"color: {tokens['text_secondary']}; font-size: 11px; padding: 0 10px; font-weight: 500;"
        )
        self.status_bar.addPermanentWidget(self.status_files_indicator)

        self.status_auth_indicator = QLabel("Not Signed In")
        self.status_auth_indicator.setStyleSheet(
            f"color: {tokens['danger']}; font-size: 11px; padding: 0 10px; font-weight: 500;"
        )
        self.status_bar.addPermanentWidget(self.status_auth_indicator)

        self.status_bar.showMessage("Ready.")
        self._update_status_files_indicator()

    def _on_theme_changed(self, tokens: dict):
        """Update window canvas backgrounds dynamically on theme switch."""
        self.workspace_page.setStyleSheet(f"background-color: {tokens['bg_base']};")
        self.welcome_page.setStyleSheet(f"background-color: {tokens['bg_base']};")
        self.card.setStyleSheet(
            f"""
            QFrame {{
                background-color: {tokens['bg_surface']};
                border: 1px solid {tokens['border']};
                border-radius: 12px;
                padding: 24px;
            }}
            """
        )
        self.main_splitter.setStyleSheet(f"QSplitter::handle {{ background-color: {tokens['border']}; width: 1px; }}")
        self.status_files_indicator.setStyleSheet(
            f"color: {tokens['text_secondary']}; font-size: 11px; padding: 0 10px; font-weight: 500;"
        )
        self._update_window_title_bar()

    def _update_window_title_bar(self):
        """Enable Windows 10/11 immersive dark mode on title bar."""
        if sys.platform == "win32":
            try:
                import ctypes
                hwnd = int(self.winId())
                DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                is_dark = (theme_manager.get_active_tokens()["bg_base"] == DARK_TOKENS["bg_base"])
                val = ctypes.c_int(1 if is_dark else 0)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    DWMWA_USE_IMMERSIVE_DARK_MODE,
                    ctypes.byref(val),
                    ctypes.sizeof(val),
                )
            except Exception:
                pass

    def _update_status_files_indicator(self):
        """Update file count in status bar."""
        try:
            count = self.repo.get_files_count()
            self.status_files_indicator.setText(f"{count:,} files indexed")
        except Exception as e:
            logger.debug("Could not update status files count: %s", e)

    def _check_initial_auth_state(self):
        """Check local Telegram session persistence."""
        self.status_bar.showMessage("Checking Telegram session...")

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
        """Refresh UI based on authentication state."""
        tokens = theme_manager.get_active_tokens()
        state = self.auth_service.state
        if state == AuthState.AUTHORIZED and self.auth_service.current_user:
            user = self.auth_service.current_user
            name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
            username = f"@{user['username']}" if user.get('username') else ""

            self.lbl_user_name.setText(name)
            self.action_login.setEnabled(False)
            self.action_logout.setEnabled(True)
            self.action_refresh_chats.setEnabled(True)

            self.status_auth_indicator.setText(f"Connected: {name}")
            self.status_auth_indicator.setStyleSheet(
                f"color: {tokens['success']}; font-size: 11px; padding: 0 10px; font-weight: 500;"
            )

            self.central_stack.setCurrentIndex(1)
            self.status_bar.showMessage(f"Connected to Telegram as {name} {username}")

            if hasattr(self, "settings_panel"):
                self.settings_panel.set_user_info(name, user.get("username", ""))

        else:
            self.lbl_user_name.setText("")
            self.central_stack.setCurrentIndex(0)
            self.action_login.setEnabled(True)
            self.action_logout.setEnabled(False)
            self.action_refresh_chats.setEnabled(False)

            if state == AuthState.NOT_CONFIGURED:
                self.status_auth_indicator.setText("API Not Configured")
                self.status_auth_indicator.setStyleSheet(
                    f"color: {tokens['warning']}; font-size: 11px; padding: 0 10px; font-weight: 500;"
                )
                self.status_bar.showMessage("Telegram API credentials required.")
            else:
                self.status_auth_indicator.setText("Not Signed In")
                self.status_auth_indicator.setStyleSheet(
                    f"color: {tokens['danger']}; font-size: 11px; padding: 0 10px; font-weight: 500;"
                )
                self.status_bar.showMessage("Ready to sign in.")

        self._update_status_files_indicator()

    def refresh_chats(self):
        """Retrieve accessible dialogs from Telegram MTProto."""
        if self.auth_service.state != AuthState.AUTHORIZED:
            return

        self.status_bar.showMessage("Discovering dialogues from Telegram...")
        self.chat_list_widget.btn_refresh.setEnabled(False)

        def on_success(chats):
            self.chat_list_widget.btn_refresh.setEnabled(True)
            self.chat_list_widget.set_chats(chats)
            self.status_bar.showMessage(f"Discovered {len(chats)} chats from Telegram.")

        def on_error(exc):
            self.chat_list_widget.btn_refresh.setEnabled(True)
            logger.error("Failed to discover chats: %s", exc)
            self.status_bar.showMessage(f"Error loading chats: {exc}")

        async_runner.run_coroutine_async(
            self.chat_service.get_dialogs(limit=200),
            callback=on_success,
            error_callback=on_error,
        )

    def _on_open_indexing_manager(self):
        """Open indexing manager dialog."""
        from .indexing_dialog import IndexingDialog
        from ..services.indexing_manager import IndexingManager
        im = IndexingManager(self.client_manager, db_path=self.repo.db_path)
        chats = getattr(self.chat_list_widget, "_all_chats", [])
        dialog = IndexingDialog(im, available_chats=chats, parent=self)
        dialog.exec()

    def _on_chat_selected(self, chat: TelegramChat):
        """Automatically display chat header, cached files, and progressively stream newer/older media."""
        self.media_browser.set_chat(chat)
        self.status_bar.showMessage(f"Viewing media in {chat.display_name}")

    # ==========================================
    # Slide + Fade Animation Helpers
    # ==========================================
    def _animate_panel_slide_fade(
        self,
        panel: QWidget,
        opacity_effect: QGraphicsOpacityEffect,
        target_width: int,
        target_opacity: float,
        duration: int,
        easing: QEasingCurve.Type,
        panel_index: int,
        on_complete=None,
    ):
        """Animate panel width and opacity with safety checks to prevent mid-flight stacking."""
        if hasattr(panel, "_slide_anim") and panel._slide_anim:
            panel._slide_anim.stop()
        if hasattr(panel, "_fade_anim") and panel._fade_anim:
            panel._fade_anim.stop()

        is_opening = (target_width > 0)
        sizes = self.main_splitter.sizes()
        start_w = sizes[panel_index] if len(sizes) > panel_index else 0

        if is_opening:
            panel.show()
            if start_w == 0:
                opacity_effect.setOpacity(0.0)

        start_opacity = opacity_effect.opacity()

        slide_anim = QVariantAnimation(panel)
        slide_anim.setDuration(duration)
        slide_anim.setEasingCurve(easing)
        slide_anim.setStartValue(float(start_w))
        slide_anim.setEndValue(float(target_width))

        def on_step(val):
            w = int(val)
            panel.setFixedWidth(w)
            s = self.main_splitter.sizes()
            sidebar_w = s[0] if s else 280
            total_w = sum(s)
            if panel_index == 2:  # preview
                self.main_splitter.setSizes([sidebar_w, max(300, total_w - sidebar_w - w), w, 0])
            else:  # settings
                self.main_splitter.setSizes([sidebar_w, max(300, total_w - sidebar_w - w), 0, w])

        def on_finished():
            if not is_opening:
                panel.hide()
                panel.setFixedWidth(320)
                s = self.main_splitter.sizes()
                sidebar_w = s[0] if s else 280
                total_w = sum(s)
                self.main_splitter.setSizes([sidebar_w, total_w - sidebar_w, 0, 0])
            else:
                panel.setFixedWidth(target_width)
                s = self.main_splitter.sizes()
                sidebar_w = s[0] if s else 280
                total_w = sum(s)
                if panel_index == 2:
                    self.main_splitter.setSizes([sidebar_w, max(300, total_w - sidebar_w - target_width), target_width, 0])
                else:
                    self.main_splitter.setSizes([sidebar_w, max(300, total_w - sidebar_w - target_width), 0, target_width])
            if on_complete:
                on_complete()

        slide_anim.valueChanged.connect(on_step)
        slide_anim.finished.connect(on_finished)
        panel._slide_anim = slide_anim

        fade_anim = QPropertyAnimation(opacity_effect, b"opacity", panel)
        fade_anim.setDuration(duration)
        fade_anim.setEasingCurve(easing)
        fade_anim.setStartValue(start_opacity)
        fade_anim.setEndValue(target_opacity)
        panel._fade_anim = fade_anim

        slide_anim.start()
        fade_anim.start()

    def _toggle_settings_panel(self):
        """Toggle right-docked Settings panel with 200ms OutCubic open / 180ms InCubic close slide+fade."""
        sizes = self.main_splitter.sizes()
        is_open = (len(sizes) > 3 and sizes[3] > 0)
        if is_open:
            self._hide_settings_panel()
        else:
            self._hide_preview_panel(immediate=True)
            self._animate_panel_slide_fade(
                self.settings_panel,
                self.settings_opacity,
                target_width=320,
                target_opacity=1.0,
                duration=200,
                easing=QEasingCurve.Type.OutCubic,
                panel_index=3,
            )

    def _hide_settings_panel(self, immediate: bool = False):
        """Hide right-docked Settings panel with 180ms slide+fade."""
        if immediate:
            if hasattr(self.settings_panel, "_slide_anim") and self.settings_panel._slide_anim:
                self.settings_panel._slide_anim.stop()
            if hasattr(self.settings_panel, "_fade_anim") and self.settings_panel._fade_anim:
                self.settings_panel._fade_anim.stop()
            self.settings_panel.hide()
            self.settings_opacity.setOpacity(0.0)
            self.settings_panel.setFixedWidth(320)
            sizes = self.main_splitter.sizes()
            sidebar_w = sizes[0] if sizes else 280
            preview_w = sizes[2] if len(sizes) > 2 else 0
            total_w = sum(sizes)
            self.main_splitter.setSizes([sidebar_w, max(300, total_w - sidebar_w - preview_w), preview_w, 0])
            return

        self._animate_panel_slide_fade(
            self.settings_panel,
            self.settings_opacity,
            target_width=0,
            target_opacity=0.0,
            duration=180,
            easing=QEasingCurve.Type.InCubic,
            panel_index=3,
        )

    def _on_chat_sidebar_collapsed(self, collapsed: bool):
        """Handle sidebar width collapse/expand."""
        sidebar_w = 72 if collapsed else 280
        sizes = self.main_splitter.sizes()
        if len(sizes) >= 4:
            right_p = sizes[2]
            right_s = sizes[3]
            total_w = sum(sizes)
            content_w = max(300, total_w - sidebar_w - right_p - right_s)
            self.main_splitter.setSizes([sidebar_w, content_w, right_p, right_s])

    def _on_file_selected(self, file_model: Optional[IndexedFileModel]):
        """Handle single-click selection on media file (opens persistent 320px right dock with slide+fade)."""
        if not file_model:
            self._hide_preview_panel()
            return

        self.status_bar.showMessage(f"Selected: {file_model.filename} ({file_model.media_type})")
        self._hide_settings_panel(immediate=True)
        self.preview_panel.set_file(file_model)

        sizes = self.main_splitter.sizes()
        is_open = (len(sizes) > 2 and sizes[2] > 0)
        if not is_open:
            self._animate_panel_slide_fade(
                self.preview_panel,
                self.preview_opacity,
                target_width=320,
                target_opacity=1.0,
                duration=200,
                easing=QEasingCurve.Type.OutCubic,
                panel_index=2,
            )

    def _toggle_preview_panel(self):
        """Toggle right-docked preview inspector panel with slide+fade."""
        sizes = self.main_splitter.sizes()
        is_open = (len(sizes) > 2 and sizes[2] > 0)
        if is_open:
            self._hide_preview_panel()
            if hasattr(self, "media_browser"):
                self.media_browser.clear_selection()
        else:
            self._hide_settings_panel(immediate=True)
            self._animate_panel_slide_fade(
                self.preview_panel,
                self.preview_opacity,
                target_width=320,
                target_opacity=1.0,
                duration=200,
                easing=QEasingCurve.Type.OutCubic,
                panel_index=2,
            )

    def _hide_preview_panel(self, immediate: bool = False):
        """Hide right-docked preview panel with 180ms slide+fade."""
        if immediate:
            if hasattr(self.preview_panel, "_slide_anim") and self.preview_panel._slide_anim:
                self.preview_panel._slide_anim.stop()
            if hasattr(self.preview_panel, "_fade_anim") and self.preview_panel._fade_anim:
                self.preview_panel._fade_anim.stop()
            self.preview_panel.hide()
            self.preview_opacity.setOpacity(0.0)
            self.preview_panel.setFixedWidth(320)
            sizes = self.main_splitter.sizes()
            sidebar_w = sizes[0] if sizes else 280
            settings_w = sizes[3] if len(sizes) > 3 else 0
            total_w = sum(sizes)
            self.main_splitter.setSizes([sidebar_w, max(300, total_w - sidebar_w - settings_w), 0, settings_w])
            return

        self._animate_panel_slide_fade(
            self.preview_panel,
            self.preview_opacity,
            target_width=0,
            target_opacity=0.0,
            duration=180,
            easing=QEasingCurve.Type.InCubic,
            panel_index=2,
        )

    def _on_escape_pressed(self):
        """Esc key closes whichever right panel is active and clears selection."""
        self._hide_preview_panel()
        self._hide_settings_panel()
        if hasattr(self, "media_browser"):
            self.media_browser.clear_selection()

    def _on_file_double_clicked(self, file_model: IndexedFileModel):
        """Open detailed media preview dialog on double click."""
        dialog = PreviewDialog(file_model, parent=self)
        dialog.download_requested.connect(self._on_download_file)
        dialog.exec()

    def _on_download_file(self, file_model: IndexedFileModel):
        """Prompt destination directory and start background download."""
        chosen_dir = QFileDialog.getExistingDirectory(
            self,
            "Select Download Destination Folder",
            str(settings.download_dir),
        )
        if not chosen_dir:
            return

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

    def open_download_manager(self):
        """Open the downloads inspector modal dialog."""
        dialog = DownloadManagerDialog(self.download_manager, parent=self)
        dialog.exec()

    def open_settings_dialog(self):
        """Open right-docked settings panel."""
        self._toggle_settings_panel()

    def _on_open_file(self, file_model: IndexedFileModel):
        """Open downloaded file in system viewer, or launch preview dialog if not yet downloaded."""
        local_path = settings.download_dir / file_model.filename
        if local_path.exists():
            from ..services.preview import PreviewService
            PreviewService.open_in_system_viewer(str(local_path))
        else:
            self._on_file_double_clicked(file_model)

    def _apply_theme(self, theme_name: str):
        """Switch application stylesheet dynamically using ThemeManager."""
        theme_manager.set_theme(theme_name)

    def open_login_dialog(self):
        """Switch to landing page and focus inline authentication card."""
        self.central_stack.setCurrentIndex(0)
        if hasattr(self, "auth_widget"):
            self.auth_widget.reset_to_initial()

    def _on_login_success(self, user_dict):
        """Callback when user completes authentication."""
        self.update_auth_ui()
        self.refresh_chats()

    def _on_logout(self):
        """Log out and remove local session file."""
        confirm = QMessageBox.question(
            self,
            "Sign Out",
            "Are you sure you want to sign out from Telegram?\n\nThis will remove your local session file from this computer.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        self.status_bar.showMessage("Signing out...")

        def on_success(_):
            self.chat_list_widget.set_chats([])
            self.media_browser.set_chat(None)
            if hasattr(self, "auth_widget"):
                self.auth_widget.reset_to_initial()
            self.update_auth_ui()
            self.status_bar.showMessage("Signed out successfully.")

        def on_error(exc):
            logger.error("Logout failed: %s", exc)
            self.update_auth_ui()
            self.status_bar.showMessage("Error during sign out.")

        async_runner.run_coroutine_async(
            self.auth_service.log_out(),
            callback=on_success,
            error_callback=on_error,
        )

    def _focus_global_search(self):
        """Focus the top bar global search input."""
        if self.central_stack.currentIndex() == 1:
            self.global_search_input.setFocus()
            self.global_search_input.selectAll()

    def _on_find_files(self):
        """Focus the media browser search input."""
        if hasattr(self, "view_stack") and self.view_stack:
            self.view_stack.setCurrentIndex(1)
        if hasattr(self, "file_explorer_widget") and self.file_explorer_widget:
            self.file_explorer_widget.focus_search()

    def _focus_chat_search(self):
        """Focus the media browser search input."""
        self._on_find_files()

    def _on_global_search_enter(self):
        """Trigger search across current chat."""
        query = self.global_search_input.text().strip()
        if hasattr(self, "media_browser"):
            self.media_browser.search_input.setText(query)

    def _on_refresh_all(self):
        """Refresh chats, indexed files, and status indicators."""
        if self.auth_service.state == AuthState.AUTHORIZED:
            self.refresh_chats()
        if hasattr(self, "media_browser"):
            self.media_browser.reload_files()
        self._update_status_files_indicator()
        self.status_bar.showMessage("Refreshed chats and media index.", 3000)

    def _show_about(self):
        """Display About dialog without emojis."""
        import sys
        import PySide6
        import telethon

        py_ver = sys.version.split()[0]
        qt_ver = PySide6.__version__
        telethon_ver = telethon.__version__

        about_text = (
            f"<div style='font-family: sans-serif; color: #F4F4F5;'>"
            f"<h2 style='margin-bottom: 4px; color: #229ED9;'>{settings.app_name} v{settings.app_version}</h2>"
            f"<p style='color: #A1A1AA; margin-top: 0;'>Desktop Telegram MTProto File Manager & Explorer</p>"
            f"<hr style='border: 0; border-top: 1px solid #27272A;' />"
            f"<p><b>System & Engine Information:</b></p>"
            f"<ul style='line-height: 1.5; color: #D4D4D8;'>"
            f"<li><b>Python:</b> {py_ver}</li>"
            f"<li><b>PySide6 (Qt):</b> {qt_ver}</li>"
            f"<li><b>Telethon:</b> {telethon_ver}</li>"
            f"<li><b>Database:</b> SQLite FTS5 Full-Text Search</li>"
            f"</ul>"
            f"<p><b>Local-First Privacy Guarantee:</b></p>"
            f"<p style='color: #A1A1AA; font-size: 12px; line-height: 1.4;'>"
            f"All credentials, session files, databases, and media downloads stay exclusively "
            f"on your computer in the <code>data/</code> folder. 2FA passwords are kept only in volatile memory. "
            f"No data is ever transmitted to third-party servers."
            f"</p>"
            f"</div>"
        )
        QMessageBox.about(
            self,
            f"About {settings.app_name}",
            about_text,
        )
