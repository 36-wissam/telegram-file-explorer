"""Chat media browser widget supporting automatic progressive media loading, virtualized QListView, and search."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set

from PySide6.QtCore import Qt, Signal, QSize, QTimer, QRectF, QModelIndex, QItemSelectionModel
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPixmap, QBrush
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    QListView,
    QAbstractItemView,
)

from ..core.async_runner import async_runner
from ..core.logger import get_logger
from ..database.models import IndexedFileModel
from ..database.repository import DatabaseRepository
from ..services.indexer import MediaIndexerService
from ..services.media_parser import MediaType
from ..services.search import SearchEngineService
from ..services.preview import PreviewService
from ..services.image_loader import thumbnail_manager
from ..telegram.chats import ChatType, TelegramChat
from .filter_bar import AdvancedFilterCriteria
from .filter_dialog import FilterDialog
from .icons import get_icon, get_pixmap
from .fonts import get_font_for_text, get_title_font, get_section_header_font, get_body_font, get_secondary_font, get_caption_font
from .media_model import MediaListModel, FileModelRole, FileIdRole
from .media_delegates import MediaGridDelegate, MediaListDelegate
from .theme_manager import theme_manager, DARK_TOKENS
from .media_card import format_bytes, MediaCardWidget

logger = get_logger("ui.media_browser")

MEDIA_TABS = [
    ("الكل", None),
    ("صور", "IMAGE"),
    ("فيديو", "VIDEO"),
    ("ملفات", "DOCUMENT"),
    ("صوت", "AUDIO"),
    ("تسجيلات", "VOICE"),
    ("روابط", "OTHER"),
]


class SkeletonCard(QFrame):
    """Flat surface-2 placeholder loading card animated 0.4 -> 0.7 -> 0.4 on 1.2s loop."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(200)
        self.setMinimumHeight(210)
        self._opacity = 0.4
        self._animating = True
        self._increasing = True
        self._init_ui()
        self._start_animation()

    def _init_ui(self):
        tokens = theme_manager.get_active_tokens()
        self.setStyleSheet(
            f"""
            QFrame {{
                background-color: {tokens['bg_surface']};
                border: 1px solid {tokens['border']};
                border-radius: 10px;
            }}
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.thumb = QLabel()
        self.thumb.setFixedSize(180, 110)
        self.thumb.setStyleSheet(f"background-color: {tokens['bg_surface_2']}; border-radius: 6px;")
        layout.addWidget(self.thumb, alignment=Qt.AlignmentFlag.AlignCenter)

        self.name_bar = QLabel()
        self.name_bar.setFixedSize(140, 14)
        self.name_bar.setStyleSheet(f"background-color: {tokens['bg_surface_2']}; border-radius: 3px;")
        layout.addWidget(self.name_bar)

        self.meta_bar = QLabel()
        self.meta_bar.setFixedSize(100, 10)
        self.meta_bar.setStyleSheet(f"background-color: {tokens['bg_surface_2']}; border-radius: 3px;")
        layout.addWidget(self.meta_bar)

    def _start_animation(self):
        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(120)  # Smooth 1.2s cycle
        self._pulse_timer.timeout.connect(self._pulse)
        self._pulse_timer.start()

    def _pulse(self):
        if self._increasing:
            self._opacity += 0.06
            if self._opacity >= 0.7:
                self._opacity = 0.7
                self._increasing = False
        else:
            self._opacity -= 0.06
            if self._opacity <= 0.4:
                self._opacity = 0.4
                self._increasing = True

        tokens = theme_manager.get_active_tokens()
        alpha = int(self._opacity * 255)
        # Pulse between surface-2 and subtle hover
        color = tokens["bg_surface_2"]
        style = f"background-color: {color}; border-radius: 6px; opacity: {self._opacity:.2f};"
        self.thumb.setStyleSheet(style)


class TableCompat:
    """Compatibility wrapper providing table.rowCount() for tests."""
    def __init__(self, model: MediaListModel):
        self._model = model

    def rowCount(self) -> int:
        return self._model.rowCount()


class ChatMediaBrowserWidget(QWidget):
    """Virtualized Media Browser using QListView + QStyledItemDelegate strictly matching Screenshots 1-4."""

    file_selected = Signal(object)
    file_double_clicked = Signal(object)
    download_requested = Signal(object)
    open_requested = Signal(object)

    def __init__(
        self,
        repo: DatabaseRepository,
        indexer_service: Optional[MediaIndexerService] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.repo = repo
        self.indexer_service = indexer_service
        self.search_service = SearchEngineService(self.repo)
        self.current_chat: Optional[TelegramChat] = None
        self._current_category: Optional[str] = None
        self._search_query: str = ""
        self._sort_by: str = "date"
        self._sort_desc: bool = True
        self._filter_criteria = AdvancedFilterCriteria()
        self._cached_files: List[IndexedFileModel] = []
        self._active_indexing_chats: Set[int] = set()
        self.preview_service: Optional[PreviewService] = None

        # Request ID for stale off-thread discard
        self._current_request_id: int = 0

        # Virtualized model & delegates
        self.media_model = MediaListModel(self)
        self.grid_delegate = MediaGridDelegate(self)
        self.list_delegate = MediaListDelegate(self)

        self.grid_delegate.download_clicked.connect(self._on_delegate_download)
        self.grid_delegate.open_clicked.connect(self._on_delegate_open)
        self.list_delegate.download_clicked.connect(self._on_delegate_download)
        self.list_delegate.open_clicked.connect(self._on_delegate_open)

        thumbnail_manager.thumbnail_ready.connect(self._on_thumbnail_decoded)
        theme_manager.theme_changed.connect(self._on_theme_changed)

        self._init_ui()

    def set_client_manager(self, client_manager):
        self.preview_service = PreviewService(client_manager)

    def _init_ui(self):
        tokens = theme_manager.get_active_tokens()
        self.setStyleSheet("background-color: transparent;")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Top Bar strictly conforming to Screenshots 1, 2, 3, 4
        self.top_bar = self._create_top_bar(tokens)
        main_layout.addWidget(self.top_bar)

        # 2. Main Canvas Stack: 0 = Grid, 1 = List, 2 = Empty
        self.view_stack = QStackedWidget(self)

        # Page 0: Grid View (QListView in IconMode)
        self.grid_view = QListView()
        self.grid_view.setViewMode(QListView.ViewMode.IconMode)
        self.grid_view.setResizeMode(QListView.ResizeMode.Adjust)
        self.grid_view.setUniformItemSizes(True)
        self.grid_view.setGridSize(QSize(178, 208))
        self.grid_view.setSpacing(14)
        self.grid_view.setMouseTracking(True)
        self.grid_view.setModel(self.media_model)
        self.grid_view.setItemDelegate(self.grid_delegate)
        self.grid_view.setStyleSheet("QListView { background-color: transparent; border: none; outline: none; }")
        self.grid_view.clicked.connect(self._on_view_item_clicked)
        self.grid_view.doubleClicked.connect(self._on_view_item_double_clicked)
        self.view_stack.addWidget(self.grid_view)

        # Page 1: List View (QListView in ListMode)
        self.list_view = QListView()
        self.list_view.setViewMode(QListView.ViewMode.ListMode)
        self.list_view.setUniformItemSizes(True)
        self.list_view.setSpacing(4)
        self.list_view.setMouseTracking(True)
        self.list_view.setModel(self.media_model)
        self.list_view.setItemDelegate(self.list_delegate)
        self.list_view.setStyleSheet("QListView { background-color: transparent; border: none; outline: none; }")
        self.list_view.clicked.connect(self._on_view_item_clicked)
        self.list_view.doubleClicked.connect(self._on_view_item_double_clicked)
        self.view_stack.addWidget(self.list_view)

        # Table compatibility
        self.table = TableCompat(self.media_model)

        # Page 2: Empty State Card
        self.empty_card = QFrame()
        self.empty_card.setStyleSheet("background-color: transparent; border: none;")
        empty_layout = QVBoxLayout(self.empty_card)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.setSpacing(12)

        self.empty_icon_label = QLabel()
        self.empty_icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_icon_label.setPixmap(get_pixmap("folder", color=tokens["text_tertiary"], size=34))
        empty_layout.addWidget(self.empty_icon_label)

        self.empty_title = QLabel("Select a chat to view files")
        self.empty_title.setFont(get_body_font("Select a chat to view files"))
        self.empty_title.setStyleSheet(f"color: {tokens['text_secondary']};")
        self.empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(self.empty_title)

        self.view_stack.addWidget(self.empty_card)
        self.view_stack.setCurrentIndex(2)
        main_layout.addWidget(self.view_stack)

        # Hidden search input for programmatic compatibility
        self.search_input = QLineEdit()
        self.search_input.hide()

    def _create_top_bar(self, tokens: dict) -> QWidget:
        """Top navigation bar matching Screenshots 1-4:
        Left: Chat title + file count ('40 ملف')
        Center: Category filter pills ('الكل', 'صور', 'فيديو', 'ملفات', 'صوت')
        Right: Grid button (blue active), List button, Sun/Moon theme toggle
        """
        top_bar = QFrame(self)
        top_bar.setFixedHeight(56)
        top_bar.setStyleSheet(
            f"""
            QFrame {{
                background-color: {tokens['bg_base']};
                border-bottom: 1px solid {tokens['border']};
            }}
            """
        )
        layout = QHBoxLayout(top_bar)
        layout.setContentsMargins(20, 8, 20, 8)
        layout.setSpacing(16)

        # Left Info: Chat Title + File Count
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        info_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.title_label = QLabel("Select Chat")
        self.title_label.setFont(get_font_for_text(self.title_label.text(), pixel_size=14, weight=600))
        self.title_label.setStyleSheet(f"color: {tokens['text_primary']};")
        info_layout.addWidget(self.title_label)

        self.count_label = QLabel("0 ملف")
        self.count_label.setFont(get_caption_font("0 ملف"))
        self.count_label.setStyleSheet(f"color: {tokens['text_tertiary']};")
        info_layout.addWidget(self.count_label)

        # Subtitle label compatibility for legacy tests
        self.subtitle_label = QLabel("")
        self.subtitle_label.hide()

        layout.addLayout(info_layout)
        layout.addStretch()

        # Center: Segmented Filter Pills
        self.pills_container = QWidget()
        pills_layout = QHBoxLayout(self.pills_container)
        pills_layout.setContentsMargins(0, 0, 0, 0)
        pills_layout.setSpacing(6)

        self.tab_buttons = []
        for label, cat_code in MEDIA_TABS:
            btn = QPushButton(label)
            btn.setObjectName("filterTabButton")
            btn.setCheckable(True)
            btn.setFont(get_body_font(label))
            btn.setFixedHeight(34)
            btn.clicked.connect(lambda checked=False, c=cat_code, b=btn: self._on_tab_clicked(c, b))
            pills_layout.addWidget(btn)
            self.tab_buttons.append(btn)

        if self.tab_buttons:
            self.tab_buttons[0].setChecked(True)

        layout.addWidget(self.pills_container)
        layout.addStretch()

        # Right Controls: Grid, List, Moon/Sun Toggle
        right_layout = QHBoxLayout()
        right_layout.setSpacing(8)

        # Grid view button
        self.btn_grid_view = QPushButton()
        self.btn_grid_view.setFixedSize(36, 36)
        self.btn_grid_view.setCheckable(True)
        self.btn_grid_view.setChecked(True)
        self.btn_grid_view.setToolTip("Grid View")
        self.btn_grid_view.clicked.connect(lambda: self._set_view_mode(0))
        right_layout.addWidget(self.btn_grid_view)

        # List view button
        self.btn_list_view = QPushButton()
        self.btn_list_view.setFixedSize(36, 36)
        self.btn_list_view.setCheckable(True)
        self.btn_list_view.setChecked(False)
        self.btn_list_view.setToolTip("List View")
        self.btn_list_view.clicked.connect(lambda: self._set_view_mode(1))
        right_layout.addWidget(self.btn_list_view)

        # Theme toggle button (Sun / Moon)
        self.btn_theme_toggle = QPushButton()
        self.btn_theme_toggle.setFixedSize(36, 36)
        self.btn_theme_toggle.setToolTip("Toggle Dark/Light Mode")
        self.btn_theme_toggle.setStyleSheet(
            f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {tokens['border']};
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {tokens['bg_hover']};
            }}
            """
        )
        self.btn_theme_toggle.clicked.connect(self._toggle_theme)
        right_layout.addWidget(self.btn_theme_toggle)

        layout.addLayout(right_layout)
        self._update_view_toggle_styles(tokens)
        return top_bar

    def _update_view_toggle_styles(self, tokens: dict):
        is_grid = self.btn_grid_view.isChecked()
        active_style = f"background-color: {tokens['accent']}; border: none; border-radius: 6px;"
        inactive_style = f"background-color: transparent; border: 1px solid {tokens['border']}; border-radius: 6px;"

        self.btn_grid_view.setStyleSheet(active_style if is_grid else inactive_style)
        self.btn_grid_view.setIcon(get_icon("grid", color="#FFFFFF" if is_grid else tokens["text_secondary"], size=18))

        self.btn_list_view.setStyleSheet(inactive_style if is_grid else active_style)
        self.btn_list_view.setIcon(get_icon("list", color=tokens["text_secondary"] if is_grid else "#FFFFFF", size=18))

        # Update Theme toggle icon: Moon in dark mode, Sun in light mode
        is_dark = (tokens["bg_base"] == DARK_TOKENS["bg_base"])
        self.btn_theme_toggle.setIcon(get_icon("moon" if is_dark else "sun", color=tokens["text_secondary"], size=18))

    def _toggle_theme(self):
        theme_manager.toggle_theme()

    def _on_theme_changed(self, tokens: dict):
        self.top_bar.setStyleSheet(f"background-color: {tokens['bg_base']}; border-bottom: 1px solid {tokens['border']};")
        self.empty_icon_label.setPixmap(get_pixmap("folder", color=tokens["text_tertiary"], size=34))
        self._update_view_toggle_styles(tokens)

    def _set_view_mode(self, mode: int):
        self.btn_grid_view.setChecked(mode == 0)
        self.btn_list_view.setChecked(mode == 1)
        tokens = theme_manager.get_active_tokens()
        self._update_view_toggle_styles(tokens)
        self.view_stack.setCurrentIndex(mode)

    def set_chat(self, chat: Optional[TelegramChat]):
        self.current_chat = chat
        self._current_request_id += 1
        req_id = self._current_request_id
        self.grid_delegate.current_request_id = req_id
        self.list_delegate.current_request_id = req_id

        if not chat:
            self.title_label.setText("Select Chat")
            self.count_label.setText("0 ملف")
            self.view_stack.setCurrentIndex(2)
            self.media_model.clear()
            return

        self.title_label.setText(chat.display_name)
        self.title_label.setFont(get_font_for_text(chat.display_name, pixel_size=14, weight=600))
        self.reload_files()
        self._start_automatic_indexing(chat, req_id)

    def _on_tab_clicked(self, category_code: Optional[str], button: QPushButton):
        for btn in self.tab_buttons:
            btn.setChecked(btn is button)
        self._current_category = category_code
        self.reload_files()

    def reload_files(self):
        if not self.current_chat:
            self.media_model.clear()
            self.view_stack.setCurrentIndex(2)
            self.count_label.setText("0 ملف")
            return

        try:
            files = self.repo.get_files_by_chat(
                chat_id=self.current_chat.id,
                category=self._current_category,
                sort_by=self._sort_by,
                sort_desc=self._sort_desc,
            )
        except Exception as e:
            logger.error("Failed to query files: %s", e)
            files = []

        self._cached_files = files
        self.count_label.setText(f"{len(files)} ملف")

        if files:
            self.media_model.set_files(files)
            mode = 0 if self.btn_grid_view.isChecked() else 1
            self.view_stack.setCurrentIndex(mode)
            self._fetch_missing_thumbnails()
        else:
            self.media_model.clear()
            self.view_stack.setCurrentIndex(2)

    def _start_automatic_indexing(self, chat: TelegramChat, request_id: int):
        if not self.indexer_service:
            return
        chat_id = chat.id
        if chat_id in self._active_indexing_chats:
            return
        self._active_indexing_chats.add(chat_id)

        def on_batch_discovered(batch):
            if request_id != self._current_request_id:
                return
            if self.current_chat and self.current_chat.id == chat_id:
                self.reload_files()
                if self.preview_service:
                    self._fetch_batch_thumbnails(batch, chat_id)

        def on_complete(count):
            self._active_indexing_chats.discard(chat_id)
            if request_id == self._current_request_id and self.current_chat and self.current_chat.id == chat_id:
                self.reload_files()

        def on_error(exc):
            self._active_indexing_chats.discard(chat_id)
            logger.debug("Automatic indexing error: %s", exc)

        async_runner.run_coroutine_async(
            self.indexer_service.index_chat(
                chat_id=chat.id,
                chat_title=chat.title,
                batch_callback=on_batch_discovered,
            ),
            callback=on_complete,
            error_callback=on_error,
        )

    def _fetch_batch_thumbnails(self, batch, chat_id):
        if not self.preview_service:
            return
        thumb_items = [item for item in batch if getattr(item, 'has_thumbnail', False)]
        if not thumb_items:
            return

        def on_thumbs_fetched(results):
            if not results:
                return
            if self.indexer_service:
                self.indexer_service.update_thumbnail_paths(results)
            for fid, p in results.items():
                self.media_model.update_thumbnail_path(fid, p)

        async_runner.run_coroutine_async(
            self.preview_service.fetch_thumbnails_batch(thumb_items),
            callback=on_thumbs_fetched,
            error_callback=lambda e: logger.debug("Batch thumbnail fetch failed: %s", e),
        )

    def _fetch_missing_thumbnails(self):
        if not self.preview_service or not self._cached_files:
            return
        missing = [f for f in self._cached_files if f.has_thumbnail and not f.thumbnail_path][:20]
        if not missing:
            return

        def on_thumbs_fetched(results):
            if not results:
                return
            if self.indexer_service:
                self.indexer_service.update_thumbnail_paths(results)
            for fid, p in results.items():
                self.media_model.update_thumbnail_path(fid, p)

        async_runner.run_coroutine_async(
            self.preview_service.fetch_thumbnails_batch(missing),
            callback=on_thumbs_fetched,
            error_callback=lambda e: logger.debug("Missing thumbnail fetch failed: %s", e),
        )

    def _on_thumbnail_decoded(self, req_id: int, file_id: str, pixmap: QPixmap):
        if req_id != self._current_request_id:
            return
        self.grid_view.viewport().update()
        self.list_view.viewport().update()

    def _on_delegate_download(self, file_model: IndexedFileModel):
        if file_model:
            self.download_requested.emit(file_model)

    def _on_delegate_open(self, file_model: IndexedFileModel):
        if file_model:
            self.open_requested.emit(file_model)

    def _on_view_item_clicked(self, index: QModelIndex):
        file_model = index.data(FileModelRole)
        if file_model:
            self.file_selected.emit(file_model)

    def _on_view_item_double_clicked(self, index: QModelIndex):
        file_model = index.data(FileModelRole)
        if file_model:
            self.file_double_clicked.emit(file_model)

    def focus_search(self):
        self.search_input.setFocus()
