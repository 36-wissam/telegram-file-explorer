"""Chat detail view widget for PySide6."""

from pathlib import Path
from PySide6.QtCore import Qt, QRectF, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPixmap, QBrush
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..telegram.chats import TelegramChat, ChatType
from .chat_list import TYPE_COLORS


class ChatDetailWidget(QWidget):
    """Displays detailed view of the currently selected Telegram chat."""

    index_chat_requested = Signal(int)  # Emits chat_id to open indexing manager

    def __init__(self, parent=None):
        super().__init__(parent)
        self.chat: TelegramChat = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignTop)

        # Empty state container
        self.empty_card = QFrame(self)
        self.empty_card.setStyleSheet(
            """
            QFrame {
                background-color: #1e1f22;
                border: 1px dashed #35373c;
                border-radius: 12px;
                padding: 40px;
            }
            """
        )
        empty_layout = QVBoxLayout(self.empty_card)
        empty_layout.setAlignment(Qt.AlignCenter)
        empty_layout.setSpacing(10)

        empty_icon = QLabel("💬")
        empty_icon.setFont(QFont("Segoe UI Emoji", 36))
        empty_icon.setAlignment(Qt.AlignCenter)
        empty_layout.addWidget(empty_icon)

        empty_title = QLabel("Select a Chat to Explore")
        empty_title_font = QFont()
        empty_title_font.setPointSize(16)
        empty_title_font.setBold(True)
        empty_title.setFont(empty_title_font)
        empty_title.setAlignment(Qt.AlignCenter)
        empty_layout.addWidget(empty_title)

        empty_desc = QLabel("Choose any dialogue, channel, or group from the left sidebar to inspect details and files.")
        empty_desc.setStyleSheet("color: #949ba4; font-size: 13px;")
        empty_desc.setAlignment(Qt.AlignCenter)
        empty_layout.addWidget(empty_desc)

        layout.addWidget(self.empty_card)

        # Chat details container (hidden initially)
        self.content_card = QFrame(self)
        self.content_card.setStyleSheet(
            """
            QFrame {
                background-color: #1e1f22;
                border: 1px solid #2b2d31;
                border-radius: 12px;
                padding: 24px;
            }
            """
        )
        self.content_card.setVisible(False)
        content_layout = QVBoxLayout(self.content_card)
        content_layout.setSpacing(18)

        # Top Header: Large Avatar + Title + Type Badge
        header_row = QHBoxLayout()
        header_row.setSpacing(16)

        self.avatar_label = QLabel()
        self.avatar_label.setFixedSize(68, 68)
        header_row.addWidget(self.avatar_label)

        title_col = QVBoxLayout()
        title_col.setSpacing(4)
        title_col.setAlignment(Qt.AlignVCenter)

        title_badge_row = QHBoxLayout()
        title_badge_row.setSpacing(8)

        self.title_label = QLabel("")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        title_badge_row.addWidget(self.title_label)

        self.type_badge = QLabel("")
        title_badge_row.addWidget(self.type_badge)
        title_badge_row.addStretch()
        title_col.addLayout(title_badge_row)

        self.subtitle_label = QLabel("")
        self.subtitle_label.setStyleSheet("color: #949ba4; font-size: 13px;")
        title_col.addWidget(self.subtitle_label)

        header_row.addLayout(title_col)
        header_row.addStretch()
        content_layout.addLayout(header_row)

        # Metadata Details Grid / Box
        self.info_box = QFrame()
        self.info_box.setStyleSheet(
            """
            QFrame {
                background-color: #2b2d31;
                border-radius: 8px;
                padding: 16px;
            }
            """
        )
        info_layout = QVBoxLayout(self.info_box)
        info_layout.setSpacing(8)

        self.chat_id_label = QLabel("")
        self.chat_id_label.setStyleSheet("font-size: 13px;")
        info_layout.addWidget(self.chat_id_label)

        self.unread_label = QLabel("")
        self.unread_label.setStyleSheet("font-size: 13px;")
        info_layout.addWidget(self.unread_label)

        self.last_active_label = QLabel("")
        self.last_active_label.setStyleSheet("font-size: 13px;")
        info_layout.addWidget(self.last_active_label)

        content_layout.addWidget(self.info_box)

        # Indexing Action Container
        self.indexing_box = QFrame()
        self.indexing_box.setStyleSheet(
            """
            QFrame {
                background-color: #232428;
                border: 1px solid #35373c;
                border-radius: 8px;
                padding: 16px;
            }
            """
        )
        idx_layout = QVBoxLayout(self.indexing_box)
        idx_layout.setAlignment(Qt.AlignCenter)
        idx_layout.setSpacing(10)

        idx_title = QLabel("⚡ Media & File Indexing")
        idx_title.setStyleSheet("color: #00aff4; font-weight: bold; font-size: 14px;")
        idx_title.setAlignment(Qt.AlignCenter)
        idx_layout.addWidget(idx_title)

        idx_desc = QLabel(
            "Scan this chat to discover, index, search, and download all shared files and media."
        )
        idx_desc.setStyleSheet("color: #949ba4; font-size: 12px;")
        idx_desc.setAlignment(Qt.AlignCenter)
        idx_layout.addWidget(idx_desc)

        self.btn_index_chat = QPushButton("⚡ Index This Chat Now")
        self.btn_index_chat.setStyleSheet(
            """
            QPushButton {
                background-color: #00aff4;
                color: white;
                font-weight: bold;
                padding: 8px 18px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover { background-color: #0098d4; }
            """
        )
        self.btn_index_chat.clicked.connect(self._on_index_chat_clicked)
        idx_layout.addWidget(self.btn_index_chat, 0, Qt.AlignCenter)

        content_layout.addWidget(self.indexing_box)

        layout.addWidget(self.content_card)
        layout.addStretch()

    def set_chat(self, chat: TelegramChat):
        """Update view with selected chat details."""
        self.chat = chat
        if not chat:
            self.empty_card.setVisible(True)
            self.content_card.setVisible(False)
            return

        self.empty_card.setVisible(False)
        self.content_card.setVisible(True)

        self.title_label.setText(chat.display_name)
        badge_color = TYPE_COLORS.get(chat.chat_type, "#5865f2")
        self.type_badge.setText(f" {chat.chat_type.value} ")
        self.type_badge.setStyleSheet(
            f"background-color: {badge_color}; color: #ffffff; border-radius: 4px; font-size: 11px; font-weight: bold; padding: 2px 6px;"
        )

        sub_text = f"@{chat.username}" if chat.username else "Private Dialogue"
        self.subtitle_label.setText(sub_text)

        self.chat_id_label.setText(f"<b>Telegram Chat ID:</b> <code>{chat.id}</code>")
        self.unread_label.setText(f"<b>Unread Messages:</b> {chat.unread_count}")
        last_date_str = chat.last_message_date.strftime("%Y-%m-%d %H:%M:%S") if chat.last_message_date else "Unknown"
        self.last_active_label.setText(f"<b>Last Activity:</b> {last_date_str}")

        self.avatar_label.setPixmap(self._render_avatar(chat))

    def _render_avatar(self, chat: TelegramChat) -> QPixmap:
        """Render circular avatar for detail card."""
        size = 68
        target_pixmap = QPixmap(size, size)
        target_pixmap.fill(Qt.transparent)

        painter = QPainter(target_pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        path = QPainterPath()
        path.addEllipse(0, 0, size, size)
        painter.setClipPath(path)

        if chat.avatar_path and Path(chat.avatar_path).exists():
            img_pixmap = QPixmap(chat.avatar_path)
            if not img_pixmap.isNull():
                painter.drawPixmap(0, 0, size, size, img_pixmap.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
                painter.end()
                return target_pixmap

        color_seed = abs(chat.id) % 6
        palette = ["#5865f2", "#3ba55d", "#fee75c", "#eb459e", "#ed4245", "#00aff4"]
        bg_color = QColor(palette[color_seed])

        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.NoPen)
        painter.drawRect(0, 0, size, size)

        initial = (chat.display_name or "?")[0].upper()
        painter.setPen(QColor("#ffffff"))
        font = QFont()
        font.setPointSize(24)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(QRectF(0, 0, size, size), Qt.AlignCenter, initial)

        painter.end()
        return target_pixmap

    def _on_index_chat_clicked(self):
        """Emit signal requesting indexing of this specific chat."""
        if self.chat:
            self.index_chat_requested.emit(self.chat.id)
