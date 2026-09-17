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
from .media_card import format_bytes

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
        self.setStyleSheet("background-color: #18181B; border-left: 1px solid #27272A;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)
        layout.setAlignment(Qt.AlignTop)

        # Container Frame
        self.frame = QFrame(self)
        self.frame.setStyleSheet(
            """
            QFrame {
                background-color: #1C1C1F;
                border: 1px solid #27272A;
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
            background-color: #111113;
            border: 1px solid #27272A;
            border-radius: 6px;
            color: #71717A;
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
        self.name_label.setStyleSheet("color: #F4F4F5;")
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
                background-color: #111113;
                border: 1px solid #27272A;
                border-radius: 6px;
                padding: 10px;
            }
            QLabel {
                color: #A1A1AA;
                font-size: 12px;
            }
            """
        )
        d_layout = QVBoxLayout(self.details_box)
        d_layout.setSpacing(6)

        self.size_label = QLabel("Size: -")
        d_layout.addWidget(self.size_label)

        self.date_label = QLabel("Date: -")
        d_layout.addWidget(self.date_label)

        self.chat_label = QLabel("Chat: -")
        d_layout.addWidget(self.chat_label)

        self.mime_label = QLabel("Format: -")
        d_layout.addWidget(self.mime_label)

        self.status_label = QLabel("Status: Available on Telegram")
        self.status_label.setStyleSheet("color: #229ED9; font-weight: 500;")
        d_layout.addWidget(self.status_label)

        self.caption_label = QLabel("")
        self.caption_label.setStyleSheet("font-size: 11px; color: #71717A;")
        self.caption_label.setWordWrap(True)
        d_layout.addWidget(self.caption_label)

        f_layout.addWidget(self.details_box)

        # Action Buttons
        self.btn_download = QPushButton("Download File")
        self.btn_download.setObjectName("primaryButton")
        self.btn_download.clicked.connect(self._on_download_clicked)
        self.btn_download.setEnabled(False)
        f_layout.addWidget(self.btn_download)

        self.btn_open = QPushButton("Open in System App")
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
            self.size_label.setText("Size: -")
            self.date_label.setText("Date: -")
            self.chat_label.setText("Chat: -")
            self.mime_label.setText("Format: -")
            self.status_label.setText("Status: -")
            self.caption_label.setText("")
            self.btn_download.setEnabled(False)
            self.btn_open.setVisible(False)
            return

        self.btn_download.setEnabled(True)
        self.name_label.setText(file_model.filename)

        # Render type badge
        self.type_badge.setText(f" {file_model.media_type} ")
        self.type_badge.setStyleSheet(
            "background-color: #27272A; color: #229ED9; border: 1px solid #3F3F46; border-radius: 4px; font-weight: 600; font-size: 11px; padding: 2px 6px;"
        )

        # Metadata
        kb_size = file_model.file_size / 1024.0
        mb_size = kb_size / 1024.0
        size_str = f"{mb_size:.2f} MB" if mb_size >= 1.0 else f"{kb_size:.1f} KB"
        self.size_label.setText(f"Size: {size_str} ({file_model.file_size:,} bytes)")

        date_str = file_model.message_date.strftime("%Y-%m-%d %H:%M:%S") if file_model.message_date else "-"
        self.date_label.setText(f"Date: {date_str}")
        self.chat_label.setText(f"Chat: {file_model.chat_title}")
        self.mime_label.setText(f"Format: {file_model.extension} ({file_model.mime_type})")

        if file_model.caption:
            self.caption_label.setText(f"Caption: {file_model.caption}")
            self.caption_label.setVisible(True)
        else:
            self.caption_label.setVisible(False)

        # Check if file exists locally in download dir
        local_path = settings.download_dir / file_model.filename
        if local_path.exists():
            self.btn_open.setVisible(True)
            self.btn_download.setText("Re-download")
            self.status_label.setText("Status: Downloaded locally")
            self.status_label.setStyleSheet("color: #22C55E; font-weight: 500;")
        else:
            self.btn_open.setVisible(False)
            self.btn_download.setText("Download File")
            self.status_label.setText("Status: Available on Telegram")
            self.status_label.setStyleSheet("color: #229ED9; font-weight: 500;")

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

    def _set_placeholder_icon(self, file_model: IndexedFileModel):
        self.thumb_label.setPixmap(QPixmap())
        self.thumb_label.setText(f"[{file_model.media_type}]\n{file_model.extension.upper()}")

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

    download_requested = Signal(object)

    def __init__(self, file_model: IndexedFileModel, image_path: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.file_model = file_model
        self.image_path = image_path
        self.setWindowTitle(f"Preview: {file_model.filename}")
        self.resize(760, 620)
        self.setMinimumSize(520, 420)
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet(
            """
            QDialog {
                background-color: #111113;
                color: #F4F4F5;
            }
            QLabel {
                color: #F4F4F5;
            }
            QPushButton {
                background-color: #27272A;
                border: 1px solid #3F3F46;
                border-radius: 6px;
                color: #F4F4F5;
                padding: 6px 14px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #3F3F46;
                color: #FFFFFF;
            }
            QPushButton#primaryButton {
                background-color: #229ED9;
                border: none;
                color: #FFFFFF;
                font-weight: 600;
            }
            QPushButton#primaryButton:hover {
                background-color: #3AAFE8;
            }
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header Info Row
        hdr_row = QHBoxLayout()
        title_lbl = QLabel(self.file_model.filename)
        t_font = QFont()
        t_font.setPointSize(13)
        t_font.setBold(True)
        title_lbl.setFont(t_font)
        title_lbl.setStyleSheet("color: #F4F4F5;")
        hdr_row.addWidget(title_lbl)

        hdr_row.addStretch()

        size_badge = QLabel(format_bytes(self.file_model.file_size))
        size_badge.setStyleSheet(
            "background-color: #27272A; color: #A1A1AA; border-radius: 4px; padding: 3px 8px; font-size: 12px;"
        )
        hdr_row.addWidget(size_badge)
        layout.addLayout(hdr_row)

        # Image view area
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet(
            "background-color: #18181B; border: 1px solid #27272A; border-radius: 8px;"
        )

        effective_path = self.image_path or self.file_model.thumbnail_path
        if effective_path and Path(effective_path).exists():
            pix = QPixmap(effective_path)
            if not pix.isNull():
                self.image_label.setPixmap(pix.scaled(720, 480, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                self._render_file_info_placeholder()
        else:
            self._render_file_info_placeholder()

        layout.addWidget(self.image_label, stretch=1)

        # Caption
        if self.file_model.caption:
            cap_lbl = QLabel(self.file_model.caption)
            cap_lbl.setStyleSheet("color: #A1A1AA; font-size: 12px;")
            cap_lbl.setWordWrap(True)
            layout.addWidget(cap_lbl)

        # Bottom Actions
        actions_row = QHBoxLayout()

        btn_download = QPushButton("Download", self)
        btn_download.setObjectName("primaryButton")
        btn_download.clicked.connect(self._on_download)
        actions_row.addWidget(btn_download)

        local_path = settings.download_dir / self.file_model.filename
        if local_path.exists():
            btn_open = QPushButton("Open in App", self)
            btn_open.clicked.connect(self._on_open)
            actions_row.addWidget(btn_open)

        actions_row.addStretch()

        btn_close = QPushButton("Close", self)
        btn_close.clicked.connect(self.accept)
        actions_row.addWidget(btn_close)

        layout.addLayout(actions_row)

    def _render_file_info_placeholder(self):
        info_text = (
            f"[{self.file_model.media_type}]\n\n"
            f"Filename: {self.file_model.filename}\n"
            f"Size: {format_bytes(self.file_model.file_size)} ({self.file_model.file_size:,} bytes)\n"
            f"Chat: {self.file_model.chat_title}\n"
            f"Format: {self.file_model.extension} ({self.file_model.mime_type})"
        )
        self.image_label.setText(info_text)
        self.image_label.setStyleSheet(
            "background-color: #18181B; color: #A1A1AA; font-size: 13px; border: 1px solid #27272A; border-radius: 8px; line-height: 1.6;"
        )

    def _on_download(self):
        self.download_requested.emit(self.file_model)

    def _on_open(self):
        local_path = settings.download_dir / self.file_model.filename
        if local_path.exists():
            from ..services.preview import PreviewService
            PreviewService.open_in_system_viewer(str(local_path))

