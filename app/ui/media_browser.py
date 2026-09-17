"""Chat media browser widget supporting automatic progressive media loading, Grid/List view, and search."""

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from PySide6.QtCore import Qt, Signal, QSize, QTimer, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPixmap, QBrush
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.async_runner import async_runner
from ..core.logger import get_logger
from ..database.models import IndexedFileModel
from ..database.repository import DatabaseRepository
from ..services.indexer import MediaIndexerService
from ..services.media_parser import MediaType
from ..services.search import SearchEngineService
from ..telegram.chats import ChatType, TelegramChat
from .filter_bar import AdvancedFilterCriteria
from .filter_dialog import FilterDialog
from .media_card import MediaCardWidget, format_bytes

logger = get_logger("ui.media_browser")

MEDIA_TABS = [
    ("All", None),
    ("Images", "IMAGE"),
    ("Videos", "VIDEO"),
    ("Documents", "DOCUMENT"),
    ("Audio", "AUDIO"),
    ("Other", "OTHER"),
]


class ChatMediaBrowserWidget(QWidget):
    """Main Content pane displaying chat header, media tabs, Grid/List views, and progressive loading."""

    file_selected = Signal(object)        # Emits IndexedFileModel
    file_double_clicked = Signal(object) # Emits IndexedFileModel

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
        self._is_loading: bool = False

        # Debounce timer for instant search
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(200)
        self._search_timer.timeout.connect(self._execute_search)

        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("background-color: #111113;")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Chat Header Section
        self.header_card = self._create_chat_header()
        main_layout.addWidget(self.header_card)

        # 2. Media Tabs Navigation Bar
        self.tabs_bar = self._create_tabs_bar()
        main_layout.addWidget(self.tabs_bar)

        # 3. View Switcher & Filter Toolbar
        self.toolbar = self._create_toolbar()
        main_layout.addWidget(self.toolbar)

        # 4. Main View Canvas (Stack: 0 = Grid, 1 = List, 2 = Empty state)
        self.view_stack = QStackedWidget(self)

        # Page 0: Grid View (Scroll Area)
        self.grid_scroll = QScrollArea()
        self.grid_scroll.setWidgetResizable(True)
        self.grid_scroll.setStyleSheet("background-color: #111113; border: none;")
        self.grid_container = QWidget()
        self.grid_container.setStyleSheet("background-color: #111113;")
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(24, 16, 24, 24)
        self.grid_layout.setSpacing(16)
        self.grid_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.grid_scroll.setWidget(self.grid_container)
        self.view_stack.addWidget(self.grid_scroll)

        # Page 1: List View (Table Widget)
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Name", "Type", "Size", "Source", "Date"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setStyleSheet(
            """
            QTableWidget {
                background-color: #111113;
                alternate-background-color: #18181B;
                border: none;
                gridline-color: transparent;
                selection-background-color: #27272A;
                font-size: 13px;
                outline: none;
            }
            QTableWidget::item {
                padding: 10px 14px;
                border-bottom: 1px solid #1C1C1F;
                color: #F4F4F5;
            }
            QTableWidget::item:selected {
                background-color: #27272A;
                color: #229ED9;
            }
            QHeaderView::section {
                background-color: #18181B;
                color: #A1A1AA;
                border: none;
                border-bottom: 1px solid #3F3F46;
                padding: 8px 14px;
                font-weight: 600;
                font-size: 12px;
            }
            """
        )
        self.table.itemSelectionChanged.connect(self._on_table_selection_changed)
        self.table.itemDoubleClicked.connect(self._on_table_double_clicked)
        self.view_stack.addWidget(self.table)

        # Page 2: Empty State Card
        self.empty_card = QFrame()
        self.empty_card.setStyleSheet("background-color: #111113; border: none;")
        empty_layout = QVBoxLayout(self.empty_card)
        empty_layout.setAlignment(Qt.AlignCenter)
        empty_layout.setSpacing(12)

        self.empty_title = QLabel("Select a chat to view files")
        self.empty_title.setStyleSheet("font-size: 18px; font-weight: 600; color: #F4F4F5;")
        self.empty_title.setAlignment(Qt.AlignCenter)
        empty_layout.addWidget(self.empty_title)

        self.empty_desc = QLabel("Choose a dialogue from the left sidebar to automatically browse shared media.")
        self.empty_desc.setStyleSheet("font-size: 13px; color: #71717A; max-width: 440px;")
        self.empty_desc.setAlignment(Qt.AlignCenter)
        self.empty_desc.setWordWrap(True)
        empty_layout.addWidget(self.empty_desc)
        self.view_stack.addWidget(self.empty_card)

        self.view_stack.setCurrentIndex(2) # Default empty
        main_layout.addWidget(self.view_stack)

        # 5. Progressive Loading Status Banner at the bottom
        self.status_banner = QFrame()
        self.status_banner.setFixedHeight(36)
        self.status_banner.setStyleSheet(
            """
            QFrame {
                background-color: #18181B;
                border-top: 1px solid #3F3F46;
                padding: 4px 16px;
            }
            """
        )
        sb_layout = QHBoxLayout(self.status_banner)
        sb_layout.setContentsMargins(16, 4, 16, 4)

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #A1A1AA; font-size: 12px; font-weight: 500;")
        sb_layout.addWidget(self.status_label)

        sb_layout.addStretch()

        self.count_label = QLabel("0 files")
        self.count_label.setStyleSheet("color: #71717A; font-size: 12px;")
        sb_layout.addWidget(self.count_label)

        main_layout.addWidget(self.status_banner)

    def _create_chat_header(self) -> QWidget:
        header = QFrame(self)
        header.setFixedHeight(72)
        header.setStyleSheet(
            """
            QFrame {
                background-color: #18181B;
                border-bottom: 1px solid #3F3F46;
                padding: 8px 24px;
            }
            """
        )
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(24, 8, 24, 8)
        h_layout.setSpacing(14)

        # Avatar
        self.avatar_label = QLabel()
        self.avatar_label.setFixedSize(48, 48)
        h_layout.addWidget(self.avatar_label)

        # Text Details (Name + Username/Type)
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        text_layout.setAlignment(Qt.AlignVCenter)

        self.title_label = QLabel("No Chat Selected")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.title_label.setStyleSheet("color: #F4F4F5;")
        text_layout.addWidget(self.title_label)

        self.subtitle_label = QLabel("Select a chat to begin")
        self.subtitle_label.setStyleSheet("color: #A1A1AA; font-size: 12px;")
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
                background-color: #18181B;
                border-bottom: 1px solid #3F3F46;
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
            btn.setObjectName("mediaTabButton")
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
                background-color: #111113;
                border-bottom: 1px solid #1C1C1F;
                padding: 4px 24px;
            }
            """
        )
        t_layout = QHBoxLayout(toolbar)
        t_layout.setContentsMargins(24, 6, 24, 6)
        t_layout.setSpacing(12)

        # View Toggle: Grid / List
        self.btn_grid_view = QPushButton("Grid")
        self.btn_grid_view.setObjectName("secondaryButton")
        self.btn_grid_view.setCheckable(True)
        self.btn_grid_view.setChecked(True)
        self.btn_grid_view.clicked.connect(lambda: self._set_view_mode(0))
        t_layout.addWidget(self.btn_grid_view)

        self.btn_list_view = QPushButton("List")
        self.btn_list_view.setObjectName("secondaryButton")
        self.btn_list_view.setCheckable(True)
        self.btn_list_view.setChecked(False)
        self.btn_list_view.clicked.connect(lambda: self._set_view_mode(1))
        t_layout.addWidget(self.btn_list_view)

        # Filters Button (Opens clean dialog)
        self.btn_filter = QPushButton("Filters")
        self.btn_filter.setObjectName("secondaryButton")
        self.btn_filter.clicked.connect(self._open_filter_dialog)
        t_layout.addWidget(self.btn_filter)

        t_layout.addStretch()

        # Sort Dropdown
        sort_label = QLabel("Sort:")
        sort_label.setStyleSheet("color: #71717A; font-size: 12px;")
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
        """Select a chat, immediately display header & cached files, then start progressive background retrieval."""
        self.current_chat = chat
        if not chat:
            self.title_label.setText("No Chat Selected")
            self.subtitle_label.setText("Select a chat to begin")
            self.avatar_label.setPixmap(QPixmap())
            self.view_stack.setCurrentIndex(2)
            self.status_label.setText("Ready")
            self.count_label.setText("0 files")
            return

        # 1. Update Chat Header
        self.title_label.setText(chat.display_name)
        subtitle_parts = []
        if chat.username:
            subtitle_parts.append(f"@{chat.username}")
        subtitle_parts.append(chat.chat_type.value)
        self.subtitle_label.setText(" · ".join(subtitle_parts))
        self.avatar_label.setPixmap(self._render_header_avatar(chat))

        # 2. Load Local Cached Files Immediately
        self.reload_files()

        # 3. Start Automatic Background Retrieval from Telegram
        self._start_automatic_indexing(chat)

    def _render_header_avatar(self, chat: TelegramChat) -> QPixmap:
        size = 48
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

        color_seed = abs(chat.id) % 6
        palette = ["#229ED9", "#22C55E", "#F59E0B", "#A855F7", "#EF4444", "#3AAFE8"]
        bg_color = QColor(palette[color_seed])

        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.NoPen)
        painter.drawRect(0, 0, size, size)

        initial = (chat.display_name or "?")[0].upper()
        painter.setPen(QColor("#FFFFFF"))
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(QRectF(0, 0, size, size), Qt.AlignCenter, initial)

        painter.end()
        return pixmap

    def reload_files(self):
        """Fetch matching files from database for the active chat and active filters."""
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
            limit=200,
            offset=0,
        )

        self._render_current_view()
        self.count_label.setText(f"{total_count} files")

    def _render_current_view(self):
        """Render files in active view mode (Grid or List)."""
        if not self._cached_files:
            if self._search_query or self._current_category:
                self.empty_title.setText("No files found")
                self.empty_desc.setText("Try a different filename, filter, or date range.")
            else:
                self.empty_title.setText("No media found")
                self.empty_desc.setText("This chat doesn't contain any accessible files or media.")
            self.view_stack.setCurrentIndex(2)
            return

        # Show Grid or List
        current_mode = 0 if self.btn_grid_view.isChecked() else 1
        self.view_stack.setCurrentIndex(current_mode)

        if current_mode == 0:
            self._render_grid()
        else:
            self._render_table()

    def _render_grid(self):
        """Populate grid layout with 200px file cards."""
        # Clear existing items
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        cols = 4  # Responsive column distribution
        for i, file_item in enumerate(self._cached_files):
            row = i // cols
            col = i % cols
            card = MediaCardWidget(file_item)
            card.clicked.connect(self.file_selected.emit)
            card.double_clicked.connect(self.file_double_clicked.emit)
            self.grid_layout.addWidget(card, row, col)

    def _render_table(self):
        """Populate list view table with file records."""
        self.table.setRowCount(0)
        self.table.setRowCount(len(self._cached_files))

        for row, file_item in enumerate(self._cached_files):
            self.table.setRowHeight(row, 44)

            name_item = QTableWidgetItem(file_item.filename)
            name_item.setData(Qt.UserRole, file_item)
            name_font = QFont()
            name_font.setBold(True)
            name_item.setFont(name_font)
            self.table.setItem(row, 0, name_item)

            type_item = QTableWidgetItem(file_item.media_type)
            type_item.setForeground(QColor("#229ED9"))
            self.table.setItem(row, 1, type_item)

            size_str = format_bytes(file_item.file_size)
            size_item = QTableWidgetItem(size_str)
            size_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, 2, size_item)

            source_item = QTableWidgetItem(file_item.chat_title or "Unknown")
            source_item.setForeground(QColor("#A1A1AA"))
            self.table.setItem(row, 3, source_item)

            date_str = file_item.message_date.strftime("%b %d, %Y %H:%M") if file_item.message_date else "-"
            date_item = QTableWidgetItem(date_str)
            date_item.setForeground(QColor("#71717A"))
            self.table.setItem(row, 4, date_item)

    def _start_automatic_indexing(self, chat: TelegramChat):
        """Progressively retrieve media in background without manual indexing buttons."""
        if not self.indexer_service:
            return

        self._is_loading = True
        self.status_label.setText("Loading media…")

        def on_batch_discovered(batch):
            # Safe callback when a batch is parsed
            self.reload_files()
            self.status_label.setText(f"Loading older media… ({len(self._cached_files)} files)")

        def on_complete(result):
            self._is_loading = False
            self.reload_files()
            self.status_label.setText("All available media loaded")

        def on_error(exc):
            self._is_loading = False
            logger.warning("Auto media loading interrupted: %s", exc)
            self.status_label.setText("Media load complete")

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

    def _on_tab_clicked(self, category_code: Optional[str], button: QPushButton):
        """Handle media navigation tab selection."""
        for b in self.tab_buttons:
            b.setChecked(b == button)
        self._current_category = category_code
        self.reload_files()

    def _set_view_mode(self, mode_index: int):
        """Toggle between Grid (0) and List (1)."""
        self.btn_grid_view.setChecked(mode_index == 0)
        self.btn_list_view.setChecked(mode_index == 1)
        self._render_current_view()

    def _open_filter_dialog(self):
        """Open clean filter dialog."""
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

    def _on_table_selection_changed(self):
        selected = self.table.selectedItems()
        if selected:
            first_item = self.table.item(selected[0].row(), 0)
            file_item = first_item.data(Qt.UserRole)
            self.file_selected.emit(file_item)

    def _on_table_double_clicked(self, item: QTableWidgetItem):
        first_item = self.table.item(item.row(), 0)
        file_item = first_item.data(Qt.UserRole)
        self.file_double_clicked.emit(file_item)

    def focus_search(self):
        self.search_input.setFocus()
        self.search_input.selectAll()
