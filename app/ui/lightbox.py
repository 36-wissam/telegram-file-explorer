"""Dedicated Fullscreen Image Lightbox Dialog for Telegram File Explorer."""

from pathlib import Path
from typing import List, Optional
from PySide6.QtCore import Qt, Signal, QPointF
from PySide6.QtGui import QColor, QFont, QKeySequence, QPainter, QPixmap, QShortcut, QWheelEvent
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

from ..database.models import IndexedFileModel
from .icons import get_icon
from .media_card import format_bytes


class ImageLightboxDialog(QDialog):
    """Fullscreen/Modal Image Lightbox with zoom, pan, navigation, and download."""

    download_requested = Signal(object) # Emits IndexedFileModel

    def __init__(
        self,
        files: List[IndexedFileModel],
        current_index: int = 0,
        parent=None,
    ):
        super().__init__(parent)
        self.files = [f for f in files if f.media_type in ("IMAGE", "PHOTO")] or files
        self.current_index = max(0, min(current_index, len(self.files) - 1)) if self.files else 0
        self.zoom_factor: float = 1.0

        self.setWindowTitle("Image Lightbox")
        self.resize(1100, 750)
        self.setMinimumSize(640, 480)
        self._init_ui()
        self._setup_shortcuts()
        self._load_current_image()

    def _init_ui(self):
        self.setStyleSheet(
            """
            QDialog {
                background-color: #111113;
                color: #F4F4F5;
            }
            QPushButton {
                background-color: #27272A;
                border: 1px solid #3F3F46;
                border-radius: 8px;
                color: #F4F4F5;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #3F3F46;
                border-color: #71717A;
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
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # 1. Top Control Bar (Title, Counter, Zoom, Actions, Close)
        top_bar = QFrame(self)
        top_bar.setFixedHeight(44)
        top_bar.setStyleSheet("background-color: #18181B; border: 1px solid #27272A; border-radius: 8px; padding: 4px 12px;")
        t_layout = QHBoxLayout(top_bar)
        t_layout.setContentsMargins(8, 2, 8, 2)
        t_layout.setSpacing(10)

        # Image Title
        self.title_label = QLabel("Image Preview")
        t_font = QFont()
        t_font.setBold(True)
        t_font.setPointSize(11)
        self.title_label.setFont(t_font)
        self.title_label.setStyleSheet("color: #F4F4F5;")
        t_layout.addWidget(self.title_label)

        # Counter (e.g. 1 of 12)
        self.counter_label = QLabel("1 / 1")
        self.counter_label.setStyleSheet("color: #A1A1AA; font-size: 12px;")
        t_layout.addWidget(self.counter_label)

        t_layout.addStretch()

        # Zoom Controls
        self.btn_zoom_out = QPushButton()
        self.btn_zoom_out.setIcon(get_icon("zoom_out", color="#F4F4F5", size=16))
        self.btn_zoom_out.setToolTip("Zoom Out (-)")
        self.btn_zoom_out.clicked.connect(self._zoom_out)
        t_layout.addWidget(self.btn_zoom_out)

        self.btn_zoom_reset = QPushButton("100%")
        self.btn_zoom_reset.setToolTip("Reset Zoom (1:1)")
        self.btn_zoom_reset.clicked.connect(self._zoom_reset)
        t_layout.addWidget(self.btn_zoom_reset)

        self.btn_zoom_in = QPushButton()
        self.btn_zoom_in.setIcon(get_icon("zoom_in", color="#F4F4F5", size=16))
        self.btn_zoom_in.setToolTip("Zoom In (+)")
        self.btn_zoom_in.clicked.connect(self._zoom_in)
        t_layout.addWidget(self.btn_zoom_in)

        # Download Button
        self.btn_download = QPushButton("Download")
        self.btn_download.setObjectName("primaryButton")
        self.btn_download.setIcon(get_icon("download", color="#FFFFFF", size=14))
        self.btn_download.setToolTip("Download image to PC")
        self.btn_download.clicked.connect(self._on_download)
        t_layout.addWidget(self.btn_download)

        # Close Button
        self.btn_close = QPushButton()
        self.btn_close.setIcon(get_icon("x", color="#F4F4F5", size=16))
        self.btn_close.setToolTip("Close (Esc)")
        self.btn_close.clicked.connect(self.accept)
        t_layout.addWidget(self.btn_close)

        layout.addWidget(top_bar)

        # 2. Main Canvas with Left/Right Navigation overlay
        canvas_row = QHBoxLayout()
        canvas_row.setSpacing(8)

        # Left Nav Button
        self.btn_prev = QPushButton()
        self.btn_prev.setIcon(get_icon("arrow_left", color="#F4F4F5", size=20))
        self.btn_prev.setFixedSize(42, 64)
        self.btn_prev.setToolTip("Previous image (Left Arrow)")
        self.btn_prev.clicked.connect(self._prev_image)
        canvas_row.addWidget(self.btn_prev, alignment=Qt.AlignVCenter)

        # Scroll / Viewport
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("background-color: #111113; border: 1px solid #27272A; border-radius: 8px;")
        self.scroll_area.setAlignment(Qt.AlignCenter)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background-color: transparent;")
        self.scroll_area.setWidget(self.image_label)
        canvas_row.addWidget(self.scroll_area, stretch=1)

        # Right Nav Button
        self.btn_next = QPushButton()
        self.btn_next.setIcon(get_icon("arrow_right", color="#F4F4F5", size=20))
        self.btn_next.setFixedSize(42, 64)
        self.btn_next.setToolTip("Next image (Right Arrow)")
        self.btn_next.clicked.connect(self._next_image)
        canvas_row.addWidget(self.btn_next, alignment=Qt.AlignVCenter)

        layout.addLayout(canvas_row, stretch=1)

        # 3. Bottom Info Strip
        self.meta_label = QLabel("")
        self.meta_label.setStyleSheet("color: #A1A1AA; font-size: 12px; padding: 4px 8px;")
        self.meta_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.meta_label)

    def _setup_shortcuts(self):
        """Configure keyboard accelerators."""
        QShortcut(QKeySequence(Qt.Key_Left), self, self._prev_image)
        QShortcut(QKeySequence(Qt.Key_Right), self, self._next_image)
        QShortcut(QKeySequence(Qt.Key_Plus), self, self._zoom_in)
        QShortcut(QKeySequence(Qt.Key_Equal), self, self._zoom_in)
        QShortcut(QKeySequence(Qt.Key_Minus), self, self._zoom_out)
        QShortcut(QKeySequence(Qt.Key_0), self, self._zoom_reset)
        QShortcut(QKeySequence(Qt.Key_Escape), self, self.accept)

    def _load_current_image(self):
        """Render the active image based on current index."""
        if not self.files:
            self.image_label.setText("No images to display")
            self.counter_label.setText("0 / 0")
            self.btn_prev.setEnabled(False)
            self.btn_next.setEnabled(False)
            return

        current_file = self.files[self.current_index]
        self.title_label.setText(current_file.filename)
        self.counter_label.setText(f"{self.current_index + 1} of {len(self.files)}")
        self.btn_prev.setEnabled(self.current_index > 0)
        self.btn_next.setEnabled(self.current_index < len(self.files) - 1)

        size_str = format_bytes(current_file.file_size)
        date_str = current_file.message_date.strftime("%b %d, %Y %H:%M") if current_file.message_date else "-"
        self.meta_label.setText(f"{current_file.filename} · {size_str} · {current_file.chat_title} · {date_str}")

        # Check local file or thumbnail
        pix: Optional[QPixmap] = None
        if current_file.thumbnail_path and Path(current_file.thumbnail_path).exists():
            pix = QPixmap(current_file.thumbnail_path)

        if pix and not pix.isNull():
            self._original_pixmap = pix
            self._update_image_render()
        else:
            self.image_label.setText(f"Preview unavailable locally for {current_file.filename}\n\nClick Download to retrieve original image.")
            self.image_label.setStyleSheet("color: #A1A1AA; font-size: 14px; text-align: center;")

    def _update_image_render(self):
        if hasattr(self, "_original_pixmap") and not self._original_pixmap.isNull():
            w = int(self._original_pixmap.width() * self.zoom_factor)
            h = int(self._original_pixmap.height() * self.zoom_factor)
            scaled = self._original_pixmap.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.image_label.setPixmap(scaled)

    def _zoom_in(self):
        self.zoom_factor = min(self.zoom_factor * 1.25, 5.0)
        self.btn_zoom_reset.setText(f"{int(self.zoom_factor * 100)}%")
        self._update_image_render()

    def _zoom_out(self):
        self.zoom_factor = max(self.zoom_factor / 1.25, 0.2)
        self.btn_zoom_reset.setText(f"{int(self.zoom_factor * 100)}%")
        self._update_image_render()

    def _zoom_reset(self):
        self.zoom_factor = 1.0
        self.btn_zoom_reset.setText("100%")
        self._update_image_render()

    def _prev_image(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.zoom_factor = 1.0
            self.btn_zoom_reset.setText("100%")
            self._load_current_image()

    def _next_image(self):
        if self.current_index < len(self.files) - 1:
            self.current_index += 1
            self.zoom_factor = 1.0
            self.btn_zoom_reset.setText("100%")
            self._load_current_image()

    def _on_download(self):
        if self.files and 0 <= self.current_index < len(self.files):
            self.download_requested.emit(self.files[self.current_index])
