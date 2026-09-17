"""Clean media filter dialog conforming strictly to specification (no emojis)."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .filter_bar import AdvancedFilterCriteria, SIZE_PRESETS, DATE_PRESETS


class FilterDialog(QDialog):
    """Clean filter popover dialog conforming strictly to Section 20."""

    filters_applied = Signal(object) # Emits AdvancedFilterCriteria

    def __init__(self, current_criteria: Optional[AdvancedFilterCriteria] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Filter Media")
        self.setFixedSize(380, 420)
        self.criteria = current_criteria or AdvancedFilterCriteria()
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet(
            """
            QDialog {
                background-color: #1C1C1F;
                border: 1px solid #3F3F46;
                border-radius: 12px;
            }
            QLabel {
                color: #F4F4F5;
                font-size: 13px;
                font-weight: 500;
            }
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Title
        title_label = QLabel("Filters")
        title_label.setStyleSheet("font-size: 16px; font-weight: 600; color: #F4F4F5;")
        layout.addWidget(title_label)

        # 1. Media Type Selector
        type_lbl = QLabel("Type")
        type_lbl.setStyleSheet("color: #A1A1AA; font-size: 12px; font-weight: 600;")
        layout.addWidget(type_lbl)

        self.combo_type = QComboBox()
        self.combo_type.addItems(["All Types", "Images", "Videos", "Documents", "Audio", "Other"])
        layout.addWidget(self.combo_type)

        # 2. Size Preset
        size_lbl = QLabel("Size")
        size_lbl.setStyleSheet("color: #A1A1AA; font-size: 12px; font-weight: 600;")
        layout.addWidget(size_lbl)

        self.combo_size = QComboBox()
        for label, _, _ in SIZE_PRESETS:
            self.combo_size.addItem(label)
        layout.addWidget(self.combo_size)

        # 3. Date Range
        date_lbl = QLabel("Date Range")
        date_lbl.setStyleSheet("color: #A1A1AA; font-size: 12px; font-weight: 600;")
        layout.addWidget(date_lbl)

        self.combo_date = QComboBox()
        for label, _ in DATE_PRESETS:
            self.combo_date.addItem(label)
        layout.addWidget(self.combo_date)

        # 4. Extension Filter
        ext_lbl = QLabel("Extension")
        ext_lbl.setStyleSheet("color: #A1A1AA; font-size: 12px; font-weight: 600;")
        layout.addWidget(ext_lbl)

        self.input_ext = QLineEdit()
        self.input_ext.setPlaceholderText(".pdf, .mp4, .zip...")
        layout.addWidget(self.input_ext)

        layout.addStretch()

        # Action Buttons: Reset & Apply
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.btn_reset = QPushButton("Reset")
        self.btn_reset.setObjectName("secondaryButton")
        self.btn_reset.clicked.connect(self._reset)
        btn_layout.addWidget(self.btn_reset)

        self.btn_apply = QPushButton("Apply Filters")
        self.btn_apply.setObjectName("primaryButton")
        self.btn_apply.clicked.connect(self._apply)
        btn_layout.addWidget(self.btn_apply)

        layout.addLayout(btn_layout)

    def _reset(self):
        self.combo_type.setCurrentIndex(0)
        self.combo_size.setCurrentIndex(0)
        self.combo_date.setCurrentIndex(0)
        self.input_ext.clear()
        self.criteria = AdvancedFilterCriteria()
        self.filters_applied.emit(self.criteria)
        self.accept()

    def _apply(self):
        # Type
        type_text = self.combo_type.currentText()
        type_map = {
            "Images": "IMAGE",
            "Videos": "VIDEO",
            "Documents": "DOCUMENT",
            "Audio": "AUDIO",
            "Other": "OTHER",
        }
        self.criteria.media_type = type_map.get(type_text)

        # Size
        size_idx = self.combo_size.currentIndex()
        _, min_s, max_s = SIZE_PRESETS[size_idx]
        self.criteria.min_size_bytes = min_s
        self.criteria.max_size_bytes = max_s

        # Date
        from datetime import timedelta
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

        self.filters_applied.emit(self.criteria)
        self.accept()
