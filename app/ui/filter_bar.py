"""Advanced filtering panel for File Explorer."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..core.logger import get_logger

logger = get_logger("ui.filter_bar")


@dataclass
class AdvancedFilterCriteria:
    """Holds all combined filter parameters."""
    search_query: str = ""
    media_type: Optional[str] = None
    extension: Optional[str] = None
    chat_id: Optional[int] = None
    min_size_bytes: Optional[int] = None
    max_size_bytes: Optional[int] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    sort_by: str = "date"
    sort_desc: bool = True


SIZE_PRESETS = [
    ("Any Size", None, None),
    ("< 1 MB", 0, 1024 * 1024),
    ("1 MB - 10 MB", 1024 * 1024, 10 * 1024 * 1024),
    ("10 MB - 100 MB", 10 * 1024 * 1024, 100 * 1024 * 1024),
    ("100 MB - 1 GB", 100 * 1024 * 1024, 1024 * 1024 * 1024),
    ("> 1 GB", 1024 * 1024 * 1024, None),
]

DATE_PRESETS = [
    ("All Time", None),
    ("Past 24 Hours", 1),
    ("Past 7 Days", 7),
    ("Past 30 Days", 30),
    ("Past 1 Year", 365),
]


class AdvancedFilterBar(QWidget):
    """Collapsible / dockable advanced filter bar for FileExplorerWidget."""

    filters_changed = Signal(object)  # Emits AdvancedFilterCriteria

    def __init__(self, parent=None):
        super().__init__(parent)
        self.criteria = AdvancedFilterCriteria()
        self._chats_cache = []
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 8, 12, 8)
        main_layout.setSpacing(8)

        self.container = QFrame(self)
        self.container.setStyleSheet(
            """
            QFrame {
                background-color: #1e1f22;
                border: 1px solid #2b2d31;
                border-radius: 6px;
                padding: 10px;
            }
            """
        )
        grid = QGridLayout(self.container)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(10)

        # 1. Size Preset Filter
        grid.addWidget(QLabel("<b>File Size:</b>"), 0, 0)
        self.combo_size = QComboBox()
        for label, _, _ in SIZE_PRESETS:
            self.combo_size.addItem(label)
        self.combo_size.currentIndexChanged.connect(self._on_filter_changed)
        grid.addWidget(self.combo_size, 0, 1)

        # 2. Date Range Filter
        grid.addWidget(QLabel("<b>Date Range:</b>"), 0, 2)
        self.combo_date = QComboBox()
        for label, _ in DATE_PRESETS:
            self.combo_date.addItem(label)
        self.combo_date.currentIndexChanged.connect(self._on_filter_changed)
        grid.addWidget(self.combo_date, 0, 3)

        # 3. Extension Filter
        grid.addWidget(QLabel("<b>Extension:</b>"), 1, 0)
        self.input_ext = QLineEdit()
        self.input_ext.setPlaceholderText("e.g. .pdf, .zip, .mp4")
        self.input_ext.textChanged.connect(self._on_filter_changed)
        grid.addWidget(self.input_ext, 1, 1)

        # 4. Source Chat Filter
        grid.addWidget(QLabel("<b>Source Chat:</b>"), 1, 2)
        self.combo_chat = QComboBox()
        self.combo_chat.addItem("All Chats", None)
        self.combo_chat.currentIndexChanged.connect(self._on_filter_changed)
        grid.addWidget(self.combo_chat, 1, 3)

        # 5. Sorting Controls & Reset Button
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.combo_sort_field = QComboBox()
        self.combo_sort_field.addItems(["Date", "Name", "Size"])
        self.combo_sort_field.currentIndexChanged.connect(self._on_filter_changed)
        btn_layout.addWidget(QLabel("<b>Sort:</b>"))
        btn_layout.addWidget(self.combo_sort_field)

        self.combo_sort_dir = QComboBox()
        self.combo_sort_dir.addItems(["Descending (▼)", "Ascending (▲)"])
        self.combo_sort_dir.currentIndexChanged.connect(self._on_filter_changed)
        btn_layout.addWidget(self.combo_sort_dir)

        btn_layout.addStretch()

        self.btn_reset = QPushButton("Reset All Filters")
        self.btn_reset.setStyleSheet("padding: 4px 12px; font-size: 11px;")
        self.btn_reset.clicked.connect(self.reset_filters)
        btn_layout.addWidget(self.btn_reset)

        grid.addLayout(btn_layout, 2, 0, 1, 4)
        main_layout.addWidget(self.container)

    def populate_chats(self, chats: List[Dict]):
        """Populate the chat dropdown list."""
        self._chats_cache = chats
        current_data = self.combo_chat.currentData()
        self.combo_chat.blockSignals(True)
        self.combo_chat.clear()
        self.combo_chat.addItem("All Chats", None)
        for c in chats:
            name = c.get("title") or f"Chat {c.get('id')}"
            self.combo_chat.addItem(name, c.get("id"))

        # Restore selection if possible
        idx = self.combo_chat.findData(current_data)
        if idx >= 0:
            self.combo_chat.setCurrentIndex(idx)
        self.combo_chat.blockSignals(False)

    def reset_filters(self):
        """Reset all inputs to default settings."""
        self.blockSignals(True)
        self.combo_size.setCurrentIndex(0)
        self.combo_date.setCurrentIndex(0)
        self.input_ext.clear()
        self.combo_chat.setCurrentIndex(0)
        self.combo_sort_field.setCurrentIndex(0)
        self.combo_sort_dir.setCurrentIndex(0)
        self.blockSignals(False)
        self._on_filter_changed()

    def _on_filter_changed(self):
        """Gather current criteria and emit signal."""
        # Size
        size_idx = self.combo_size.currentIndex()
        _, min_s, max_s = SIZE_PRESETS[size_idx]
        self.criteria.min_size_bytes = min_s
        self.criteria.max_size_bytes = max_s

        # Date
        date_idx = self.combo_date.currentIndex()
        _, days = DATE_PRESETS[date_idx]
        if days:
            self.criteria.start_date = datetime.now(timezone.utc) - timedelta(days=days)
        else:
            self.criteria.start_date = None

        # Extension
        raw_ext = self.input_ext.text().strip().lower()
        if raw_ext:
            self.criteria.extension = raw_ext if raw_ext.startswith(".") else f".{raw_ext}"
        else:
            self.criteria.extension = None

        # Source Chat
        self.criteria.chat_id = self.combo_chat.currentData()

        # Sorting
        field_map = {0: "date", 1: "name", 2: "size"}
        self.criteria.sort_by = field_map.get(self.combo_sort_field.currentIndex(), "date")
        self.criteria.sort_desc = (self.combo_sort_dir.currentIndex() == 0)

        self.filters_changed.emit(self.criteria)
