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
from .media_model import MediaListModel, FileModelRole, FileIdRole
from .media_delegates import MediaGridDelegate, MediaListDelegate
from .theme_manager import theme_manager
from .media_card import format_bytes, MediaCardWidget

logger = get_logger("ui.media_browser")

MEDIA_TABS = [
    ("All", None),
    ("Photos", "IMAGE"),
    ("Videos", "VIDEO"),
    ("Files", "DOCUMENT"),
    ("Audio", "AUDIO"),
    ("Voice", "VOICE"),
    ("Links", "OTHER"),
]


class SkeletonCard(QFrame):
    """Placeholder loading card shown during progressive media discovery."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(200)
        self.setMinimumHeight(210)
        self._opacity = 0.3
        self._animating = True
        self._init_ui()
        self._start_animation()

    def _init_ui(self):
        self.setStyleSheet("""
            QFrame {
                background-color: #14171C;
                border: 1px solid #2A2F38;
                border-radius: 10px;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        thumb = QLabel()
        thumb.setFixedSize(180, 110)
        thumb.setStyleSheet("background-color: #1B1F26; border-radius: 6px;")
        layout.addWidget(thumb, alignment=Qt.AlignCenter)

        name = QLabel()
        name.setFixedSize(140, 14)
        name.setStyleSheet("background-color: #1B1F26; border-radius: 3px;")
        layout.addWidget(name)

        meta = QLabel()
        meta.setFixedSize(100, 10)
        meta.setStyleSheet("background-color: #1B1F26; border-radius: 3px;")
        layout.addWidget(meta)

    def _start_animation(self):
        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(800)
        self._pulse_timer.timeout.connect(self._pulse)
        self._pulse_timer.start()

    def _pulse(self):
        if self._opacity < 0.5:
            self._opacity = 0.6
            bg = "#232830"
        else:
            self._opacity = 0.3
            bg = "#1B1F26"
        for child in self.findChildren(QLabel):
            child.setStyleSheet(f"background-color: {bg}; border-radius: {6 if child.height() > 20 else 3}px;")


class ChatMediaBrowserWidget(QWidget):
    """Virtualized Media Browser using QListView + QStyledItemDelegate for 60fps anti-freeze rendering."""

    file_selected = Signal(object)        # Emits IndexedFileModel
    file_double_clicked = Signal(object) # Emits IndexedFileModel
    download_requested = Signal(object)  # Emits IndexedFileModel
    open_requested = Signal(object)      # Emits IndexedFileModel

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

        # Anti-freeze stale-request tracking
        self._current_request_id: int = 0

        # Virtualized model and delegates
        self.media_model = MediaListModel(self)
        self.grid_delegate = MediaGridDelegate(self)
        self.list_delegate = MediaListDelegate(self)

        # Connect delegate action signals
        self.grid_delegate.download_clicked.connect(self._on_delegate_download)
        self.grid_delegate.open_clicked.connect(self._on_delegate_open)
        self.list_delegate.download_clicked.connect(self._on_delegate_download)
        self.list_delegate.open_clicked.connect(self._on_delegate_open)

        # Off-thread thumbnail ready signal
        thumbnail_manager.thumbnail_ready.connect(self._on_thumbnail_decoded)

        # Debounce timer for search
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(200)
        self._search_timer.timeout.connect(self._execute_search)

        self._init_ui()

    def set_client_manager(self, client_manager):
        """Inject Telegram client manager for background thumbnail fetching."""
        self.preview_service = PreviewService(client_manager)

    def _init_ui(self):
        self.setStyleSheet("background-color: transparent;")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Chat Header Section
        self.header_card = self._create_chat_header()
        main_layout.addWidget(self.header_card)

        # 2. Media Tabs Navigation Bar (Segmented Pills)
        self.tabs_bar = self._create_tabs_bar()
        main_layout.addWidget(self.tabs_bar)

        # 3. View Switcher & Filter Toolbar
        self.toolbar = self._create_toolbar()
        main_layout.addWidget(self.toolbar)

        # 4. Main View Canvas (Stack: 0 = Grid, 1 = List, 2 = Empty state)
        self.view_stack = QStackedWidget(self)

        # Page 0: Virtualized Grid View (QListView in IconMode)
        self.grid_view = QListView()
        self.grid_view.setViewMode(QListView.ViewMode.IconMode)
        self.grid_view.setResizeMode(QListView.ResizeMode.Adjust)
        self.grid_view.setUniformItemSizes(True)
        self.grid_view.setGridSize(QSize(180, 210))
        self.grid_view.setSpacing(12)
        self.grid_view.setMouseTracking(True)
        self.grid_view.setModel(self.media_model)
        self.grid_view.setItemDelegate(self.grid_delegate)
        self.grid_view.setStyleSheet("QListView { background-color: transparent; border: none; outline: none; }")
        self.grid_view.clicked.connect(self._on_view_item_clicked)
        self.grid_view.doubleClicked.connect(self._on_view_item_double_clicked)
        self.view_stack.addWidget(self.grid_view)

        # Page 1: Virtualized List View (QListView in ListMode)
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

        # Table compatibility object for existing test suite
        class TableCompat:
            def __init__(self, model):
                self._model = model
            def rowCount(self):
                return self._model.rowCount()
        self.table = TableCompat(self.media_model)

        # Page 2: Empty State Card / Preload Skeleton
        self.empty_card = QFrame()
        self.empty_card.setStyleSheet("background-color: transparent; border: none;")
        empty_layout = QVBoxLayout(self.empty_card)
        empty_layout.setAlignment(Qt.AlignCenter)
        empty_layout.setSpacing(12)

        self.empty_icon_label = QLabel()
        self.empty_icon_label.setAlignment(Qt.AlignCenter)
        self.empty_icon_label.setPixmap(get_pixmap("folder", color="#5F6672", size=48))
        empty_layout.addWidget(self.empty_icon_label)

        self.empty_title = QLabel("Select a chat to view files")
        self.empty_title.setStyleSheet("font-size: 16px; font-weight: 600; color: #ECEDEE;")
        self.empty_title.setAlignment(Qt.AlignCenter)
        empty_layout.addWidget(self.empty_title)

        self.empty_desc = QLabel("Choose a dialogue from the left sidebar to browse shared media.")
        self.empty_desc.setStyleSheet("font-size: 13px; color: #9BA1AC; max-width: 440px;")
        self.empty_desc.setAlignment(Qt.AlignCenter)
        self.empty_desc.setWordWrap(True)
        empty_layout.addWidget(self.empty_desc)

        self.view_stack.addWidget(self.empty_card)
        self.view_stack.setCurrentIndex(2)  # Default empty
        main_layout.addWidget(self.view_stack)

        # 5. Progressive Loading Status Banner
        self.status_banner = QFrame()
        self.status_banner.setFixedHeight(36)
        self.status_banner.setStyleSheet(
            """
            QFrame {
                background-color: #14171C;
                border-top: 1px solid #2A2F38;
                padding: 4px 16px;
            }
            """
        )
        sb_layout = QHBoxLayout(self.status_banner)
        sb_layout.setContentsMargins(16, 4, 16, 4)

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #9BA1AC; font-size: 12px; font-weight: 500;")
        sb_layout.addWidget(self.status_label)

        sb_layout.addStretch()

        self.count_label = QLabel("0 files")
        self.count_label.setStyleSheet("color: #5F6672; font-size: 12px;")
        sb_layout.addWidget(self.count_label)

        main_layout.addWidget(self.status_banner)

    def _create_chat_header(self) -> QWidget:
        header = QFrame(self)
        header.setFixedHeight(64)
        header.setStyleSheet(
            """
            QFrame {
                background-color: #14171C;
                border-bottom: 1px solid #2A2F38;
                padding: 8px 24px;
            }
            """
        )
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(24, 8, 24, 8)
        h_layout.setSpacing(14)

        # Avatar
        self.avatar_label = QLabel()
        self.avatar_label.setFixedSize(40, 40)
        h_layout.addWidget(self.avatar_label)

        # Text Details (Name + Username/Type)
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        text_layout.setAlignment(Qt.AlignVCenter)

        self.title_label = QLabel("No Chat Selected")
        title_font = QFont("Inter", 12)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.title_label.setStyleSheet("color: #ECEDEE;")
        text_layout.addWidget(self.title_label)

        self.subtitle_label = QLabel("Select a chat to begin")
        self.subtitle_label.setStyleSheet("color: #9BA1AC; font-size: 12px;")
        text_layout.addWidget(self.subtitle_label)

        h_layout.addLayout(text_layout)
        h_layout.addStretch()

        # Chat Search Input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search files...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setFixedWidth(240)
        self.search_input.textChanged.connect(self._on_search_text_changed)
        h_layout.addWidget(self.search_input)

        return header

    def _create_tabs_bar(self) -> QWidget:
        bar = QFrame(self)
        bar.setFixedHeight(44)
        bar.setStyleSheet(
            """
            QFrame {
                background-color: #14171C;
                border-bottom: 1px solid #2A2F38;
                padding: 0 16px;
            }
            """
        )
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(8)

        self.tab_buttons = []
        for label, cat_code in MEDIA_TABS:
            btn = QPushButton(label)
            btn.setObjectName("filterTabButton")
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked=False, c=cat_code, b=btn: self._on_tab_clicked(c, b))
            layout.addWidget(btn)
            self.tab_buttons.append(btn)

        if self.tab_buttons:
            self.tab_buttons[0].setChecked(True)

        layout.addStretch()
        return bar

    def _create_toolbar(self) -> QWidget:
        toolbar = QFrame(self)
        toolbar.setFixedHeight(48)
        toolbar.setStyleSheet(
            """
            QFrame {
                background-color: #0B0D10;
                border-bottom: 1px solid #2A2F38;
                padding: 4px 24px;
            }
            """
        )
        t_layout = QHBoxLayout(toolbar)
        t_layout.setContentsMargins(24, 6, 24, 6)
        t_layout.setSpacing(10)

        # View Toggle: Grid / List
        self.btn_grid_view = QPushButton("Grid")
        self.btn_grid_view.setObjectName("secondaryButton")
        self.btn_grid_view.setIcon(get_icon("grid", color="#9BA1AC", size=14))
        self.btn_grid_view.setToolTip("Switch to thumbnail grid view")
        self.btn_grid_view.setCheckable(True)
        self.btn_grid_view.setChecked(True)
        self.btn_grid_view.clicked.connect(lambda: self._set_view_mode(0))
        t_layout.addWidget(self.btn_grid_view)

        self.btn_list_view = QPushButton("List")
        self.btn_list_view.setObjectName("secondaryButton")
        self.btn_list_view.setIcon(get_icon("list", color="#9BA1AC", size=14))
        self.btn_list_view.setToolTip("Switch to detailed list view")
        self.btn_list_view.setCheckable(True)
        self.btn_list_view.setChecked(False)
        self.btn_list_view.clicked.connect(lambda: self._set_view_mode(1))
        t_layout.addWidget(self.btn_list_view)

        # Filters Button
        self.btn_filter = QPushButton("Filters")
        self.btn_filter.setObjectName("secondaryButton")
        self.btn_filter.setIcon(get_icon("sliders_horizontal", color="#9BA1AC", size=14))
        self.btn_filter.setToolTip("Open advanced filters")
        self.btn_filter.clicked.connect(self._open_filter_dialog)
        t_layout.addWidget(self.btn_filter)

        t_layout.addStretch()

        # Sort Dropdown
        sort_label = QLabel("Sort:")
        sort_label.setStyleSheet("color: #5F6672; font-size: 12px;")
        t_layout.addWidget(sort_label)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems([
            "Newest First",
            "Oldest First",
            "Largest First",
            "Smallest First",
            "Name (A to Z)",
            "Name (Z to A)",
        ])
        self.sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        t_layout.addWidget(self.sort_combo)

        return toolbar

    def set_chat(self, chat: Optional[TelegramChat]):
        """Select chat, immediately query local cache (0ms wait), and sync Telegram in background."""
        self.current_chat = chat
        self._current_request_id += 1
        req_id = self._current_request_id
        self.grid_delegate.current_request_id = req_id
        self.list_delegate.current_request_id = req_id

        if not chat:
            self.title_label.setText("No Chat Selected")
            self.subtitle_label.setText("Select a chat to begin")
            self.avatar_label.setPixmap(QPixmap())
            self.view_stack.setCurrentIndex(2)
            self.status_label.setText("Ready")
            self.count_label.setText("0 files")
            self.media_model.clear()
            return

        # 1. Update Header
        self.title_label.setText(chat.display_name)
        subtitle_parts = []
        if chat.username:
            subtitle_parts.append(f"@{chat.username}")
        subtitle_parts.append(chat.chat_type.value)
        self.subtitle_label.setText(" · ".join(subtitle_parts))
        self.avatar_label.setPixmap(self._render_header_avatar(chat))

        # 2. Instant Local Cache Render (Zero freeze, zero network delay)
        self.reload_files()

        # 3. Trigger Background Telegram Sync (Tagged with request_id for stale cancellation)
        self._start_automatic_indexing(chat, req_id)

    def _render_header_avatar(self, chat: TelegramChat) -> QPixmap:
        size = 40
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        path = QPainterPath()
        path.addEllipse(0, 0, size, size)
        painter.setClipPath(path)

        if chat.avatar_path and Path(chat.avatar_path).exists():
            img = QPixmap(chat.avatar_path)
            if not img.isNull():
                painter.drawPixmap(0, 0, size, size, img.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
                painter.end()
                return pixmap

        palette = ["#5C8DFF", "#3DDC84", "#F5A623", "#A855F7", "#F1554C", "#7AA2FF"]
        bg_color = QColor(palette[abs(chat.id) % len(palette)])

        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.NoPen)
        painter.drawRect(0, 0, size, size)

        initial = (chat.display_name or "?")[0].upper()
        painter.setPen(QColor("#FFFFFF"))
        font = QFont("Inter", 13)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(QRectF(0, 0, size, size), Qt.AlignCenter, initial)

        painter.end()
        return pixmap

    def reload_files(self):
        """Synchronously query SQLite local cache for instantaneous rendering."""
        if not self.current_chat:
            self.view_stack.setCurrentIndex(2)
            return

        category = self._current_category
        if self._filter_criteria.media_type:
            category = self._filter_criteria.media_type

        self._cached_files, total_count = self.search_service.search_files(
            query_text=self._search_query,
            chat_id=self.current_chat.id,
            media_type=category,
            extension=self._filter_criteria.extension,
            min_size=self._filter_criteria.min_size_bytes,
            max_size=self._filter_criteria.max_size_bytes,
            start_date=self._filter_criteria.start_date,
            end_date=self._filter_criteria.end_date,
            sort_by=self._sort_by,
            sort_desc=self._sort_desc,
            limit=500,
            offset=0,
        )

        self._render_current_view()
        self.count_label.setText(f"{total_count} files")

    def _render_current_view(self):
        """Render files instantly via virtualized QListView."""
        if not self._cached_files:
            self.media_model.clear()
            if self._search_query or self._current_category:
                self.empty_title.setText("No files found")
                self.empty_desc.setText("Try a different filename, filter, or date range.")
            else:
                self.empty_title.setText("No media found")
                self.empty_desc.setText("This chat doesn't contain any accessible files or media.")
            self.view_stack.setCurrentIndex(2)
            return

        # Virtual model update (instant, <1ms)
        self.media_model.set_files(self._cached_files)

        current_mode = 0 if self.btn_grid_view.isChecked() else 1
        self.view_stack.setCurrentIndex(current_mode)

    def _set_view_mode(self, mode_index: int):
        """Toggle between Grid (0) and List (1)."""
        self.btn_grid_view.setChecked(mode_index == 0)
        self.btn_list_view.setChecked(mode_index == 1)
        if self._cached_files:
            self.view_stack.setCurrentIndex(mode_index)
        else:
            self.view_stack.setCurrentIndex(2)

    def _start_automatic_indexing(self, chat: TelegramChat, req_id: int):
        """Progressively retrieve media in background; stale requests are silently dropped."""
        if not self.indexer_service:
            return

        chat_id = chat.id
        if chat_id in self._active_indexing_chats:
            return

        self._active_indexing_chats.add(chat_id)
        self.status_label.setText("Checking for new media...")

        def on_batch_discovered(batch):
            # STALE REQUEST CHECK: Drop result if user switched to another chat
            if req_id != self._current_request_id:
                return

            if self.current_chat and self.current_chat.id == chat_id:
                # Append to virtual model without resetting view or jumping scroll!
                self.media_model.append_files(batch)
                self._cached_files = self.media_model.get_all_files()
                self.count_label.setText(f"{len(self._cached_files)} files")
                self.status_label.setText(f"Loading media... ({len(self._cached_files)} files)")

                # If view was showing empty state, swap to grid view
                if self.view_stack.currentIndex() == 2 and self._cached_files:
                    current_mode = 0 if self.btn_grid_view.isChecked() else 1
                    self.view_stack.setCurrentIndex(current_mode)

                # Fetch thumbnails in background tagged with req_id
                self._fetch_batch_thumbnails(batch, chat_id, req_id)

        def on_complete(result):
            self._active_indexing_chats.discard(chat_id)
            if req_id != self._current_request_id:
                return
            if self.current_chat and self.current_chat.id == chat_id:
                self.status_label.setText("All media loaded")

        def on_error(exc):
            self._active_indexing_chats.discard(chat_id)
            if req_id != self._current_request_id:
                return
            logger.debug("Auto media loading interrupted for %s: %s", chat.display_name, exc)
            if self.current_chat and self.current_chat.id == chat_id:
                self.status_label.setText("Ready")

        async_runner.run_coroutine_async(
            self.indexer_service.index_chat(
                chat.id,
                chat.display_name,
                limit=500,
                batch_size=25,
                batch_discovered_callback=on_batch_discovered,
            ),
            callback=on_complete,
            error_callback=on_error,
        )

    def _fetch_batch_thumbnails(self, batch, chat_id: int, req_id: int):
        """Fetch thumbnails for batch; dropped if request_id is stale."""
        if not self.preview_service:
            return

        thumb_items = [item for item in batch if getattr(item, "has_thumbnail", False)]
        if not thumb_items:
            return

        def on_thumbs_fetched(results):
            if req_id != self._current_request_id:
                return
            if not results:
                return
            if self.indexer_service:
                self.indexer_service.update_thumbnail_paths(results)
            # Update model rows with new thumbnail paths
            for file_id, path in results.items():
                self.media_model.update_thumbnail_path(file_id, path)

        def on_thumbs_error(exc):
            logger.debug("Batch thumbnail error: %s", exc)

        async_runner.run_coroutine_async(
            self.preview_service.fetch_thumbnails_batch(thumb_items),
            callback=on_thumbs_fetched,
            error_callback=on_thumbs_error,
        )

    def _on_thumbnail_decoded(self, req_id: int, file_id: str, pixmap: QPixmap):
        """Triggered on main thread when off-thread QThreadPool finishes decoding an image."""
        if req_id != self._current_request_id:
            return
        # Trigger viewport repaint of visible items
        self.grid_view.viewport().update()
        self.list_view.viewport().update()

    def _on_view_item_clicked(self, index: QModelIndex):
        """Handle single-click selection on virtual item."""
        file_model = index.data(FileModelRole)
        if file_model:
            self.file_selected.emit(file_model)

    def _on_view_item_double_clicked(self, index: QModelIndex):
        """Handle double-click on virtual item."""
        file_model = index.data(FileModelRole)
        if file_model:
            self.file_double_clicked.emit(file_model)

    def _on_delegate_download(self, file_model: IndexedFileModel):
        self.download_requested.emit(file_model)

    def _on_delegate_open(self, file_model: IndexedFileModel):
        self.open_requested.emit(file_model)

    def _on_tab_clicked(self, category_code: Optional[str], button: QPushButton):
        for b in self.tab_buttons:
            b.setChecked(b == button)
        self._current_category = category_code
        self.reload_files()

    def _open_filter_dialog(self):
        dialog = FilterDialog(self._filter_criteria, parent=self)
        dialog.filters_applied.connect(self._on_filters_applied)
        dialog.exec()

    def _on_filters_applied(self, criteria: AdvancedFilterCriteria):
        self._filter_criteria = criteria
        self.reload_files()

    def _on_search_text_changed(self, text: str):
        self._search_query = text.strip()
        self._search_timer.start()

    def _execute_search(self):
        self.reload_files()

    def _on_sort_changed(self, index: int):
        sort_map = {
            0: ("date", True),
            1: ("date", False),
            2: ("size", True),
            3: ("size", False),
            4: ("name", False),
            5: ("name", True),
        }
        self._sort_by, self._sort_desc = sort_map.get(index, ("date", True))
        self.reload_files()

    def focus_search(self):
        self.search_input.setFocus()
        self.search_input.selectAll()
