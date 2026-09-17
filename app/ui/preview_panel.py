"""File preview panel and preview modal dialog for PySide6."""

from pathlib import Path
from typing import Optional
from PySide6.QtCore import Qt, Signal, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPixmap, QBrush
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..core.config import settings
from ..core.logger import get_logger
from ..database.models import IndexedFileModel
from .chat_list import TYPE_COLORS

logger = get_logger("ui.preview_panel")


class PreviewPanel(QWidget):
    """Inspector sidebar displaying detailed metadata and thumbnail of the selected file."""

    download_requested = Signal(object)  # Emits IndexedFileModel
    open_file_requested = Signal(str)   # Emits local file path

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_file: Optional[IndexedFileModel] = None
        self.setMinimumWidth(260)
        self.setMaximumWidth(360)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(14)
        layout.setAlignment(Qt.AlignTop)

        # Container Frame
        self.frame = QFrame(self)
        self.frame.setStyleSheet(
            """
            QFrame {
                background-color: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 12px;
            }
            """
        )
        f_layout = QVBoxLayout(self.frame)
        f_layout.setSpacing(12)
        f_layout.setAlignment(Qt.AlignTop)

        # Thumbnail Preview Container
        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(240, 150)
        self.thumb_label.setAlignment(Qt.AlignCenter)
        self.thumb_label.setStyleSheet(
            """
            background-color: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            color: #94a3b8;
            font-size: 12px;
            """
        )
        self.thumb_label.setText("No File Selected")
        f_layout.addWidget(self.thumb_label, alignment=Qt.AlignCenter)

        # File Name
        self.name_label = QLabel("Select a file to inspect")
        name_font = QFont()
        name_font.setPointSize(11)
        name_font.setBold(True)
        self.name_label.setFont(name_font)
        self.name_label.setStyleSheet("color: #0f172a;")
        self.name_label.setWordWrap(True)
        self.name_label.setAlignment(Qt.AlignCenter)
        f_layout.addWidget(self.name_label)

        # Media Type Badge
        self.type_badge = QLabel("")
        self.type_badge.setAlignment(Qt.AlignCenter)
        f_layout.addWidget(self.type_badge)

        # Metadata Details Box
        self.details_box = QFrame()
        self.details_box.setStyleSheet(
            """
            QFrame {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                padding: 10px;
            }
            QLabel {
                color: #334155;
            }
            """
        )
        d_layout = QVBoxLayout(self.details_box)
        d_layout.setSpacing(6)

        self.size_label = QLabel("<b>Size:</b> -")
        self.size_label.setStyleSheet("font-size: 12px;")
        d_layout.addWidget(self.size_label)

        self.date_label = QLabel("<b>Date:</b> -")
        self.date_label.setStyleSheet("font-size: 12px;")
        d_layout.addWidget(self.date_label)

        self.chat_label = QLabel("<b>Chat:</b> -")
        self.chat_label.setStyleSheet("font-size: 12px;")
        d_layout.addWidget(self.chat_label)

        self.mime_label = QLabel("<b>Format:</b> -")
        self.mime_label.setStyleSheet("font-size: 12px;")
        d_layout.addWidget(self.mime_label)

        self.caption_label = QLabel("")
        self.caption_label.setStyleSheet("font-size: 11px; color: #64748b;")
        self.caption_label.setWordWrap(True)
        d_layout.addWidget(self.caption_label)

        f_layout.addWidget(self.details_box)

        # Action Buttons
        self.btn_download = QPushButton("⬇ Download File")
        self.btn_download.setObjectName("primaryButton")
        self.btn_download.clicked.connect(self._on_download_clicked)
        self.btn_download.setEnabled(False)
        f_layout.addWidget(self.btn_download)

        self.btn_open = QPushButton("↗ Open in System App")
        self.btn_open.clicked.connect(self._on_open_clicked)
        self.btn_open.setVisible(False)
        f_layout.addWidget(self.btn_open)

        layout.addWidget(self.frame)
        layout.addStretch()

    def set_file(self, file_model: Optional[IndexedFileModel], thumbnail_path: Optional[str] = None):
        """Update preview panel with selected file."""
        self.current_file = file_model
        if not file_model:
            self.thumb_label.setText("No File Selected")
            self.thumb_label.setPixmap(QPixmap())
            self.name_label.setText("Select a file to inspect")
            self.type_badge.setText("")
            self.size_label.setText("<b>Size:</b> -")
            self.date_label.setText("<b>Date:</b> -")
            self.chat_label.setText("<b>Chat:</b> -")
            self.mime_label.setText("<b>Format:</b> -")
            self.caption_label.setText("")
            self.btn_download.setEnabled(False)
            self.btn_open.setVisible(False)
            return

        self.btn_download.setEnabled(True)
        self.name_label.setText(file_model.filename)

        # Render type badge
        self.type_badge.setText(f" {file_model.media_type} ")
        self.type_badge.setStyleSheet(
            "background-color: #5865f2; color: #ffffff; border-radius: 4px; font-weight: bold; font-size: 11px; padding: 2px 6px;"
        )

        # Metadata
        kb_size = file_model.file_size / 1024.0
        mb_size = kb_size / 1024.0
        size_str = f"{mb_size:.2f} MB" if mb_size >= 1.0 else f"{kb_size:.1f} KB"
        self.size_label.setText(f"<b>Size:</b> {size_str} ({file_model.file_size:,} bytes)")

        date_str = file_model.message_date.strftime("%Y-%m-%d %H:%M:%S") if file_model.message_date else "-"
        self.date_label.setText(f"<b>Date:</b> {date_str}")
        self.chat_label.setText(f"<b>Chat:</b> {file_model.chat_title}")
        self.mime_label.setText(f"<b>Format:</b> {file_model.extension} ({file_model.mime_type})")

        if file_model.caption:
            self.caption_label.setText(f"<b>Caption:</b> {file_model.caption}")
            self.caption_label.setVisible(True)
        else:
            self.caption_label.setVisible(False)

        # Render Thumbnail
        effective_thumb = thumbnail_path or file_model.thumbnail_path
        if effective_thumb and Path(effective_thumb).exists():
            pix = QPixmap(effective_thumb)
            if not pix.isNull():
                scaled_pix = pix.scaled(240, 160, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.thumb_label.setPixmap(scaled_pix)
                self.thumb_label.setText("")
            else:
                self._set_placeholder_icon(file_model)
        else:
            self._set_placeholder_icon(file_model)

        # Check if file exists locally in download dir
        local_path = settings.download_dir / file_model.filename
        if local_path.exists():
            self.btn_open.setVisible(True)
            self.btn_download.setText("⬇ Re-download")
        else:
            self.btn_open.setVisible(False)
            self.btn_download.setText("⬇ Download File")

    def _set_placeholder_icon(self, file_model: IndexedFileModel):
        icons = {
            "IMAGE": "🖼️",
            "VIDEO": "🎬",
            "AUDIO": "🎵",
            "VOICE": "🎤",
            "DOCUMENT": "📄",
            "ARCHIVE": "📦",
        }
        icon = icons.get(file_model.media_type, "📎")
        self.thumb_label.setPixmap(QPixmap())
        self.thumb_label.setText(f"{icon}\n{file_model.extension.upper()}")

    def _on_download_clicked(self):
        if self.current_file:
            self.download_requested.emit(self.current_file)

    def _on_open_clicked(self):
        if self.current_file:
            local_path = settings.download_dir / self.current_file.filename
            if local_path.exists():
                from ..services.preview import PreviewService
                PreviewService.open_in_system_viewer(str(local_path))


class PreviewDialog(QDialog):
    """Large modal preview window for inspecting images and full media details."""

    def __init__(self, file_model: IndexedFileModel, image_path: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.file_model = file_model
        self.image_path = image_path
        self.setWindowTitle(f"Preview: {file_model.filename}")
        self.resize(750, 600)
        self.setMinimumSize(500, 400)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Image view area
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background-color: #18191c; border-radius: 8px;")

        if self.image_path and Path(self.image_path).exists():
            pix = QPixmap(self.image_path)
            if not pix.isNull():
                self.image_label.setPixmap(pix.scaled(700, 460, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.image_label.setText(f"📄 {self.file_model.filename}\n\nSize: {self.file_model.file_size:,} bytes")
            self.image_label.setStyleSheet("background-color: #18191c; color: #949ba4; font-size: 14px; border-radius: 8px;")

        layout.addWidget(self.image_label, stretch=1)

        # Close button
        btn_close = QPushButton("Close Preview")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignRight)
