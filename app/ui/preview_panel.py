"""File preview inspector panel and media preview dialog with real playback."""

from pathlib import Path
from typing import Optional
from PySide6.QtCore import QTime, QUrl, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPixmap
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ..core.config import settings
from ..core.logger import get_logger
from ..database.models import IndexedFileModel
from .icons import get_icon, get_pixmap
from .lightbox import ImageLightboxDialog
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
                border-radius: 10px;
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
        self.btn_download.setIcon(get_icon("download", color="#FFFFFF", size=14))
        self.btn_download.clicked.connect(self._on_download_clicked)
        self.btn_download.setEnabled(False)
        f_layout.addWidget(self.btn_download)

        self.btn_open = QPushButton("Open File")
        self.btn_open.setIcon(get_icon("external_link", color="#F4F4F5", size=14))
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
            self.status_label.setText("Status: Downloaded")
            self.status_label.setStyleSheet("color: #22C55E; font-weight: 500;")
        else:
            self.btn_open.setVisible(False)
            self.btn_download.setText("Download File")
            self.status_label.setText("Status: Available on Telegram")
            self.status_label.setStyleSheet("color: #229ED9; font-weight: 500;")

        # Render Thumbnail / Icon
        effective_thumb = thumbnail_path or file_model.thumbnail_path
        if effective_thumb and Path(effective_thumb).exists():
            pix = QPixmap(effective_thumb)
            if not pix.isNull():
                scaled_pix = pix.scaled(240, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.thumb_label.setPixmap(scaled_pix)
                self.thumb_label.setText("")
                return

        # Render clean SVG icon fallback
        icon_name = "file"
        mtype = file_model.media_type.upper()
        if mtype in ("IMAGE", "PHOTO"):
            icon_name = "image"
        elif mtype == "VIDEO":
            icon_name = "video"
        elif mtype == "AUDIO":
            icon_name = "audio"
        elif mtype == "DOCUMENT":
            icon_name = "file_text"
        elif file_model.extension.lower() in (".zip", ".rar", ".7z", ".tar", ".gz"):
            icon_name = "archive"

        self.thumb_label.setPixmap(get_pixmap(icon_name, color="#229ED9", size=48))
        self.thumb_label.setText("")

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
    """Media preview modal with real video/audio playback and lightbox integration."""

    download_requested = Signal(object) # Emits IndexedFileModel

    def __init__(self, file_model: IndexedFileModel, image_path: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.file_model = file_model
        self.image_path = image_path
        self.setWindowTitle(f"Preview: {file_model.filename}")
        self.resize(800, 640)
        self.setMinimumSize(540, 440)

        self._player: Optional[QMediaPlayer] = None
        self._audio_output: Optional[QAudioOutput] = None
        self._video_widget: Optional[QVideoWidget] = None

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
                border-radius: 8px;
                color: #F4F4F5;
                padding: 6px 14px;
                font-size: 13px;
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
            QSlider::groove:horizontal {
                height: 4px;
                background: #27272A;
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #229ED9;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #FFFFFF;
                width: 12px;
                margin: -4px 0;
                border-radius: 6px;
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
            "background-color: #27272A; color: #A1A1AA; border: 1px solid #3F3F46; border-radius: 6px; padding: 3px 8px; font-size: 12px;"
        )
        hdr_row.addWidget(size_badge)
        layout.addLayout(hdr_row)

        # Media Canvas
        mtype = self.file_model.media_type.upper()
        local_path = settings.download_dir / self.file_model.filename
        has_local = local_path.exists()

        if mtype == "VIDEO" and has_local:
            self._setup_video_player(layout, local_path)
        elif mtype == "AUDIO" and has_local:
            self._setup_audio_player(layout, local_path)
        elif mtype in ("IMAGE", "PHOTO"):
            self._setup_image_preview(layout)
        else:
            self._setup_generic_preview(layout, has_local)

        # Caption
        if self.file_model.caption:
            cap_lbl = QLabel(f"Caption: {self.file_model.caption}")
            cap_lbl.setStyleSheet("color: #A1A1AA; font-size: 12px; padding: 4px 0;")
            cap_lbl.setWordWrap(True)
            layout.addWidget(cap_lbl)

        # Bottom Actions Bar
        actions_row = QHBoxLayout()
        actions_row.setSpacing(10)

        self.btn_download = QPushButton("Download", self)
        self.btn_download.setObjectName("primaryButton")
        self.btn_download.setIcon(get_icon("download", color="#FFFFFF", size=14))
        self.btn_download.clicked.connect(self._on_download)
        actions_row.addWidget(self.btn_download)

        if has_local:
            self.btn_open = QPushButton("Open File", self)
            self.btn_open.setIcon(get_icon("external_link", color="#F4F4F5", size=14))
            self.btn_open.clicked.connect(self._on_open)
            actions_row.addWidget(self.btn_open)

        if mtype in ("IMAGE", "PHOTO"):
            btn_lightbox = QPushButton("Fullscreen Lightbox", self)
            btn_lightbox.setIcon(get_icon("maximize", color="#F4F4F5", size=14))
            btn_lightbox.clicked.connect(self._open_lightbox)
            actions_row.addWidget(btn_lightbox)

        actions_row.addStretch()

        btn_close = QPushButton("Close", self)
        btn_close.setIcon(get_icon("x", color="#F4F4F5", size=14))
        btn_close.clicked.connect(self._on_close_dialog)
        actions_row.addWidget(btn_close)

        layout.addLayout(actions_row)

    def _setup_image_preview(self, parent_layout: QVBoxLayout):
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background-color: #18181B; border: 1px solid #27272A; border-radius: 8px;")

        effective_path = self.image_path or self.file_model.thumbnail_path
        if effective_path and Path(effective_path).exists():
            pix = QPixmap(effective_path)
            if not pix.isNull():
                self.image_label.setPixmap(pix.scaled(720, 440, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                self._render_placeholder_icon("image")
        else:
            self._render_placeholder_icon("image")

        parent_layout.addWidget(self.image_label, stretch=1)

    def _setup_video_player(self, parent_layout: QVBoxLayout, video_path: Path):
        container = QFrame()
        container.setStyleSheet("background-color: #000000; border: 1px solid #27272A; border-radius: 8px;")
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(6)

        self._video_widget = QVideoWidget()
        c_layout.addWidget(self._video_widget, stretch=1)

        # Controls bar
        ctrl_bar = QFrame()
        ctrl_bar.setFixedHeight(40)
        ctrl_bar.setStyleSheet("background-color: #18181B; padding: 2px 10px;")
        ctrl_layout = QHBoxLayout(ctrl_bar)
        ctrl_layout.setContentsMargins(8, 2, 8, 2)
        ctrl_layout.setSpacing(8)

        self.btn_play = QPushButton()
        self.btn_play.setIcon(get_icon("play", color="#F4F4F5", size=14))
        self.btn_play.setFixedSize(32, 28)
        self.btn_play.clicked.connect(self._toggle_playback)
        ctrl_layout.addWidget(self.btn_play)

        self.seek_slider = QSlider(Qt.Horizontal)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.sliderMoved.connect(self._set_playback_position)
        ctrl_layout.addWidget(self.seek_slider, stretch=1)

        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setStyleSheet("color: #A1A1AA; font-size: 11px;")
        ctrl_layout.addWidget(self.time_label)

        c_layout.addWidget(ctrl_bar)
        parent_layout.addWidget(container, stretch=1)

        # Initialize Qt Multimedia Player
        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)
        self._player.setVideoOutput(self._video_widget)
        self._player.positionChanged.connect(self._on_video_position_changed)
        self._player.durationChanged.connect(self._on_video_duration_changed)
        self._player.setSource(QUrl.fromLocalFile(str(video_path)))

    def _setup_audio_player(self, parent_layout: QVBoxLayout, audio_path: Path):
        container = QFrame()
        container.setStyleSheet("background-color: #18181B; border: 1px solid #27272A; border-radius: 8px; padding: 20px;")
        c_layout = QVBoxLayout(container)
        c_layout.setSpacing(14)
        c_layout.setAlignment(Qt.AlignCenter)

        icon_lbl = QLabel()
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setPixmap(get_pixmap("audio", color="#229ED9", size=64))
        c_layout.addWidget(icon_lbl)

        name_lbl = QLabel(self.file_model.filename)
        name_lbl.setAlignment(Qt.AlignCenter)
        name_lbl.setStyleSheet("font-size: 14px; font-weight: 600; color: #F4F4F5;")
        c_layout.addWidget(name_lbl)

        # Seek row
        seek_row = QHBoxLayout()
        seek_row.setSpacing(10)

        self.btn_play = QPushButton()
        self.btn_play.setIcon(get_icon("play", color="#F4F4F5", size=14))
        self.btn_play.setFixedSize(36, 32)
        self.btn_play.clicked.connect(self._toggle_playback)
        seek_row.addWidget(self.btn_play)

        self.seek_slider = QSlider(Qt.Horizontal)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.sliderMoved.connect(self._set_playback_position)
        seek_row.addWidget(self.seek_slider, stretch=1)

        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setStyleSheet("color: #A1A1AA; font-size: 11px;")
        seek_row.addWidget(self.time_label)

        c_layout.addLayout(seek_row)
        parent_layout.addWidget(container, stretch=1)

        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)
        self._player.positionChanged.connect(self._on_video_position_changed)
        self._player.durationChanged.connect(self._on_video_duration_changed)
        self._player.setSource(QUrl.fromLocalFile(str(audio_path)))

    def _setup_generic_preview(self, parent_layout: QVBoxLayout, has_local: bool):
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background-color: #18181B; border: 1px solid #27272A; border-radius: 8px; padding: 24px;")

        mtype = self.file_model.media_type.upper()
        icon_name = "file"
        if mtype == "VIDEO":
            icon_name = "video"
        elif mtype == "AUDIO":
            icon_name = "audio"
        elif mtype == "DOCUMENT":
            icon_name = "file_text"
        elif self.file_model.extension.lower() in (".zip", ".rar", ".7z"):
            icon_name = "archive"

        status_text = "Downloaded locally." if has_local else "Available on Telegram.\n\nClick Download to save and open."
        self.image_label.setPixmap(get_pixmap(icon_name, color="#229ED9", size=64))
        parent_layout.addWidget(self.image_label, stretch=1)

    def _render_placeholder_icon(self, icon_name: str):
        self.image_label.setPixmap(get_pixmap(icon_name, color="#229ED9", size=64))

    def _toggle_playback(self):
        if not self._player:
            return
        if self._player.playbackState() == QMediaPlayer.PlayingState:
            self._player.pause()
            self.btn_play.setIcon(get_icon("play", color="#F4F4F5", size=14))
        else:
            self._player.play()
            self.btn_play.setIcon(get_icon("pause", color="#F4F4F5", size=14))

    def _set_playback_position(self, value: int):
        if self._player and self._player.duration() > 0:
            target_ms = int((value / 1000.0) * self._player.duration())
            self._player.setPosition(target_ms)

    def _on_video_position_changed(self, pos_ms: int):
        if self._player and self._player.duration() > 0:
            pct = int((pos_ms / self._player.duration()) * 1000)
            self.seek_slider.blockSignals(True)
            self.seek_slider.setValue(pct)
            self.seek_slider.blockSignals(False)

            cur_str = QTime(0, 0, 0).addMSecs(pos_ms).toString("mm:ss")
            dur_str = QTime(0, 0, 0).addMSecs(self._player.duration()).toString("mm:ss")
            self.time_label.setText(f"{cur_str} / {dur_str}")

    def _on_video_duration_changed(self, dur_ms: int):
        cur_str = "00:00"
        dur_str = QTime(0, 0, 0).addMSecs(dur_ms).toString("mm:ss")
        self.time_label.setText(f"{cur_str} / {dur_str}")

    def _open_lightbox(self):
        self._stop_player()
        lightbox = ImageLightboxDialog([self.file_model], parent=self)
        lightbox.download_requested.connect(self.download_requested.emit)
        lightbox.exec()

    def _on_download(self):
        self.download_requested.emit(self.file_model)

    def _on_open(self):
        local_path = settings.download_dir / self.file_model.filename
        if local_path.exists():
            from ..services.preview import PreviewService
            PreviewService.open_in_system_viewer(str(local_path))

    def _stop_player(self):
        if self._player:
            self._player.stop()

    def _on_close_dialog(self):
        self._stop_player()
        self.accept()

    def closeEvent(self, event):
        self._stop_player()
        super().closeEvent(event)
