"""Slide-in / docked settings panel matching right-side design specifications."""

import shutil
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal, QSize, QSettings, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..core.config import settings
from ..core.logger import get_logger
from ..database.repository import DatabaseRepository
from ..database.models import IndexedFileModel, IndexingStateModel
from ..database.connection import session_scope
from .icons import get_icon
from .theme_manager import theme_manager, DARK_TOKENS, LIGHT_TOKENS
from .fonts import (
    get_font_for_text,
    get_title_font,
    get_section_header_font,
    get_body_font,
    get_secondary_font,
    get_caption_font,
)

logger = get_logger("ui.settings_panel")


class SettingsPanel(QFrame):
    """Right-docked slide-in settings panel strictly adhering to user specifications:
    - Right edge docked (width 320px, border-left 1px solid border).
    - Fully wired to real app state & QSettings.
    - Pinned bottom 'Apply' button with live preview and revert on close.
    - Includes Account, Theme, Download path, Cache, Concurrency, Language, Tools, and About.
    """

    close_requested = Signal()
    theme_changed = Signal(str)
    language_changed = Signal(str)
    sign_out_requested = Signal()
    logout_requested = Signal()
    open_indexing_requested = Signal()
    reindex_requested = Signal()

    def __init__(self, repo: Optional[DatabaseRepository] = None, parent=None):
        super().__init__(parent)
        self.repo = repo or DatabaseRepository()
        self.setFixedWidth(320)
        self.setObjectName("settingsPanel")

        self.app_settings = QSettings("TelegramFileExplorer", "AppSettings")
        
        # Saved state for revert-on-close functionality
        self._saved_theme = theme_manager.current_theme_mode
        self._saved_language = theme_manager.get_current_language()
        self._pending_theme = self._saved_theme
        self._pending_language = self._saved_language
        self._pending_download_dir = str(settings.download_dir)
        self._pending_concurrency = getattr(settings, "max_concurrent_downloads", 3)

        self._init_ui()
        self._refresh_cache_size()
        theme_manager.theme_changed.connect(self._on_theme_changed)

    def _init_ui(self):
        tokens = theme_manager.get_active_tokens()
        self.setStyleSheet(
            f"""
            QFrame#settingsPanel {{
                background-color: {tokens['bg_surface']};
                border-left: 1px solid {tokens['border']};
            }}
            """
        )

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Header Row: Title "Settings" + Close 'x' button
        header_row = QHBoxLayout()
        self.header_title = QLabel("Settings")
        self.header_title.setFont(get_title_font("Settings"))
        self.header_title.setStyleSheet(f"color: {tokens['text_primary']};")
        header_row.addWidget(self.header_title)

        header_row.addStretch()

        self.btn_close = QPushButton()
        self.btn_close.setIcon(get_icon("x", color=tokens["text_secondary"], size=16))
        self.btn_close.setFixedSize(30, 30)
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.setStyleSheet("background: transparent; border: none; border-radius: 6px;")
        self.btn_close.setToolTip("Close Settings (Esc)")
        self.btn_close.clicked.connect(self._on_cancel_close)
        header_row.addWidget(self.btn_close)

        main_layout.addLayout(header_row)

        # Scrollable settings content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        self.c_layout = QVBoxLayout(scroll_content)
        self.c_layout.setContentsMargins(0, 0, 0, 0)
        self.c_layout.setSpacing(18)

        # --- Section 1: Account ---
        account_box = QVBoxLayout()
        account_box.setSpacing(8)

        self.account_header = QLabel("Account")
        self.account_header.setFont(get_section_header_font("Account"))
        self.account_header.setStyleSheet(f"color: {tokens['text_secondary']};")
        account_box.addWidget(self.account_header)

        self.user_card = QFrame()
        self.user_card.setStyleSheet(
            f"""
            QFrame {{
                background-color: {tokens['bg_surface_2']};
                border: 1px solid {tokens['border']};
                border-radius: 8px;
                padding: 10px;
            }}
            """
        )
        uc_layout = QHBoxLayout(self.user_card)
        uc_layout.setContentsMargins(10, 8, 10, 8)
        uc_layout.setSpacing(10)

        self.user_avatar_label = QLabel()
        self.user_avatar_label.setFixedSize(36, 36)
        from .chat_list import generate_avatar_pixmap
        self.user_avatar_label.setPixmap(generate_avatar_pixmap(None, 36, custom_initial="W"))
        uc_layout.addWidget(self.user_avatar_label)

        user_info = QVBoxLayout()
        user_info.setSpacing(2)
        self.lbl_user_display_name = QLabel("Telegram User")
        self.lbl_user_display_name.setFont(get_body_font("User"))
        self.lbl_user_display_name.setStyleSheet(f"color: {tokens['text_primary']}; font-weight: 500;")
        user_info.addWidget(self.lbl_user_display_name)

        self.lbl_user_status = QLabel("Connected via MTProto")
        self.lbl_user_status.setFont(get_caption_font("Connected"))
        self.lbl_user_status.setStyleSheet(f"color: {tokens['success']};")
        user_info.addWidget(self.lbl_user_status)
        uc_layout.addLayout(user_info)
        uc_layout.addStretch()

        account_box.addWidget(self.user_card)

        self.btn_sign_out = QPushButton("Sign Out")
        self.btn_sign_out.setObjectName("secondaryButton")
        self.btn_sign_out.setFixedHeight(34)
        self.btn_sign_out.setFont(get_body_font("Sign Out"))
        self.btn_sign_out.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_sign_out.setStyleSheet(f"color: {tokens['danger']}; border-color: {tokens['border']};")
        self.btn_sign_out.clicked.connect(self._on_sign_out_clicked)
        account_box.addWidget(self.btn_sign_out)

        self.c_layout.addLayout(account_box)

        # --- Section 2: Theme (System / Light / Dark) ---
        theme_box = QVBoxLayout()
        theme_box.setSpacing(8)

        self.theme_label = QLabel("Theme")
        self.theme_label.setFont(get_section_header_font("Theme"))
        self.theme_label.setStyleSheet(f"color: {tokens['text_secondary']};")
        theme_box.addWidget(self.theme_label)

        theme_pills = QHBoxLayout()
        theme_pills.setSpacing(4)

        self.btn_theme_system = QPushButton("System")
        self.btn_theme_light = QPushButton("Light")
        self.btn_theme_dark = QPushButton("Dark")

        self.theme_buttons = [
            (self.btn_theme_system, "system"),
            (self.btn_theme_light, "light"),
            (self.btn_theme_dark, "dark"),
        ]

        active_mode = self._pending_theme
        for btn, mode in self.theme_buttons:
            btn.setObjectName("themePillButton")
            btn.setCheckable(True)
            btn.setChecked(mode == active_mode)
            btn.setFont(get_body_font(btn.text()))
            btn.setFixedHeight(32)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, m=mode: self._on_theme_preview(m))
            theme_pills.addWidget(btn)

        theme_box.addLayout(theme_pills)
        self.c_layout.addLayout(theme_box)

        # --- Section 3: Download Location ---
        dl_box = QVBoxLayout()
        dl_box.setSpacing(8)

        self.dl_label = QLabel("Download Location")
        self.dl_label.setFont(get_section_header_font("Download Location"))
        self.dl_label.setStyleSheet(f"color: {tokens['text_secondary']};")
        dl_box.addWidget(self.dl_label)

        dl_row = QHBoxLayout()
        dl_row.setSpacing(6)

        self.dl_path_input = QLineEdit(self._pending_download_dir)
        self.dl_path_input.setReadOnly(True)
        self.dl_path_input.setFixedHeight(34)
        self.dl_path_input.setFont(get_secondary_font())
        self.dl_path_input.setStyleSheet(
            f"""
            QLineEdit {{
                background-color: {tokens['bg_base']};
                border: 1px solid {tokens['border']};
                border-radius: 6px;
                color: {tokens['text_primary']};
                padding: 0 10px;
            }}
            """
        )
        dl_row.addWidget(self.dl_path_input)

        self.btn_browse = QPushButton()
        self.btn_browse.setIcon(get_icon("folder", color=tokens["text_secondary"], size=16))
        self.btn_browse.setFixedSize(34, 34)
        self.btn_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_browse.setObjectName("secondaryButton")
        self.btn_browse.setToolTip("Browse folder")
        self.btn_browse.clicked.connect(self._on_browse_download_path)
        dl_row.addWidget(self.btn_browse)

        dl_box.addLayout(dl_row)
        self.c_layout.addLayout(dl_box)

        # --- Section 4: Cache & Storage ---
        cache_box = QVBoxLayout()
        cache_box.setSpacing(8)

        self.cache_size_label = QLabel("Cache (الذاكرة المؤقتة): 0 MB")
        self.cache_size_label.setFont(get_section_header_font())
        self.cache_size_label.setStyleSheet(f"color: {tokens['text_secondary']};")
        cache_box.addWidget(self.cache_size_label)

        self.btn_clear_cache = QPushButton("Clear Cache")
        self.btn_clear_cache.setObjectName("secondaryButton")
        self.btn_clear_cache.setFixedHeight(34)
        self.btn_clear_cache.setFont(get_body_font("Clear Cache"))
        self.btn_clear_cache.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear_cache.clicked.connect(self._on_clear_cache)
        cache_box.addWidget(self.btn_clear_cache)

        self.c_layout.addLayout(cache_box)

        # --- Section 5: Max Concurrent Downloads (Stepper) ---
        concurrent_box = QVBoxLayout()
        concurrent_box.setSpacing(8)

        self.concurrent_label = QLabel("Concurrent Downloads")
        self.concurrent_label.setFont(get_section_header_font("Concurrent Downloads"))
        self.concurrent_label.setStyleSheet(f"color: {tokens['text_secondary']};")
        concurrent_box.addWidget(self.concurrent_label)

        stepper_row = QHBoxLayout()
        stepper_row.setSpacing(8)

        self.btn_minus = QPushButton("-")
        self.btn_minus.setFixedSize(32, 32)
        self.btn_minus.setFont(QFont("Inter", 13, QFont.Bold))
        self.btn_minus.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_minus.setObjectName("secondaryButton")
        self.btn_minus.clicked.connect(self._decrement_concurrent)
        stepper_row.addWidget(self.btn_minus)

        self.concurrent_val_label = QLabel(str(self._pending_concurrency))
        self.concurrent_val_label.setFixedWidth(40)
        self.concurrent_val_label.setAlignment(Qt.AlignCenter)
        self.concurrent_val_label.setFont(QFont("Inter", 14, QFont.Bold))
        self.concurrent_val_label.setStyleSheet(f"color: {tokens['text_primary']};")
        stepper_row.addWidget(self.concurrent_val_label)

        self.btn_plus = QPushButton("+")
        self.btn_plus.setFixedSize(32, 32)
        self.btn_plus.setFont(QFont("Inter", 13, QFont.Bold))
        self.btn_plus.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_plus.setObjectName("secondaryButton")
        self.btn_plus.clicked.connect(self._increment_concurrent)
        stepper_row.addWidget(self.btn_plus)

        stepper_row.addStretch()
        concurrent_box.addLayout(stepper_row)
        self.c_layout.addLayout(concurrent_box)

        # --- Section 6: Language (Default English / العربية) ---
        lang_box = QVBoxLayout()
        lang_box.setSpacing(8)

        self.lang_label = QLabel("Language")
        self.lang_label.setFont(get_section_header_font("Language"))
        self.lang_label.setStyleSheet(f"color: {tokens['text_secondary']};")
        lang_box.addWidget(self.lang_label)

        lang_pills = QHBoxLayout()
        lang_pills.setSpacing(4)

        self.btn_lang_en = QPushButton("English")
        self.btn_lang_ar = QPushButton("العربية")

        self.btn_lang_en.setObjectName("themePillButton")
        self.btn_lang_ar.setObjectName("themePillButton")
        self.btn_lang_en.setCheckable(True)
        self.btn_lang_ar.setCheckable(True)
        self.btn_lang_en.setChecked(self._pending_language == "en")
        self.btn_lang_ar.setChecked(self._pending_language == "ar")
        self.btn_lang_en.setFixedHeight(32)
        self.btn_lang_ar.setFixedHeight(32)
        self.btn_lang_en.setFont(get_body_font("English"))
        self.btn_lang_ar.setFont(get_body_font("العربية"))
        self.btn_lang_en.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_lang_ar.setCursor(Qt.CursorShape.PointingHandCursor)

        self.btn_lang_en.clicked.connect(lambda: self._on_language_preview("en"))
        self.btn_lang_ar.clicked.connect(lambda: self._on_language_preview("ar"))

        lang_pills.addWidget(self.btn_lang_en)
        lang_pills.addWidget(self.btn_lang_ar)
        lang_box.addLayout(lang_pills)
        self.c_layout.addLayout(lang_box)

        # --- Section 7: Tools / Advanced ---
        tools_box = QVBoxLayout()
        tools_box.setSpacing(8)

        self.tools_label = QLabel("Tools")
        self.tools_label.setFont(get_section_header_font("Tools"))
        self.tools_label.setStyleSheet(f"color: {tokens['text_secondary']};")
        tools_box.addWidget(self.tools_label)

        self.btn_indexing_manager = QPushButton("Indexing Manager")
        self.btn_indexing_manager.setObjectName("secondaryButton")
        self.btn_indexing_manager.setFixedHeight(34)
        self.btn_indexing_manager.setFont(get_body_font("Indexing Manager"))
        self.btn_indexing_manager.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_indexing_manager.clicked.connect(self.open_indexing_requested.emit)
        tools_box.addWidget(self.btn_indexing_manager)

        self.btn_reindex = QPushButton("Re-Index Dialogues")
        self.btn_reindex.setObjectName("secondaryButton")
        self.btn_reindex.setFixedHeight(34)
        self.btn_reindex.setFont(get_body_font("Re-Index Dialogues"))
        self.btn_reindex.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reindex.clicked.connect(self.reindex_requested.emit)
        tools_box.addWidget(self.btn_reindex)

        self.c_layout.addLayout(tools_box)

        # --- Section 8: About Section ---
        about_box = QVBoxLayout()
        about_box.setSpacing(4)

        about_title = QLabel("Telegram File Explorer")
        about_title.setFont(get_section_header_font("Telegram File Explorer"))
        about_title.setStyleSheet(f"color: {tokens['text_primary']};")
        about_box.addWidget(about_title)

        version_label = QLabel(f"Version {settings.app_version}")
        version_label.setFont(get_caption_font())
        version_label.setStyleSheet(f"color: {tokens['text_tertiary']};")
        about_box.addWidget(version_label)

        desc_label = QLabel("Local-first Telegram MTProto desktop file explorer.")
        desc_label.setFont(get_caption_font())
        desc_label.setStyleSheet(f"color: {tokens['text_secondary']};")
        desc_label.setWordWrap(True)
        about_box.addWidget(desc_label)

        self.c_layout.addLayout(about_box)
        self.c_layout.addStretch()

        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

        # --- Pinned Bottom "Apply" Button ---
        bottom_box = QVBoxLayout()
        bottom_box.setContentsMargins(0, 8, 0, 0)

        self.btn_apply = QPushButton("Apply")
        self.btn_apply.setObjectName("primaryButton")
        self.btn_apply.setFixedHeight(38)
        self.btn_apply.setFont(QFont("Inter", 13, QFont.Bold))
        self.btn_apply.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_apply.clicked.connect(self._on_apply_clicked)
        bottom_box.addWidget(self.btn_apply)

        main_layout.addLayout(bottom_box)

        self._update_localized_ui()

    def set_user_info(self, name: str, username: str = ""):
        self.lbl_user_display_name.setText(name or "Telegram User")
        if username:
            self.lbl_user_status.setText(f"@{username} · Connected")
        else:
            self.lbl_user_status.setText("Connected via MTProto")

    def _on_theme_changed(self, tokens: dict):
        self.setStyleSheet(
            f"""
            QFrame#settingsPanel {{
                background-color: {tokens['bg_surface']};
                border-left: 1px solid {tokens['border']};
            }}
            """
        )
        self.btn_close.setIcon(get_icon("x", color=tokens["text_secondary"], size=16))
        self.btn_browse.setIcon(get_icon("folder", color=tokens["text_secondary"], size=16))

    def _on_theme_preview(self, mode: str):
        self._pending_theme = mode
        for btn, m in self.theme_buttons:
            btn.setChecked(m == mode)
        # Live preview theme
        theme_manager.set_theme(mode)

    def _on_theme_pill_clicked(self, mode: str):
        self._on_theme_preview(mode)

    def _on_language_preview(self, lang: str):
        self._pending_language = lang
        self.btn_lang_en.setChecked(lang == "en")
        self.btn_lang_ar.setChecked(lang == "ar")
        self._update_localized_ui()
        self.language_changed.emit(lang)

    def _update_localized_ui(self):
        is_ar = (self._pending_language == "ar")
        if is_ar:
            self.header_title.setText("الإعدادات")
            self.account_header.setText("الحساب")
            self.btn_sign_out.setText("تسجيل الخروج")
            self.theme_label.setText("الثيم")
            self.btn_theme_system.setText("النظام")
            self.btn_theme_light.setText("فاتح")
            self.btn_theme_dark.setText("غامق")
            self.dl_label.setText("مسار التحميل")
            self.cache_size_label.setText(self.cache_size_label.text().replace("Cache:", "الذاكرة المؤقتة:"))
            self.btn_clear_cache.setText("مسح الذاكرة المؤقتة")
            self.concurrent_label.setText("التحميلات المتزامنة")
            self.lang_label.setText("اللغة")
            self.tools_label.setText("الأدوات")
            self.btn_indexing_manager.setText("إدارة الفهرسة")
            self.btn_reindex.setText("إعادة فهرسة المحادثات")
            self.btn_apply.setText("تطبيق")
        else:
            self.header_title.setText("Settings")
            self.account_header.setText("Account")
            self.btn_sign_out.setText("Sign Out")
            self.theme_label.setText("Theme")
            self.btn_theme_system.setText("System")
            self.btn_theme_light.setText("Light")
            self.btn_theme_dark.setText("Dark")
            self.dl_label.setText("Download Location")
            self.cache_size_label.setText(self.cache_size_label.text().replace("الذاكرة المؤقتة:", "Cache:"))
            self.btn_clear_cache.setText("Clear Cache")
            self.concurrent_label.setText("Concurrent Downloads")
            self.lang_label.setText("Language")
            self.tools_label.setText("Tools")
            self.btn_indexing_manager.setText("Indexing Manager")
            self.btn_reindex.setText("Re-Index Dialogues")
            self.btn_apply.setText("Apply")

    def _on_browse_download_path(self):
        new_dir = QFileDialog.getExistingDirectory(
            self,
            "Select Download Directory",
            self._pending_download_dir,
        )
        if new_dir:
            self._pending_download_dir = new_dir
            self.dl_path_input.setText(new_dir)

    def _refresh_cache_size(self):
        cache_dir = settings.data_dir / "cache"
        total_bytes = 0
        if cache_dir.exists():
            for f in cache_dir.rglob("*"):
                if f.is_file():
                    total_bytes += f.stat().st_size
        mb = total_bytes / (1024 * 1024)
        is_ar = (self._pending_language == "ar")
        prefix = "الذاكرة المؤقتة:" if is_ar else "Cache (الذاكرة المؤقتة):"
        if mb >= 1024:
            self.cache_size_label.setText(f"{prefix} {mb / 1024:.1f} GB")
        else:
            self.cache_size_label.setText(f"{prefix} {mb:.1f} MB")

    def _on_clear_cache(self):
        confirm = QMessageBox.question(
            self,
            "Clear Cache",
            "Are you sure you want to clear all cached thumbnails?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            cache_dir = settings.data_dir / "cache"
            if cache_dir.exists():
                shutil.rmtree(cache_dir, ignore_errors=True)
                cache_dir.mkdir(parents=True, exist_ok=True)
            from ..services.image_loader import thumbnail_manager
            thumbnail_manager.clear_memory_cache()
            self._refresh_cache_size()

    def _increment_concurrent(self):
        if self._pending_concurrency < 8:
            self._pending_concurrency += 1
            self.concurrent_val_label.setText(str(self._pending_concurrency))

    def _decrement_concurrent(self):
        if self._pending_concurrency > 1:
            self._pending_concurrency -= 1
            self.concurrent_val_label.setText(str(self._pending_concurrency))

    def _on_sign_out_clicked(self):
        confirm = QMessageBox.question(
            self,
            "Sign Out",
            "Are you sure you want to sign out of Telegram?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            self.sign_out_requested.emit()
            self.logout_requested.emit()

    def _on_apply_clicked(self):
        """Commit pending changes to QSettings and real application state."""
        # 1. Apply & Persist Theme
        self._saved_theme = self._pending_theme
        theme_manager.set_theme(self._saved_theme)

        # 2. Apply & Persist Language
        self._saved_language = self._pending_language
        theme_manager.set_language(self._saved_language)

        # 3. Apply & Persist Download Dir
        settings.download_dir = Path(self._pending_download_dir)
        self.app_settings.setValue("download_dir", self._pending_download_dir)

        # 4. Apply & Persist Concurrency
        settings.max_concurrent_downloads = self._pending_concurrency
        self.app_settings.setValue("max_concurrent_downloads", self._pending_concurrency)

        # 5. Non-blocking temporary confirmation
        orig_text = self.btn_apply.text()
        self.btn_apply.setText("Applied")
        self.btn_apply.setEnabled(False)

        def restore():
            self.btn_apply.setText(orig_text)
            self.btn_apply.setEnabled(True)

        QTimer.singleShot(1500, restore)
        logger.info("Settings applied and saved successfully.")

    def _on_cancel_close(self):
        """Revert unapplied live previews if closed without applying."""
        if self._pending_theme != self._saved_theme:
            self._pending_theme = self._saved_theme
            theme_manager.set_theme(self._saved_theme)

        if self._pending_language != self._saved_language:
            self._pending_language = self._saved_language
            theme_manager.set_language(self._saved_language)
            self._update_localized_ui()

        self.close_requested.emit()
