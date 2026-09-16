"""Modern desktop file explorer interface for Telegram File Explorer."""

from datetime import datetime
from typing import List, Optional
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QFont, QIcon, QColor
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.logger import get_logger
from ..database.models import IndexedFileModel
from ..database.repository import DatabaseRepository
from ..services.media_parser import MediaType

logger = get_logger("ui.file_explorer")

CATEGORY_ICONS = {
    "ALL": "📁",
    "IMAGE": "🖼️",
    "VIDEO": "🎬",
    "AUDIO": "🎵",
    "VOICE": "🎤",
    "DOCUMENT": "📄",
    "ARCHIVE": "📦",
    "OTHER": "📎",
}


def format_bytes(size_bytes: int) -> str:
    """Format bytes to human-readable size."""
    s = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if s < 1024.0 or unit == "TB":
            return f"{s:.1f} {unit}" if unit != "B" else f"{int(s)} B"
        s /= 1024.0
    return f"{size_bytes} B"


class FileExplorerWidget(QWidget):
    """Desktop file manager for browsing indexed Telegram files."""

    file_selected = Signal(object)      # Emits selected IndexedFileModel
    file_double_clicked = Signal(object) # Emits on open/download action

    def __init__(self, repo: DatabaseRepository, parent=None):
        super().__init__(parent)
        self.repo = repo
        from ..services.search import SearchEngineService
        self.search_service = SearchEngineService(self.repo)
        self._current_category: Optional[str] = None
        self._current_chat_id: Optional[int] = None
        self._search_query: str = ""
        self._sort_by: str = "date"
        self._sort_desc: bool = True
        self._page: int = 0
        self._page_size: int = 50
        self._total_files: int = 0
        self._cached_files: List[IndexedFileModel] = []

        self._init_ui()
        self.reload_files()


    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Top Navigation & Search Toolbar
        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)

        # Splitter: Sidebar (Categories & Chats) + Central Table View
        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet(
            """
            QSplitter::handle {
                background-color: #2b2d31;
                width: 1px;
            }
            """
        )

        # Left Explorer Sidebar
        self.sidebar = self._create_sidebar()
        splitter.addWidget(self.sidebar)

        # Center Content: File Table + Pagination Bar
        content_pane = self._create_content_pane()
        splitter.addWidget(content_pane)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)

    def _create_toolbar(self) -> QWidget:
        toolbar = QFrame(self)
        toolbar.setStyleSheet(
            """
            QFrame {
                background-color: #1e1f22;
                border-bottom: 1px solid #2b2d31;
                padding: 6px 12px;
            }
            """
        )
        t_layout = QHBoxLayout(toolbar)
        t_layout.setContentsMargins(8, 4, 8, 4)
        t_layout.setSpacing(12)

        # Search Bar
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Search files by name, caption, chat...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setFixedWidth(340)
        self.search_input.textChanged.connect(self._on_search_changed)
        t_layout.addWidget(self.search_input)

        t_layout.addStretch()

        # Sort Dropdown
        sort_label = QLabel("Sort by:")
        sort_label.setStyleSheet("color: #949ba4; font-size: 12px;")
        t_layout.addWidget(sort_label)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems([
            "Date (Newest First)",
            "Date (Oldest First)",
            "Size (Largest First)",
            "Size (Smallest First)",
            "Name (A to Z)",
            "Name (Z to A)",
        ])
        self.sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        t_layout.addWidget(self.sort_combo)

        # Refresh Button
        self.btn_refresh = QPushButton("🔄 Refresh")
        self.btn_refresh.clicked.connect(self.reload_files)
        t_layout.addWidget(self.btn_refresh)

        return toolbar

    def _create_sidebar(self) -> QWidget:
        sidebar = QFrame(self)
        sidebar.setMinimumWidth(220)
        sidebar.setMaximumWidth(280)
        sidebar.setStyleSheet(
            """
            QFrame {
                background-color: #18191c;
                border-right: 1px solid #2b2d31;
            }
            """
        )
        s_layout = QVBoxLayout(sidebar)
        s_layout.setContentsMargins(10, 12, 10, 12)
        s_layout.setSpacing(8)

        section_title = QLabel("CATEGORIES")
        section_title.setStyleSheet("color: #949ba4; font-size: 11px; font-weight: bold; padding-left: 4px;")
        s_layout.addWidget(section_title)

        self.category_tree = QTreeWidget()
        self.category_tree.setHeaderHidden(True)
        self.category_tree.setStyleSheet(
            """
            QTreeWidget {
                background-color: transparent;
                border: none;
                font-size: 13px;
            }
            QTreeWidget::item {
                padding: 6px 8px;
                border-radius: 6px;
                margin-bottom: 2px;
            }
            QTreeWidget::item:selected {
                background-color: #35373c;
                color: #ffffff;
            }
            QTreeWidget::item:hover:!selected {
                background-color: #232428;
            }
            """
        )

        categories = [
            ("ALL", "📁 All Files"),
            ("IMAGE", "🖼️ Images & Photos"),
            ("VIDEO", "🎬 Videos & Clips"),
            ("AUDIO", "🎵 Audio & Music"),
            ("VOICE", "🎤 Voice Notes"),
            ("DOCUMENT", "📄 Documents & PDFs"),
            ("ARCHIVE", "📦 Archives & Zips"),
            ("OTHER", "📎 Other Media"),
        ]

        for code, label in categories:
            item = QTreeWidgetItem([label])
            item.setData(0, Qt.UserRole, code)
            self.category_tree.addTopLevelItem(item)

        self.category_tree.itemClicked.connect(self._on_category_clicked)
        # Select "All Files" initially
        self.category_tree.setCurrentItem(self.category_tree.topLevelItem(0))
        s_layout.addWidget(self.category_tree)

        return sidebar

    def _create_content_pane(self) -> QWidget:
        pane = QWidget(self)
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        inner_splitter = QSplitter(Qt.Horizontal)
        inner_splitter.setStyleSheet("QSplitter::handle { background-color: #2b2d31; width: 1px; }")

        # Center Column: Table + Pagination Footer
        table_container = QWidget()
        tc_layout = QVBoxLayout(table_container)
        tc_layout.setContentsMargins(0, 0, 0, 0)
        tc_layout.setSpacing(0)

        # File List Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Name", "Source Chat", "Type", "Size", "Date"])
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
                background-color: #1e1f22;
                alternate-background-color: #232428;
                border: none;
                gridline-color: transparent;
                selection-background-color: #35373c;
                font-size: 13px;
            }
            QTableWidget::item {
                padding: 6px 10px;
                border: none;
            }
            QHeaderView::section {
                background-color: #18191c;
                color: #949ba4;
                border: none;
                border-bottom: 1px solid #2b2d31;
                padding: 6px 10px;
                font-weight: bold;
                font-size: 11px;
            }
            """
        )
        self.table.itemSelectionChanged.connect(self._on_table_selection_changed)
        self.table.itemDoubleClicked.connect(self._on_table_double_clicked)
        tc_layout.addWidget(self.table)

        # Pagination & Summary Footer
        footer = QFrame()
        footer.setStyleSheet(
            """
            QFrame {
                background-color: #18191c;
                border-top: 1px solid #2b2d31;
                padding: 4px 12px;
            }
            """
        )
        f_layout = QHBoxLayout(footer)
        f_layout.setContentsMargins(8, 6, 8, 6)

        self.summary_label = QLabel("0 files indexed")
        self.summary_label.setStyleSheet("color: #949ba4; font-size: 12px;")
        f_layout.addWidget(self.summary_label)

        f_layout.addStretch()

        # Pagination Controls
        self.btn_prev_page = QPushButton("◀ Previous")
        self.btn_prev_page.clicked.connect(self._prev_page)
        f_layout.addWidget(self.btn_prev_page)

        self.page_label = QLabel("Page 1 of 1")
        self.page_label.setStyleSheet("color: #dbdee1; font-size: 12px; padding: 0 8px;")
        f_layout.addWidget(self.page_label)

        self.btn_next_page = QPushButton("Next ▶")
        self.btn_next_page.clicked.connect(self._next_page)
        f_layout.addWidget(self.btn_next_page)

        tc_layout.addWidget(footer)
        inner_splitter.addWidget(table_container)

        # Right Inspector: Preview Panel
        from .preview_panel import PreviewPanel
        self.preview_panel = PreviewPanel()
        inner_splitter.addWidget(self.preview_panel)

        inner_splitter.setStretchFactor(0, 1)
        inner_splitter.setStretchFactor(1, 0)

        layout.addWidget(inner_splitter)
        return pane


    def set_chat_filter(self, chat_id: Optional[int]):
        """Filter files for a specific chat."""
        self._current_chat_id = chat_id
        self._page = 0
        self.reload_files()

    def reload_files(self):
        """Fetch files using FTS5 search service with active filters and render table."""
        category = self._current_category if self._current_category != "ALL" else None
        offset = self._page * self._page_size

        self._cached_files, self._total_files = self.search_service.search_files(
            query_text=self._search_query,
            chat_id=self._current_chat_id,
            media_type=category,
            sort_by=self._sort_by,
            sort_desc=self._sort_desc,
            limit=self._page_size,
            offset=offset,
        )

        self._render_table()
        self._update_pagination()


    def _render_table(self):
        """Populate table with fetched files."""
        self.table.setRowCount(0)
        self.table.setRowCount(len(self._cached_files))

        for row, file_item in enumerate(self._cached_files):
            # Filename with category icon
            icon = CATEGORY_ICONS.get(file_item.media_type, "📎")
            name_item = QTableWidgetItem(f"{icon}  {file_item.filename}")
            name_item.setData(Qt.UserRole, file_item)
            self.table.setItem(row, 0, name_item)

            # Chat title
            chat_item = QTableWidgetItem(file_item.chat_title or "Unknown")
            chat_item.setForeground(QColor("#949ba4"))
            self.table.setItem(row, 1, chat_item)

            # Media Type
            type_item = QTableWidgetItem(file_item.media_type)
            type_item.setForeground(QColor("#00aff4"))
            self.table.setItem(row, 2, type_item)

            # Size
            size_str = format_bytes(file_item.file_size)
            size_item = QTableWidgetItem(size_str)
            size_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, 3, size_item)

            # Date
            date_str = file_item.message_date.strftime("%Y-%m-%d %H:%M") if file_item.message_date else "-"
            date_item = QTableWidgetItem(date_str)
            date_item.setForeground(QColor("#949ba4"))
            self.table.setItem(row, 4, date_item)

    def _update_pagination(self):
        """Update pagination button states and labels."""
        total_pages = max(1, (self._total_files + self._page_size - 1) // self._page_size)
        current_page = min(self._page + 1, total_pages)

        self.page_label.setText(f"Page {current_page} of {total_pages}")
        self.btn_prev_page.setEnabled(self._page > 0)
        self.btn_next_page.setEnabled(current_page < total_pages)

        cat_str = self._current_category or "All"
        self.summary_label.setText(f"Showing {len(self._cached_files)} of {self._total_files} files ({cat_str})")

    def _next_page(self):
        total_pages = (self._total_files + self._page_size - 1) // self._page_size
        if self._page + 1 < total_pages:
            self._page += 1
            self.reload_files()

    def _prev_page(self):
        if self._page > 0:
            self._page -= 1
            self.reload_files()

    def _on_category_clicked(self, item: QTreeWidgetItem):
        code = item.data(0, Qt.UserRole)
        self._current_category = code
        self._page = 0
        self.reload_files()

    def _on_search_changed(self, text: str):
        self._search_query = text.strip()
        self._page = 0
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
        self._page = 0
        self.reload_files()

    def _on_table_selection_changed(self):
        selected_rows = self.table.selectedItems()
        if selected_rows:
            first_item = self.table.item(selected_rows[0].row(), 0)
            file_item = first_item.data(Qt.UserRole)
            self.file_selected.emit(file_item)
            self.preview_panel.set_file(file_item)
        else:
            self.preview_panel.set_file(None)

    def _on_table_double_clicked(self, item: QTableWidgetItem):
        first_item = self.table.item(item.row(), 0)
        file_item = first_item.data(Qt.UserRole)
        self.file_double_clicked.emit(file_item)
        if file_item:
            from .preview_panel import PreviewDialog
            dialog = PreviewDialog(file_item, parent=self)
            dialog.exec()

