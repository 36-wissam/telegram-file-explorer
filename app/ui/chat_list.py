"""Chat sidebar list widget conforming strictly to the specification (300px width, 64px rows, no emojis)."""

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
    ChatType.CHANNEL: "#229ED9",       # Telegram Blue
    ChatType.SUPERGROUP: "#3AAFE8",    # Light Blue
    ChatType.GROUP: "#22C55E",         # Green
    ChatType.USER: "#71717A",          # Gray
    ChatType.BOT: "#A855F7",           # Purple
    ChatType.SAVED_MESSAGES: "#F59E0B" # Amber
}


class ChatListItemWidget(QWidget):
    """Custom widget rendered for each chat in QListWidget (64px row height, 44x44 avatar)."""

    def __init__(self, chat: TelegramChat, parent=None):
        super().__init__(parent)
        self.chat = chat
        self.setFixedHeight(64)
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        # Avatar Label (44x44)
        self.avatar_label = QLabel()
        self.avatar_label.setFixedSize(44, 44)
        self.avatar_label.setPixmap(self._generate_avatar())
        layout.addWidget(self.avatar_label)

        # Text Details (Title, Last message preview, Timestamp)
        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        text_layout.setAlignment(Qt.AlignVCenter)

        # Top row: Title + Timestamp
        top_row = QHBoxLayout()
        top_row.setSpacing(6)

        title_label = QLabel(self.chat.display_name)
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(10)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #F4F4F5;")
        top_row.addWidget(title_label)

        top_row.addStretch()

        # Time
        time_str = ""
        if self.chat.last_message_date:
            time_str = self.chat.last_message_date.strftime("%H:%M")
        time_label = QLabel(time_str)
        time_label.setStyleSheet("color: #71717A; font-size: 11px;")
        top_row.addWidget(time_label)

        text_layout.addLayout(top_row)

        # Bottom row: Preview / Subtitle + Unread Badge
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(6)

        info_text = f"@{self.chat.username}" if self.chat.username else self.chat.chat_type.value
        preview_label = QLabel(info_text)
        preview_label.setStyleSheet("color: #A1A1AA; font-size: 12px;")
        bottom_row.addWidget(preview_label)

        bottom_row.addStretch()

        # Unread Count Badge
        if self.chat.unread_count > 0:
            unread_badge = QLabel(f"{self.chat.unread_count}")
            unread_badge.setStyleSheet(
                "background-color: #229ED9; color: #FFFFFF; border-radius: 9px; font-size: 11px; font-weight: 600; min-width: 18px; padding: 1px 6px;"
            )
            unread_badge.setAlignment(Qt.AlignCenter)
            bottom_row.addWidget(unread_badge)

        text_layout.addLayout(bottom_row)
        layout.addLayout(text_layout)

    def _generate_avatar(self) -> QPixmap:
        """Create circular avatar with image or colored initials (44x44)."""
        size = 44
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

        # Fallback: subtle colored circle with clean initial letter
        color_seed = abs(self.chat.id) % 6
        palette = ["#229ED9", "#22C55E", "#F59E0B", "#A855F7", "#EF4444", "#3AAFE8"]
        bg_color = QColor(palette[color_seed])

        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.NoPen)
        painter.drawRect(0, 0, size, size)

        # Initial letter
        initial = (self.chat.display_name or "?")[0].upper()
        painter.setPen(QColor("#FFFFFF"))
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(QRectF(0, 0, size, size), Qt.AlignCenter, initial)

        painter.end()
        return target_pixmap


class ChatListWidget(QWidget):
    """300px sidebar widget for chat discovery, filtering, and progressive selection."""

    chat_selected = Signal(object)  # Emits TelegramChat
    refresh_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(260)
        self.setMaximumWidth(340)
        self.resize(300, 700)
        self._all_chats: List[TelegramChat] = []
        self._current_filter: str = "ALL"
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("background-color: #18181B; border-right: 1px solid #3F3F46;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Header Bar: Chats Title + Refresh button
        header_layout = QHBoxLayout()
        header_title = QLabel("Chats")
        header_font = QFont()
        header_font.setPointSize(14)
        header_font.setBold(True)
        header_title.setFont(header_font)
        header_title.setStyleSheet("color: #F4F4F5;")
        header_layout.addWidget(header_title)

        header_layout.addStretch()

        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.setObjectName("secondaryButton")
        self.btn_refresh.setStyleSheet("padding: 3px 8px; font-size: 11px;")
        self.btn_refresh.clicked.connect(self.refresh_requested.emit)
        header_layout.addWidget(self.btn_refresh)
        layout.addLayout(header_layout)

        # Search Box
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search chats...")
        self.search_input.textChanged.connect(self._apply_filter)
        layout.addWidget(self.search_input)

        # Filter Tabs: All, Private, Groups, Channels, Saved Messages
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(2)

        self.btn_filter_all = QPushButton("All")
        self.btn_filter_users = QPushButton("Private")
        self.btn_filter_groups = QPushButton("Groups")
        self.btn_filter_channels = QPushButton("Channels")

        self.filter_buttons = [
            (self.btn_filter_all, "ALL"),
            (self.btn_filter_users, "USER"),
            (self.btn_filter_groups, "GROUP"),
            (self.btn_filter_channels, "CHANNEL"),
        ]

        for btn, cat in self.filter_buttons:
            btn.setObjectName("filterTabButton")
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked=False, c=cat: self._set_category_filter(c))
            filter_layout.addWidget(btn)

        self.btn_filter_all.setChecked(True)
        layout.addLayout(filter_layout)

        # List Widget
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(
            """
            QListWidget {
                background-color: transparent;
                border: none;
                outline: none;
            }
            QListWidget::item {
                border-radius: 8px;
                margin: 2px 0px;
            }
            QListWidget::item:selected {
                background-color: #27272A;
                border-left: 3px solid #229ED9;
            }
            QListWidget::item:hover:!selected {
                background-color: #1C1C1F;
            }
            """
        )
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.list_widget)

    @property
    def chats(self) -> List[TelegramChat]:
        """Return the current full list of discovered chats."""
        return self._all_chats

    def set_chats(self, chats: List[TelegramChat]):
        """Populate the list with discovered chats."""
        self._all_chats = chats
        self._apply_filter()

    def _set_category_filter(self, category: str):
        """Update active category filter."""
        self._current_filter = category
        for btn, cat in self.filter_buttons:
            btn.setChecked(cat == category)
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

    def _on_item_clicked(self, item: QListWidgetItem):
        """Handle chat selection in the list."""
        chat: TelegramChat = item.data(Qt.UserRole)
        if chat:
            logger.info("Selected chat: %s (ID: %d)", chat.display_name, chat.id)
            self.chat_selected.emit(chat)

