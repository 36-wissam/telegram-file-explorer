"""Chat discovery list widget and list item for PySide6."""

from typing import List, Optional
from pathlib import Path
from PySide6.QtCore import Qt, Signal, QSize, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPixmap, QBrush
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..telegram.chats import ChatType, TelegramChat
from ..core.logger import get_logger

logger = get_logger("ui.chat_list")

TYPE_COLORS = {
    ChatType.CHANNEL: "#5865f2",      # Discord blurple
    ChatType.SUPERGROUP: "#3ba55d",   # Green
    ChatType.GROUP: "#57f287",        # Light green
    ChatType.USER: "#4f545c",         # Subtle grey
    ChatType.BOT: "#eb459e",          # Pink
    ChatType.SAVED_MESSAGES: "#fee75c" # Gold
}


class ChatListItemWidget(QWidget):
    """Custom widget rendered for each chat in QListWidget."""

    def __init__(self, chat: TelegramChat, parent=None):
        super().__init__(parent)
        self.chat = chat
        self.setFixedHeight(64)
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(12)

        # Avatar Label
        self.avatar_label = QLabel()
        self.avatar_label.setFixedSize(46, 46)
        self.avatar_label.setPixmap(self._generate_avatar())
        layout.addWidget(self.avatar_label)

        # Text Details (Title, Type badge, Chat ID)
        text_layout = QVBoxLayout()
        text_layout.setSpacing(3)
        text_layout.setAlignment(Qt.AlignVCenter)

        # Top row: Title + Type Badge
        top_row = QHBoxLayout()
        top_row.setSpacing(6)

        title_label = QLabel(self.chat.display_name)
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(11)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #ffffff;")
        top_row.addWidget(title_label)

        badge_color = TYPE_COLORS.get(self.chat.chat_type, "#5865f2")
        type_badge = QLabel(f" {self.chat.chat_type.value} ")
        type_badge.setStyleSheet(
            f"background-color: {badge_color}; color: #ffffff; border-radius: 4px; font-size: 10px; font-weight: bold; padding: 1px 4px;"
        )
        top_row.addWidget(type_badge)
        top_row.addStretch()

        text_layout.addLayout(top_row)

        # Bottom row: Chat ID + Username
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(8)

        id_label = QLabel(f"ID: {self.chat.id}")
        id_label.setStyleSheet("color: #949ba4; font-size: 11px;")
        bottom_row.addWidget(id_label)

        if self.chat.username:
            user_label = QLabel(f"@{self.chat.username}")
            user_label.setStyleSheet("color: #00aff4; font-size: 11px;")
            bottom_row.addWidget(user_label)

        bottom_row.addStretch()
        text_layout.addLayout(bottom_row)

        layout.addLayout(text_layout)

        # Unread Count Badge
        if self.chat.unread_count > 0:
            unread_badge = QLabel(f"{self.chat.unread_count}")
            unread_badge.setStyleSheet(
                "background-color: #5865f2; color: #ffffff; border-radius: 10px; font-size: 11px; font-weight: bold; min-width: 20px; padding: 2px 6px;"
            )
            unread_badge.setAlignment(Qt.AlignCenter)
            layout.addWidget(unread_badge)

    def _generate_avatar(self) -> QPixmap:
        """Create circular avatar with image or colored initials."""
        size = 46
        target_pixmap = QPixmap(size, size)
        target_pixmap.fill(Qt.transparent)

        painter = QPainter(target_pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        path = QPainterPath()
        path.addEllipse(0, 0, size, size)
        painter.setClipPath(path)

        # Try loading cached image if available
        if self.chat.avatar_path and Path(self.chat.avatar_path).exists():
            img_pixmap = QPixmap(self.chat.avatar_path)
            if not img_pixmap.isNull():
                painter.drawPixmap(0, 0, size, size, img_pixmap.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
                painter.end()
                return target_pixmap

        # Fallback: colored circle with initial letter
        color_seed = abs(self.chat.id) % 6
        palette = ["#5865f2", "#3ba55d", "#fee75c", "#eb459e", "#ed4245", "#00aff4"]
        bg_color = QColor(palette[color_seed])

        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.NoPen)
        painter.drawRect(0, 0, size, size)

        # Initial letter
        initial = (self.chat.display_name or "?")[0].upper()
        painter.setPen(QColor("#ffffff"))
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(QRectF(0, 0, size, size), Qt.AlignCenter, initial)

        painter.end()
        return target_pixmap


class ChatListWidget(QWidget):
    """Complete sidebar widget for chat discovery, filtering, and selection."""

    chat_selected = Signal(object)  # Emits TelegramChat
    refresh_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_chats: List[TelegramChat] = []
        self._current_filter: str = "ALL"
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # Header Bar: Title + Refresh
        header_layout = QHBoxLayout()
        header_title = QLabel("Chats & Channels")
        header_font = QFont()
        header_font.setPointSize(14)
        header_font.setBold(True)
        header_title.setFont(header_font)
        header_layout.addWidget(header_title)

        self.btn_refresh = QPushButton("🔄 Refresh")
        self.btn_refresh.setStyleSheet("padding: 4px 10px; font-size: 11px;")
        self.btn_refresh.clicked.connect(self.refresh_requested.emit)
        header_layout.addWidget(self.btn_refresh)
        layout.addLayout(header_layout)

        # Search Box
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Search chats by name or ID...")
        self.search_input.textChanged.connect(self._apply_filter)
        layout.addWidget(self.search_input)

        # Category Filter Buttons
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(4)

        self.btn_filter_all = QPushButton("All")
        self.btn_filter_channels = QPushButton("Channels")
        self.btn_filter_groups = QPushButton("Groups")
        self.btn_filter_users = QPushButton("Direct")

        for btn, cat in [
            (self.btn_filter_all, "ALL"),
            (self.btn_filter_channels, "CHANNEL"),
            (self.btn_filter_groups, "GROUP"),
            (self.btn_filter_users, "USER"),
        ]:
            btn.setStyleSheet("padding: 4px 8px; font-size: 11px;")
            btn.clicked.connect(lambda checked=False, c=cat: self._set_category_filter(c))
            filter_layout.addWidget(btn)

        layout.addLayout(filter_layout)

        # Chat Count Info
        self.count_label = QLabel("0 chats discovered")
        self.count_label.setStyleSheet("color: #949ba4; font-size: 11px;")
        layout.addWidget(self.count_label)

        # List Widget
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(
            """
            QListWidget {
                background-color: #1e1f22;
                border: 1px solid #2b2d31;
                border-radius: 8px;
            }
            QListWidget::item {
                border-bottom: 1px solid #2b2d31;
                border-radius: 6px;
                margin: 2px 4px;
            }
            QListWidget::item:selected {
                background-color: #35373c;
            }
            QListWidget::item:hover:!selected {
                background-color: #232428;
            }
            """
        )
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.list_widget)

    def set_chats(self, chats: List[TelegramChat]):
        """Populate the list with discovered chats."""
        self._all_chats = chats
        self._apply_filter()

    def _set_category_filter(self, category: str):
        """Update active category filter."""
        self._current_filter = category
        self._apply_filter()

    def _apply_filter(self):
        """Filter chats by search query and category."""
        query = self.search_input.text().strip().lower()
        self.list_widget.clear()

        matched = 0
        for chat in self._all_chats:
            # Category filter
            if self._current_filter == "CHANNEL" and chat.chat_type != ChatType.CHANNEL:
                continue
            if self._current_filter == "GROUP" and chat.chat_type not in (ChatType.GROUP, ChatType.SUPERGROUP):
                continue
            if self._current_filter == "USER" and chat.chat_type not in (ChatType.USER, ChatType.BOT, ChatType.SAVED_MESSAGES):
                continue

            # Query filter
            if query:
                in_title = query in chat.title.lower()
                in_username = chat.username and query in chat.username.lower()
                in_id = query in str(chat.id)
                if not (in_title or in_username or in_id):
                    continue

            # Add to list widget
            item = QListWidgetItem(self.list_widget)
            item.setSizeHint(QSize(0, 64))
            item.setData(Qt.UserRole, chat)

            widget = ChatListItemWidget(chat)
            self.list_widget.setItemWidget(item, widget)
            matched += 1

        self.count_label.setText(f"{matched} of {len(self._all_chats)} chats")

    def _on_item_clicked(self, item: QListWidgetItem):
        """Handle chat selection in the list."""
        chat: TelegramChat = item.data(Qt.UserRole)
        if chat:
            logger.info("Selected chat: %s (ID: %d)", chat.display_name, chat.id)
            self.chat_selected.emit(chat)
