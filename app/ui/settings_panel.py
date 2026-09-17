"""Slide-in / docked settings panel matching Screenshot 4 of the Obsidian specification."""

import shutil
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal, QSize
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
from .theme_manager import theme_manager
from .fonts import get_font_for_text, get_title_font, get_section_header_font, get_body_font, get_secondary_font

logger = get_logger("ui.settings_panel")


class SettingsPanel(QFrame):
    """Slide-in docked settings panel strictly adhering to Screenshot 4:
    - Theme: System / Light / Dark (segmented pills)
    - Download location: folder icon + path picker
    - Cache size limit + Clear cache button
    - Max concurrent downloads: stepper (+ / -)
    - Language: English / العربية
    """

    close_requested = Signal()
    theme_changed = Signal(str)
    language_changed = Signal(str)

    def __init__(self, repo: Optional[DatabaseRepository] = None, parent=None):
        super().__init__(parent)
        self.repo = repo or DatabaseRepository()
        self.setFixedWidth(320)
        self.setObjectName("settingsPanel")
        self._init_ui()
        self._refresh_cache_size()

    def _init_ui(self):
        tokens = theme_manager.get_active_tokens()
        self.setStyleSheet(
            f"""
            QFrame#settingsPanel {{
                background-color: {tokens['bg_surface']};
                border-right: 1px solid {tokens['border']};
            }}
            """
        )

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # Header Row: Title "الإعدادات / Settings" + Close button
        header_row = QHBoxLayout()
        header_title = QLabel("الإعدادات")
        header_title.setFont(get_title_font("الإعدادات"))
        header_title.setStyleSheet(f"color: {tokens['text_primary']};")
        header_row.addWidget(header_title)

        header_row.addStretch()

        self.btn_close = QPushButton()
        self.btn_close.setIcon(get_icon("x", color=tokens["text_secondary"], size=16))
        self.btn_close.setFixedSize(32, 32)
        self.btn_close.setStyleSheet("background: transparent; border: none; border-radius: 6px;")
        self.btn_close.clicked.connect(self.close_requested.emit)
        header_row.addWidget(self.btn_close)

        main_layout.addLayout(header_row)

        # Scrollable settings content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        c_layout = QVBoxLayout(scroll_content)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(24)

        # --- Section 1: Theme (Segmented Control: System / Light / Dark) ---
        theme_box = QVBoxLayout()
        theme_box.setSpacing(8)

        theme_label = QLabel("الثيم")
        theme_label.setFont(get_section_header_font("الثيم"))
        theme_label.setStyleSheet(f"color: {tokens['text_secondary']};")
        theme_box.addWidget(theme_label)

        theme_pills = QHBoxLayout()
        theme_pills.setSpacing(4)

        self.btn_theme_system = QPushButton("النظام")
        self.btn_theme_light = QPushButton("فاتح")
        self.btn_theme_dark = QPushButton("غامق")

        self.theme_buttons = [
            (self.btn_theme_system, "system"),
            (self.btn_theme_light, "light"),
            (self.btn_theme_dark, "dark"),
        ]

        active_mode = theme_manager.current_theme_mode
        for btn, mode in self.theme_buttons:
            btn.setObjectName("themePillButton")
            btn.setCheckable(True)
            btn.setChecked(mode == active_mode)
            btn.setFont(get_body_font(btn.text()))
            btn.setFixedHeight(34)
            btn.clicked.connect(lambda checked=False, m=mode: self._on_theme_pill_clicked(m))
            theme_pills.addWidget(btn)

        theme_box.addLayout(theme_pills)
        c_layout.addLayout(theme_box)

        # --- Section 2: Download Location (Path Picker) ---
        dl_box = QVBoxLayout()
        dl_box.setSpacing(8)

        dl_label = QLabel("مسار التحميل")
        dl_label.setFont(get_section_header_font("مسار التحميل"))
        dl_label.setStyleSheet(f"color: {tokens['text_secondary']};")
        dl_box.addWidget(dl_label)

        dl_row = QHBoxLayout()
        dl_row.setSpacing(6)

        self.dl_path_input = QLineEdit(str(settings.download_dir))
        self.dl_path_input.setReadOnly(True)
        self.dl_path_input.setFixedHeight(36)
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
        self.btn_browse.setFixedSize(36, 36)
        self.btn_browse.setObjectName("secondaryButton")
        self.btn_browse.setToolTip("Browse folder")
        self.btn_browse.clicked.connect(self._on_browse_download_path)
        dl_row.addWidget(self.btn_browse)

        dl_box.addLayout(dl_row)
        c_layout.addLayout(dl_box)

        # --- Section 3: Cache size limit + Clear Cache ---
        cache_box = QVBoxLayout()
        cache_box.setSpacing(8)

        self.cache_size_label = QLabel("الذاكرة المؤقتة: 0 MB")
        self.cache_size_label.setFont(get_section_header_font())
        self.cache_size_label.setStyleSheet(f"color: {tokens['text_secondary']};")
        cache_box.addWidget(self.cache_size_label)

        self.btn_clear_cache = QPushButton("مسح الذاكرة المؤقتة")
        self.btn_clear_cache.setObjectName("secondaryButton")
        self.btn_clear_cache.setFixedHeight(36)
        self.btn_clear_cache.setFont(get_body_font("مسح الذاكرة المؤقتة"))
        self.btn_clear_cache.clicked.connect(self._on_clear_cache)
        cache_box.addWidget(self.btn_clear_cache)

        c_layout.addLayout(cache_box)

        # --- Section 4: Max Concurrent Downloads (Stepper: + value -) ---
        concurrent_box = QVBoxLayout()
        concurrent_box.setSpacing(8)

        concurrent_label = QLabel("التحميلات المتزامنة")
        concurrent_label.setFont(get_section_header_font("التحميلات المتزامنة"))
        concurrent_label.setStyleSheet(f"color: {tokens['text_secondary']};")
        concurrent_box.addWidget(concurrent_label)

        stepper_row = QHBoxLayout()
        stepper_row.setSpacing(8)

        self.btn_plus = QPushButton("+")
        self.btn_plus.setFixedSize(34, 34)
        self.btn_plus.setFont(QFont("Inter", 13, QFont.Bold))
        self.btn_plus.setObjectName("secondaryButton")
        self.btn_plus.clicked.connect(self._increment_concurrent)
        stepper_row.addWidget(self.btn_plus)

        val = getattr(settings, "max_concurrent_downloads", 3)
        self.concurrent_val_label = QLabel(str(val))
        self.concurrent_val_label.setFixedWidth(40)
        self.concurrent_val_label.setAlignment(Qt.AlignCenter)
        self.concurrent_val_label.setFont(QFont("Inter", 14, QFont.Bold))
        self.concurrent_val_label.setStyleSheet(f"color: {tokens['text_primary']};")
        stepper_row.addWidget(self.concurrent_val_label)

        self.btn_minus = QPushButton("-")
        self.btn_minus.setFixedSize(34, 34)
        self.btn_minus.setFont(QFont("Inter", 13, QFont.Bold))
        self.btn_minus.setObjectName("secondaryButton")
        self.btn_minus.clicked.connect(self._decrement_concurrent)
        stepper_row.addWidget(self.btn_minus)

        stepper_row.addStretch()
        concurrent_box.addLayout(stepper_row)
        c_layout.addLayout(concurrent_box)

        # --- Section 5: Language (English / العربية) ---
        lang_box = QVBoxLayout()
        lang_box.setSpacing(8)

        lang_label = QLabel("اللغة")
        lang_label.setFont(get_section_header_font("اللغة"))
        lang_label.setStyleSheet(f"color: {tokens['text_secondary']};")
        lang_box.addWidget(lang_label)

        lang_pills = QHBoxLayout()
        lang_pills.setSpacing(4)

        self.btn_lang_en = QPushButton("English")
        self.btn_lang_ar = QPushButton("العربية")

        self.btn_lang_en.setObjectName("themePillButton")
        self.btn_lang_ar.setObjectName("themePillButton")
        self.btn_lang_en.setCheckable(True)
        self.btn_lang_ar.setCheckable(True)
        self.btn_lang_ar.setChecked(True)  # Default Arabic per screenshot
        self.btn_lang_en.setFixedHeight(34)
        self.btn_lang_ar.setFixedHeight(34)
        self.btn_lang_en.setFont(get_body_font("English"))
        self.btn_lang_ar.setFont(get_body_font("العربية"))

        self.btn_lang_en.clicked.connect(lambda: self._set_language("en"))
        self.btn_lang_ar.clicked.connect(lambda: self._set_language("ar"))

        lang_pills.addWidget(self.btn_lang_en)
        lang_pills.addWidget(self.btn_lang_ar)
        lang_box.addLayout(lang_pills)
        c_layout.addLayout(lang_box)

        c_layout.addStretch()
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

    def _on_theme_pill_clicked(self, mode: str):
        for btn, m in self.theme_buttons:
            btn.setChecked(m == mode)
        theme_manager.set_theme(mode)
        self.theme_changed.emit(mode)

    def _on_browse_download_path(self):
        new_dir = QFileDialog.getExistingDirectory(
            self,
            "Select Download Directory",
            str(settings.download_dir),
        )
        if new_dir:
            self.dl_path_input.setText(new_dir)
            settings.download_dir = Path(new_dir)

    def _refresh_cache_size(self):
        cache_dir = settings.data_dir / "cache"
        total_bytes = 0
        if cache_dir.exists():
            for f in cache_dir.rglob("*"):
                if f.is_file():
                    total_bytes += f.stat().st_size
        mb = total_bytes / (1024 * 1024)
        if mb >= 1024:
            self.cache_size_label.setText(f"الذاكرة المؤقتة: {mb / 1024:.1f} GB")
        else:
            self.cache_size_label.setText(f"الذاكرة المؤقتة: {mb:.1f} MB")

    def _on_clear_cache(self):
        confirm = QMessageBox.question(
            self,
            "Clear Cache",
            "Are you sure you want to clear all cached thumbnails and indexing state?",
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
        val = int(self.concurrent_val_label.text())
        if val < 8:
            val += 1
            self.concurrent_val_label.setText(str(val))
            settings.max_concurrent_downloads = val

    def _decrement_concurrent(self):
        val = int(self.concurrent_val_label.text())
        if val > 1:
            val -= 1
            self.concurrent_val_label.setText(str(val))
            settings.max_concurrent_downloads = val

    def _set_language(self, lang: str):
        self.btn_lang_en.setChecked(lang == "en")
        self.btn_lang_ar.setChecked(lang == "ar")
        self.language_changed.emit(lang)
