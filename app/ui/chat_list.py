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
    ChatType.CHANNEL: "#2f66ee",       # Vibrant Blue
    ChatType.SUPERGROUP: "#38bdf8",    # Sky Blue
    ChatType.GROUP: "#10b981",         # Emerald Green
    ChatType.USER: "#64748b",          # Slate
    ChatType.BOT: "#ec4899",           # Pink
    ChatType.SAVED_MESSAGES: "#f59e0b" # Amber
}


class ChatListItemWidget(QWidget):
    """Custom widget rendered for each chat in QListWidget."""

    def __init__(self, chat: TelegramChat, parent=None):
        super().__init__(parent)
        self.chat = chat
        self.setFixedHeight(56)
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(10)

        # Avatar Label
        self.avatar_label = QLabel()
        self.avatar_label.setFixedSize(38, 38)
        self.avatar_label.setPixmap(self._generate_avatar())
        layout.addWidget(self.avatar_label)

        # Text Details (Title, Type badge, Subtitle info)
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        text_layout.setAlignment(Qt.AlignVCenter)

        # Top row: Title + Type Badge / Lock icon
        top_row = QHBoxLayout()
        top_row.setSpacing(6)

        prefix = "🔒 " if self.chat.chat_type == ChatType.USER else ""
        title_label = QLabel(f"{prefix}{self.chat.display_name}")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(10)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #f1f5f9;")
        top_row.addWidget(title_label)

        badge_color = TYPE_COLORS.get(self.chat.chat_type, "#2f66ee")
        type_badge = QLabel(f" {self.chat.chat_type.value} ")
        type_badge.setStyleSheet(
            f"background-color: {badge_color}; color: #ffffff; border-radius: 4px; font-size: 9px; font-weight: bold; padding: 1px 4px;"
        )
        top_row.addWidget(type_badge)
        top_row.addStretch()

        text_layout.addLayout(top_row)

        # Bottom row: Subtitle tag e.g. • Channel 12.4k or @username
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(6)

        info_text = f"• ID: {self.chat.id}"
        if self.chat.username:
            info_text = f"• @{self.chat.username}"
        id_label = QLabel(info_text)
        id_label.setStyleSheet("color: #64748b; font-size: 11px;")
        bottom_row.addWidget(id_label)

        bottom_row.addStretch()
        text_layout.addLayout(bottom_row)

        layout.addLayout(text_layout)

        # Unread Count Badge
        if self.chat.unread_count > 0:
            unread_badge = QLabel(f"{self.chat.unread_count}")
            unread_badge.setStyleSheet(
                "background-color: #2f66ee; color: #ffffff; border-radius: 9px; font-size: 10px; font-weight: bold; min-width: 18px; padding: 1px 5px;"
            )
            unread_badge.setAlignment(Qt.AlignCenter)
            layout.addWidget(unread_badge)

    def _generate_avatar(self) -> QPixmap:
        """Create circular avatar with image or colored initials."""
        size = 38
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
        palette = ["#2f66ee", "#10b981", "#f59e0b", "#ec4899", "#ef4444", "#38bdf8"]
        bg_color = QColor(palette[color_seed])

        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.NoPen)
        painter.drawRect(0, 0, size, size)

        # Initial letter
        initial = (self.chat.display_name or "?")[0].upper()
        painter.setPen(QColor("#ffffff"))
        font = QFont()
        font.setPointSize(13)
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
        self.setStyleSheet("background-color: #1a1c29; border: none;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Header Bar: Title "Telegram Explorer ▾" + Refresh
        header_layout = QHBoxLayout()
        header_title = QLabel("Platform ▾")
        header_font = QFont()
        header_font.setPointSize(13)
        header_font.setBold(True)
        header_title.setFont(header_font)
        header_title.setStyleSheet("color: #ffffff;")
        header_layout.addWidget(header_title)

        header_layout.addStretch()

        self.btn_refresh = QPushButton("🔄")
        self.btn_refresh.setFixedSize(28, 28)
        self.btn_refresh.setToolTip("Refresh discovered chats")
        self.btn_refresh.setStyleSheet(
            """
            QPushButton {
                background-color: #24273b;
                color: #94a3b8;
                border: 1px solid #2e3248;
                border-radius: 6px;
                padding: 0;
            }
            QPushButton:hover {
                background-color: #2f334d;
                color: #ffffff;
            }
            """
        )
        self.btn_refresh.clicked.connect(self.refresh_requested.emit)
        header_layout.addWidget(self.btn_refresh)
        layout.addLayout(header_layout)

        # Search Box
        self.search_input = QLineEdit()
        self.search_input.setObjectName("darkSearchInput")
        self.search_input.setPlaceholderText("🔍 Search chats & channels...")
        self.search_input.textChanged.connect(self._apply_filter)
        layout.addWidget(self.search_input)

        # Section Header: CHATS / SOURCES ▾
        section_layout = QHBoxLayout()
        section_label = QLabel("📁 CHATS ▾")
        section_label.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: bold;")
        section_layout.addWidget(section_label)
        section_layout.addStretch()

        self.count_label = QLabel("0 chats")
        self.count_label.setStyleSheet("color: #64748b; font-size: 11px;")
        section_layout.addWidget(self.count_label)
        layout.addLayout(section_layout)

        # Category Filter Pills
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
            btn.setStyleSheet(
                """
                QPushButton {
                    background-color: #24273b;
                    color: #94a3b8;
                    border: 1px solid #2e3248;
                    border-radius: 12px;
                    padding: 3px 8px;
                    font-size: 10px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #2f334d;
                    color: #ffffff;
                }
                """
            )
            btn.clicked.connect(lambda checked=False, c=cat: self._set_category_filter(c))
            filter_layout.addWidget(btn)

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
                background-color: #282b3e;
                border: 1px solid #373a4f;
            }
            QListWidget::item:hover:!selected {
                background-color: #202334;
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
            item.setSizeHint(QSize(0, 56))
            item.setData(Qt.UserRole, chat)

            widget = ChatListItemWidget(chat)
            self.list_widget.setItemWidget(item, widget)
            matched += 1

        self.count_label.setText(f"{matched} chats")

    def _on_item_clicked(self, item: QListWidgetItem):
        """Handle chat selection in the list."""
        chat: TelegramChat = item.data(Qt.UserRole)
        if chat:
            logger.info("Selected chat: %s (ID: %d)", chat.display_name, chat.id)
            self.chat_selected.emit(chat)

