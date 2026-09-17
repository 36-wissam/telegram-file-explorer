"""Desktop media grid card widget (180-220px) conforming strictly to specification (no emojis)."""

from pathlib import Path
from typing import Optional
from PySide6.QtCore import Qt, Signal, QRectF
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ..database.models import IndexedFileModel
from ..services.media_parser import MediaType


def format_bytes(size_bytes: int) -> str:
    """Format bytes to human-readable size."""
    s = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if s < 1024.0 or unit == "TB":
            return f"{s:.1f} {unit}" if unit != "B" else f"{int(s)} B"
        s /= 1024.0
    return f"{size_bytes} B"


class MediaCardWidget(QFrame):
    """File card widget for the 180-220px responsive media grid."""

    clicked = Signal(object)        # Emits IndexedFileModel
    double_clicked = Signal(object) # Emits IndexedFileModel

    def __init__(self, file_model: IndexedFileModel, parent=None):
        super().__init__(parent)
        self.file_model = file_model
        self.setFixedWidth(200)
        self.setMinimumHeight(210)
        self.setCursor(Qt.PointingHandCursor)
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet(
            """
            QFrame {
                background-color: #1C1C1F;
                border: 1px solid #3F3F46;
                border-radius: 10px;
            }
            QFrame:hover {
                border-color: #229ED9;
                background-color: #27272A;
            }
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # 1. Preview / Thumbnail Box (180x110)
        self.thumb_box = QLabel()
        self.thumb_box.setFixedSize(180, 110)
        self.thumb_box.setAlignment(Qt.AlignCenter)
        self.thumb_box.setPixmap(self._generate_thumbnail())
        layout.addWidget(self.thumb_box, alignment=Qt.AlignCenter)

        # 2. Filename
        self.name_label = QLabel(self.file_model.filename)
        name_font = QFont()
        name_font.setPointSize(12)
        name_font.setBold(True)
        self.name_label.setFont(name_font)
        self.name_label.setStyleSheet("color: #F4F4F5; background: transparent;")
        self.name_label.setWordWrap(False)
        layout.addWidget(self.name_label)

        # 3. Size and Date Meta Row
        meta_layout = QHBoxLayout()
        meta_layout.setSpacing(6)

        size_str = format_bytes(self.file_model.file_size)
        self.size_label = QLabel(size_str)
        self.size_label.setStyleSheet("color: #A1A1AA; font-size: 11px; background: transparent;")
        meta_layout.addWidget(self.size_label)

        meta_layout.addStretch()

        date_str = ""
        if self.file_model.message_date:
            date_str = self.file_model.message_date.strftime("%b %d, %Y")
        self.date_label = QLabel(date_str)
        self.date_label.setStyleSheet("color: #71717A; font-size: 11px; background: transparent;")
        meta_layout.addWidget(self.date_label)

        layout.addLayout(meta_layout)

    def _generate_thumbnail(self) -> QPixmap:
        """Render image thumbnail or format badge card."""
        w, h = 180, 110
        pixmap = QPixmap(w, h)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # Rounded rectangle path
        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, 6, 6)
        painter.setClipPath(path)

        # Try loading thumbnail image
        if self.file_model.thumbnail_path and Path(self.file_model.thumbnail_path).exists():
            img = QPixmap(self.file_model.thumbnail_path)
            if not img.isNull():
                scaled_img = img.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                painter.drawPixmap(0, 0, w, h, scaled_img)
                painter.end()
                return pixmap

        # Fallback format badge box
        painter.setBrush(QBrush(QColor("#27272A")))
        painter.setPen(Qt.NoPen)
        painter.drawRect(0, 0, w, h)

        # Format label (PDF, MP4, ZIP, PNG, etc.)
        ext = (self.file_model.extension or "").replace(".", "").upper()
        if not ext:
            ext = self.file_model.media_type[:3].upper()

        painter.setPen(QColor("#229ED9"))
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(QRectF(0, 0, w, h), Qt.AlignCenter, ext)

        painter.end()
        return pixmap

    def mousePressEvent(self, event):
        if hasattr(event, "button") and event.button() == Qt.LeftButton:
            self.clicked.emit(self.file_model)
        try:
            super().mousePressEvent(event)
        except (TypeError, RuntimeError):
            pass

    def mouseDoubleClickEvent(self, event):
        if hasattr(event, "button") and event.button() == Qt.LeftButton:
            self.double_clicked.emit(self.file_model)
        try:
            super().mouseDoubleClickEvent(event)
        except (TypeError, RuntimeError):
            pass
