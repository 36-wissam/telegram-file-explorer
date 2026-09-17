"""Slide-in / docked settings panel matching right-side design specifications."""

import shutil
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QSettings,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..core.config import settings
from ..core.logger import get_logger
from ..database.connection import session_scope
from ..database.models import IndexedFileModel, IndexingStateModel
from ..database.repository import DatabaseRepository
from .animated_controls import AnimatedHoverButton, AnimatedSegmentedControl
from .fonts import (
    get_body_font,
    get_caption_font,
    get_font_for_text,
    get_section_header_font,
    get_secondary_font,
    get_title_font,
)
from .i18n import tr
from .icons import get_icon
from .media_card import format_bytes
from .theme_manager import DARK_TOKENS, LIGHT_TOKENS, theme_manager

logger = get_logger("ui.settings_panel")


def _create_section_card(tokens: Optional[dict] = None) -> QFrame:
    """Create a bounded section card conforming to the 4px design scale."""
    card = QFrame()
    card.setObjectName("settingsCard")
    card.setMinimumWidth(0)
    return card


class SettingsPanel(QFrame):
    """Right-docked slide-in settings panel with visual card hierarchy and smooth controls."""

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
        self.setObjectName("settingsPanel")
        self.setMinimumWidth(280)
        self.setMaximumWidth(340)
        self.resize(320, 600)

        self.app_settings = QSettings("TelegramFileExplorer", "AppSettings")
        self._cached_cache_mb: float = 0.0

        # Saved state for revert-on-close functionality
        self._saved_theme = theme_manager.current_theme_mode
        self._saved_language = theme_manager.get_current_language()
        self._pending_theme = self._saved_theme
        self._pending_language = self._saved_language
        self._pending_download_dir = str(settings.download_dir)
        self._pending_concurrency = getattr(settings, "max_concurrent_downloads", 3)

        self._init_ui()
        self._refresh_cache_size(scan_disk=True)
        theme_manager.theme_changed.connect(self._on_theme_changed)
        theme_manager.language_changed.connect(self._on_language_changed)

    def sizeHint(self) -> QSize:
        return QSize(320, 600)

    def _init_ui(self):
        tokens = theme_manager.get_active_tokens()
        self._apply_panel_style(tokens)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 12, 10, 12)
        main_layout.setSpacing(10)

        # Header Row: Title "Settings" + Close 'x' button
        header_row = QHBoxLayout()
        self.header_title = QLabel("Settings")
        self.header_title.setObjectName("settingsTitle")
        self.header_title.setFont(get_title_font("Settings"))
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
        self.c_layout.setSpacing(12)  # 12px gap between section groups

        # ==========================================
        # 1. SECTION: Account
        # ==========================================
        account_section = QVBoxLayout()
        account_section.setSpacing(6)

        self.account_header = QLabel("Account")
        self.account_header.setObjectName("settingsHeader")
        self.account_header.setFont(get_section_header_font("Account"))
        account_section.addWidget(self.account_header)

        self.account_card = _create_section_card(tokens)
        card_layout = QVBoxLayout(self.account_card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(10)

        # Top row: Avatar + Name & Status
        user_row = QHBoxLayout()
        user_row.setSpacing(12)

        self.user_avatar_label = QLabel()
        self.user_avatar_label.setFixedSize(36, 36)
        from .chat_list import generate_avatar_pixmap
        self.user_avatar_label.setPixmap(generate_avatar_pixmap(None, 36, custom_initial="W"))
        user_row.addWidget(self.user_avatar_label)

        user_info = QVBoxLayout()
        user_info.setSpacing(2)
        self.lbl_user_display_name = QLabel("Telegram User")
        self.lbl_user_display_name.setObjectName("settingsUserName")
        self.lbl_user_display_name.setFont(get_body_font("User"))
        user_info.addWidget(self.lbl_user_display_name)

        status_row = QHBoxLayout()
        status_row.setSpacing(4)
        self.lbl_username = QLabel("@user")
        self.lbl_username.setObjectName("settingsUserHandle")
        self.lbl_username.setFont(get_caption_font())

        self.lbl_status_badge = QLabel("Connected")
        self.lbl_status_badge.setFont(get_caption_font())
        self.lbl_status_badge.setStyleSheet(f"color: {tokens['success']}; font-weight: 500;")

        status_row.addWidget(self.lbl_username)
        status_row.addWidget(self.lbl_status_badge)
        status_row.addStretch()

        user_info.addLayout(status_row)
        user_row.addLayout(user_info)
        user_row.addStretch()
        card_layout.addLayout(user_row)

        # Bottom row: Ghost Danger "Sign Out" Button
        self.btn_sign_out = AnimatedHoverButton(
            "Sign Out",
            is_ghost=True,
            ghost_color=tokens["danger"],
            border_radius=6,
        )
        self.btn_sign_out.setFixedHeight(34)
        self.btn_sign_out.setFont(get_body_font("Sign Out"))
        self.btn_sign_out.clicked.connect(self._on_sign_out_clicked)
        card_layout.addWidget(self.btn_sign_out)

        account_section.addWidget(self.account_card)
        self.c_layout.addLayout(account_section)

        # Compatibility reference for legacy tests
        self.lbl_user_status = self.lbl_status_badge

        # ==========================================
        # 2. SECTION: Theme
        # ==========================================
        theme_section = QVBoxLayout()
        theme_section.setSpacing(6)

        self.theme_label = QLabel("Theme")
        self.theme_label.setObjectName("settingsHeader")
        self.theme_label.setFont(get_section_header_font("Theme"))
        theme_section.addWidget(self.theme_label)

        self.theme_card = _create_section_card(tokens)
        theme_card_layout = QVBoxLayout(self.theme_card)
        theme_card_layout.setContentsMargins(10, 10, 10, 10)

        theme_options = [("System", "system"), ("Light", "light"), ("Dark", "dark")]
        self.theme_segmented = AnimatedSegmentedControl(theme_options, self._pending_theme)
        self.theme_segmented.valueChanged.connect(self._on_theme_preview)
        theme_card_layout.addWidget(self.theme_segmented)

        # Compatibility bindings for tests
        self.btn_theme_system = self.theme_segmented.buttons[0]
        self.btn_theme_light = self.theme_segmented.buttons[1]
        self.btn_theme_dark = self.theme_segmented.buttons[2]
        self.theme_buttons = [
            (self.btn_theme_system, "system"),
            (self.btn_theme_light, "light"),
            (self.btn_theme_dark, "dark"),
        ]

        theme_section.addWidget(self.theme_card)
        self.c_layout.addLayout(theme_section)

        # ==========================================
        # 3. SECTION: Download Location
        # ==========================================
        dl_section = QVBoxLayout()
        dl_section.setSpacing(6)

        self.dl_label = QLabel("Download Location")
        self.dl_label.setObjectName("settingsHeader")
        self.dl_label.setFont(get_section_header_font("Download Location"))
        dl_section.addWidget(self.dl_label)

        self.dl_card = _create_section_card(tokens)
        dl_card_layout = QHBoxLayout(self.dl_card)
        dl_card_layout.setContentsMargins(10, 10, 10, 10)
        dl_card_layout.setSpacing(8)

        self.dl_path_input = QLineEdit(self._pending_download_dir)
        self.dl_path_input.setObjectName("dlPathInput")
        self.dl_path_input.setReadOnly(True)
        self.dl_path_input.setFixedHeight(34)
        self.dl_path_input.setFont(get_secondary_font())
        self.dl_path_input.setMinimumWidth(0)
        self.dl_path_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        dl_card_layout.addWidget(self.dl_path_input)

        self.btn_browse = AnimatedHoverButton(
            icon=get_icon("folder", color=tokens["text_secondary"], size=16),
            border_radius=6,
        )
        self.btn_browse.setFixedSize(34, 34)
        self.btn_browse.setToolTip("Browse folder")
        self.btn_browse.clicked.connect(self._on_browse_download_path)
        dl_card_layout.addWidget(self.btn_browse)

        dl_section.addWidget(self.dl_card)
        self.c_layout.addLayout(dl_section)

        # ==========================================
        # 4. SECTION: Cache & Storage
        # ==========================================
        cache_section = QVBoxLayout()
        cache_section.setSpacing(6)

        self.cache_header = QLabel("Cache & Storage")
        self.cache_header.setObjectName("settingsHeader")
        self.cache_header.setFont(get_section_header_font("Cache"))
        cache_section.addWidget(self.cache_header)

        self.cache_card = _create_section_card(tokens)
        cache_card_layout = QHBoxLayout(self.cache_card)
        cache_card_layout.setContentsMargins(10, 8, 10, 8)
        cache_card_layout.setSpacing(6)

        self.cache_size_label = QLabel("Cache (الذاكرة المؤقتة): 0 MB")
        self.cache_size_label.setObjectName("cacheSizeLabel")
        self.cache_size_label.setFont(get_caption_font())
        self.cache_size_label.setMinimumWidth(0)
        self.cache_size_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.cache_size_label.setWordWrap(False)
        cache_card_layout.addWidget(self.cache_size_label)

        self.btn_clear_cache = AnimatedHoverButton("Clear Cache", border_radius=6)
        self.btn_clear_cache.setFixedHeight(28)
        self.btn_clear_cache.setMinimumWidth(0)
        self.btn_clear_cache.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.btn_clear_cache.setFont(get_caption_font())
        self.btn_clear_cache.clicked.connect(self._on_clear_cache)
        cache_card_layout.addWidget(self.btn_clear_cache)

        cache_section.addWidget(self.cache_card)
        self.c_layout.addLayout(cache_section)

        # ==========================================
        # 5. SECTION: Max Concurrent Downloads (Stepper)
        # ==========================================
        concurrent_section = QVBoxLayout()
        concurrent_section.setSpacing(6)

        self.concurrent_header = QLabel("Performance")
        self.concurrent_header.setObjectName("settingsHeader")
        self.concurrent_header.setFont(get_section_header_font("Performance"))
        concurrent_section.addWidget(self.concurrent_header)

        self.concurrent_card = _create_section_card(tokens)
        concurrent_card_layout = QHBoxLayout(self.concurrent_card)
        concurrent_card_layout.setContentsMargins(10, 8, 10, 8)
        concurrent_card_layout.setSpacing(6)

        self.concurrent_label = QLabel("Concurrent Downloads")
        self.concurrent_label.setObjectName("concurrentLabel")
        self.concurrent_label.setFont(get_secondary_font())
        self.concurrent_label.setMinimumWidth(0)
        self.concurrent_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        concurrent_card_layout.addWidget(self.concurrent_label)

        # Stepper control pill: [-]  3  [+]
        self.stepper_frame = QFrame()
        self.stepper_frame.setObjectName("stepperFrame")
        self.stepper_frame.setFixedSize(76, 28)
        stepper_layout = QHBoxLayout(self.stepper_frame)
        stepper_layout.setContentsMargins(1, 1, 1, 1)
        stepper_layout.setSpacing(0)

        self.btn_minus = QPushButton("-")
        self.btn_minus.setObjectName("stepperBtn")
        self.btn_minus.setFixedSize(22, 24)
        self.btn_minus.setFont(QFont("Inter", 12, QFont.Bold))
        self.btn_minus.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_minus.clicked.connect(self._decrement_concurrent)
        stepper_layout.addWidget(self.btn_minus)

        self.concurrent_val_label = QLabel(str(self._pending_concurrency))
        self.concurrent_val_label.setObjectName("stepperVal")
        self.concurrent_val_label.setFixedWidth(22)
        self.concurrent_val_label.setAlignment(Qt.AlignCenter)
        self.concurrent_val_label.setFont(QFont("Inter", 12, QFont.Bold))
        stepper_layout.addWidget(self.concurrent_val_label)

        self.btn_plus = QPushButton("+")
        self.btn_plus.setObjectName("stepperBtn")
        self.btn_plus.setFixedSize(22, 24)
        self.btn_plus.setFont(QFont("Inter", 12, QFont.Bold))
        self.btn_plus.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_plus.clicked.connect(self._increment_concurrent)
        stepper_layout.addWidget(self.btn_plus)

        concurrent_card_layout.addWidget(self.stepper_frame)
        concurrent_section.addWidget(self.concurrent_card)
        self.c_layout.addLayout(concurrent_section)

        # ==========================================
        # 6. SECTION: Language
        # ==========================================
        lang_section = QVBoxLayout()
        lang_section.setSpacing(6)

        self.lang_label = QLabel("Language")
        self.lang_label.setObjectName("settingsHeader")
        self.lang_label.setFont(get_section_header_font("Language"))
        lang_section.addWidget(self.lang_label)

        self.lang_card = _create_section_card(tokens)
        lang_card_layout = QVBoxLayout(self.lang_card)
        lang_card_layout.setContentsMargins(10, 10, 10, 10)

        lang_options = [("English", "en"), ("العربية", "ar")]
        self.lang_segmented = AnimatedSegmentedControl(lang_options, self._pending_language)
        self.lang_segmented.valueChanged.connect(self._on_language_preview)
        lang_card_layout.addWidget(self.lang_segmented)

        self.btn_lang_en = self.lang_segmented.buttons[0]
        self.btn_lang_ar = self.lang_segmented.buttons[1]

        lang_section.addWidget(self.lang_card)
        self.c_layout.addLayout(lang_section)

        # ==========================================
        # 7. SECTION: Tools
        # ==========================================
        tools_section = QVBoxLayout()
        tools_section.setSpacing(6)

        self.tools_label = QLabel("Tools")
        self.tools_label.setObjectName("settingsHeader")
        self.tools_label.setFont(get_section_header_font("Tools"))
        tools_section.addWidget(self.tools_label)

        self.tools_card = _create_section_card(tokens)
        tools_card_layout = QVBoxLayout(self.tools_card)
        tools_card_layout.setContentsMargins(8, 8, 8, 8)
        tools_card_layout.setSpacing(6)

        self.btn_indexing_manager = AnimatedHoverButton(
            "Indexing Manager",
            icon=get_icon("hard_drive", color=tokens["text_secondary"], size=16),
            border_radius=6,
        )
        self.btn_indexing_manager.setFixedHeight(36)
        self.btn_indexing_manager.setFont(get_body_font("Indexing Manager"))
        self.btn_indexing_manager.setStyleSheet("text-align: left;")
        self.btn_indexing_manager.clicked.connect(self.open_indexing_requested.emit)
        tools_card_layout.addWidget(self.btn_indexing_manager)

        self.btn_reindex = AnimatedHoverButton(
            "Re-Index Dialogues",
            icon=get_icon("refresh_cw", color=tokens["text_secondary"], size=16),
            border_radius=6,
        )
        self.btn_reindex.setFixedHeight(36)
        self.btn_reindex.setFont(get_body_font("Re-Index Dialogues"))
        self.btn_reindex.setStyleSheet("text-align: left;")
        self.btn_reindex.clicked.connect(self.reindex_requested.emit)
        tools_card_layout.addWidget(self.btn_reindex)

        tools_section.addWidget(self.tools_card)
        self.c_layout.addLayout(tools_section)

        # ==========================================
        # 8. SECTION: About
        # ==========================================
        about_section = QVBoxLayout()
        about_section.setSpacing(6)

        self.about_header = QLabel("About")
        self.about_header.setObjectName("settingsHeader")
        self.about_header.setFont(get_section_header_font("About"))
        about_section.addWidget(self.about_header)

        self.about_card = _create_section_card(tokens)
        about_card_layout = QVBoxLayout(self.about_card)
        about_card_layout.setContentsMargins(12, 12, 12, 12)
        about_card_layout.setSpacing(4)

        self.about_title = QLabel("Telegram File Explorer")
        self.about_title.setObjectName("aboutTitle")
        self.about_title.setFont(get_body_font("Telegram File Explorer"))
        about_card_layout.addWidget(self.about_title)

        self.version_label = QLabel(f"Version {settings.app_version}")
        self.version_label.setObjectName("aboutMeta")
        self.version_label.setFont(get_caption_font())
        about_card_layout.addWidget(self.version_label)

        self.desc_label = QLabel("Local-first Telegram MTProto desktop file explorer.")
        self.desc_label.setObjectName("aboutDesc")
        self.desc_label.setFont(get_caption_font())
        self.desc_label.setWordWrap(True)
        about_card_layout.addWidget(self.desc_label)

        about_section.addWidget(self.about_card)
        self.c_layout.addLayout(about_section)

        self.c_layout.addStretch()

        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

        # Pinned Bottom "Apply" Button
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

    def _apply_panel_style(self, tokens: dict):
        pass  # Styled via global QSS QFrame#settingsPanel

    def set_user_info(self, name: str, username: str = ""):
        self.lbl_user_display_name.setText(name or "Telegram User")
        if username:
            self.lbl_username.setText(f"@{username} ·")
        else:
            self.lbl_username.setText("")
        self.lbl_status_badge.setText("Connected")

    def _on_theme_changed(self, tokens: dict):
        self.btn_close.setIcon(get_icon("x", color=tokens["text_secondary"], size=16))
        self.btn_sign_out.ghost_color = tokens["danger"]
        self.btn_sign_out.update()
        self.btn_browse.setIcon(get_icon("folder", color=tokens["text_secondary"], size=16))
        self.btn_indexing_manager.setIcon(get_icon("hard_drive", color=tokens["text_secondary"], size=16))
        self.btn_reindex.setIcon(get_icon("refresh_cw", color=tokens["text_secondary"], size=16))
        if hasattr(self, "theme_segmented"):
            self.theme_segmented._update_button_visuals()
        if hasattr(self, "lang_segmented"):
            self.lang_segmented._update_button_visuals()

    def _on_theme_preview(self, mode: str):
        self._pending_theme = mode
        self.theme_segmented.set_value(mode)
        theme_manager.set_theme(mode, save=False)

    def _on_theme_pill_clicked(self, mode: str):
        self._on_theme_preview(mode)

    def _on_language_preview(self, lang: str):
        self._pending_language = lang
        self.lang_segmented.set_value(lang)
        self._update_localized_ui()
        self.language_changed.emit(lang)

    def _on_language_changed(self, lang: str):
        self._pending_language = lang
        self.lang_segmented.set_value(lang)
        self._update_localized_ui()

    def _update_localized_ui(self):
        lang = self._pending_language
        is_ar = (lang == "ar")

        self.header_title.setText(tr("settings_title", lang))
        self.account_header.setText(tr("account_section", lang))
        self.btn_sign_out.setText(tr("sign_out", lang))
        self.theme_label.setText(tr("theme_section", lang))
        self.dl_label.setText(tr("download_location", lang))
        self.cache_header.setText(tr("cache_section", lang))
        self.btn_clear_cache.setText(tr("clear_cache", lang))
        self.concurrent_header.setText(tr("concurrent_downloads", lang))
        self.concurrent_label.setText(tr("concurrent_downloads", lang))
        self.lang_label.setText(tr("language_section", lang))
        self.tools_label.setText(tr("tools_section", lang))
        self.btn_indexing_manager.setText(tr("indexing_manager", lang))
        self.btn_reindex.setText(tr("reindex_dialogues", lang))
        self.about_header.setText(tr("about_section", lang))
        self.desc_label.setText(tr("about_desc", lang))
        self.btn_apply.setText(tr("apply_button", lang))

        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft if is_ar else Qt.LayoutDirection.LeftToRight)
        self._refresh_cache_size(scan_disk=False)

    def _on_browse_download_path(self):
        chosen_dir = QFileDialog.getExistingDirectory(
            self,
            "Select Download Directory",
            self._pending_download_dir,
        )
        if chosen_dir:
            new_dir = str(Path(chosen_dir))
            self._pending_download_dir = new_dir
            self.dl_path_input.setText(new_dir)

    def _refresh_cache_size(self, scan_disk: bool = False):
        if scan_disk:
            cache_dir = settings.data_dir / "cache"
            total_bytes = 0
            if cache_dir.exists():
                try:
                    for f in cache_dir.rglob("*"):
                        if f.is_file():
                            total_bytes += f.stat().st_size
                except Exception:
                    pass
            self._cached_cache_mb = total_bytes / (1024 * 1024)

        mb = self._cached_cache_mb
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
            self._refresh_cache_size(scan_disk=True)

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
        """Commit pending changes to QSettings and real application state without lag."""
        self._saved_theme = self._pending_theme
        if theme_manager.current_theme_mode != self._saved_theme:
            theme_manager.set_theme(self._saved_theme)
        else:
            theme_manager.settings.setValue("theme_mode", self._saved_theme)

        self._saved_language = self._pending_language
        if theme_manager.get_current_language() != self._saved_language:
            theme_manager.set_language(self._saved_language)
        else:
            self.app_settings.setValue("language", self._saved_language)

        if self._pending_download_dir:
            settings.download_dir = Path(self._pending_download_dir)
            self.app_settings.setValue("download_dir", self._pending_download_dir)

        settings.max_concurrent_downloads = self._pending_concurrency
        self.app_settings.setValue("max_concurrent_downloads", self._pending_concurrency)

        is_ar = (self._saved_language == "ar")
        self.btn_apply.setText("تم التطبيق" if is_ar else "Applied")
        self.btn_apply.setIcon(get_icon("check", color="#FFFFFF", size=14))
        self.btn_apply.setEnabled(False)

        def restore_btn():
            from PySide6.QtGui import QIcon
            self.btn_apply.setIcon(QIcon())
            self.btn_apply.setText("تطبيق" if is_ar else "Apply")
            self.btn_apply.setEnabled(True)

        QTimer.singleShot(1500, restore_btn)

    def _on_cancel_close(self):
        """Revert uncommitted theme / language preview and close panel."""
        if self._pending_theme != self._saved_theme:
            self._pending_theme = self._saved_theme
            self.theme_segmented.set_value(self._saved_theme)
            theme_manager.set_theme(self._saved_theme)

        if self._pending_language != self._saved_language:
            self._pending_language = self._saved_language
            self.lang_segmented.set_value(self._saved_language)
            self._update_localized_ui()
            self.language_changed.emit(self._saved_language)

        self.close_requested.emit()
