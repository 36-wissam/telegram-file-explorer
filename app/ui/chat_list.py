"""Chat sidebar list widget conforming strictly to the Obsidian specification (280px width collapsible to 72px, 64px rows, 40px circular avatars, debounced selection)."""

from typing import List, Optional
from pathlib import Path
from PySide6.QtCore import Qt, Signal, QSize, QRectF, QTimer
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
from .icons import get_icon, get_pixmap
from .theme_manager import theme_manager

logger = get_logger("ui.chat_list")

TYPE_COLORS = {
    ChatType.CHANNEL: "#5C8DFF",
    ChatType.SUPERGROUP: "#7AA2FF",
    ChatType.GROUP: "#3DDC84",
    ChatType.USER: "#9BA1AC",
    ChatType.BOT: "#A855F7",
    ChatType.SAVED_MESSAGES: "#F5A623",
}


class ChatListItemWidget(QWidget):
    """Custom widget rendered for each chat in QListWidget (64px row height, 40px circular avatar)."""

    def __init__(self, chat: TelegramChat, parent=None):
        super().__init__(parent)
        self.chat = chat
        self.setFixedHeight(64)
        self._init_ui()

    def _init_ui(self):
        tokens = theme_manager.get_active_tokens()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        # Avatar Label (40x40 circular)
        self.avatar_label = QLabel()
        self.avatar_label.setFixedSize(40, 40)
        self.avatar_label.setPixmap(self._generate_avatar())
        layout.addWidget(self.avatar_label)

        # Text Details (Title, Last message preview, Timestamp)
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        text_layout.setAlignment(Qt.AlignVCenter)

        # Top row: Title + Timestamp
        top_row = QHBoxLayout()
        top_row.setSpacing(6)

        title_label = QLabel(self.chat.display_name)
        title_font = QFont("Inter", 10)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet(f"color: {tokens['text_primary']};")
        top_row.addWidget(title_label)

        top_row.addStretch()

        # Time
        time_str = ""
        if self.chat.last_message_date:
            time_str = self.chat.last_message_date.strftime("%H:%M")
        time_label = QLabel(time_str)
        time_label.setStyleSheet(f"color: {tokens['text_tertiary']}; font-size: 11px;")
        top_row.addWidget(time_label)

        text_layout.addLayout(top_row)

        # Bottom row: Preview / Subtitle + Unread Badge
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(6)

        info_text = f"@{self.chat.username}" if self.chat.username else self.chat.chat_type.value
        preview_label = QLabel(info_text)
        preview_label.setStyleSheet(f"color: {tokens['text_secondary']}; font-size: 12px;")
        bottom_row.addWidget(preview_label)

        bottom_row.addStretch()

        # Unread Count Badge
        if self.chat.unread_count > 0:
            unread_badge = QLabel(f"{self.chat.unread_count}")
            unread_badge.setStyleSheet(
                f"background-color: {tokens['accent']}; color: #FFFFFF; border-radius: 9px; font-size: 11px; font-weight: 600; min-width: 18px; padding: 1px 6px;"
            )
            unread_badge.setAlignment(Qt.AlignCenter)
            bottom_row.addWidget(unread_badge)

        text_layout.addLayout(bottom_row)
        layout.addLayout(text_layout)

    def _generate_avatar(self) -> QPixmap:
        """Create circular avatar with image or colored initials (40x40)."""
        size = 40
        target_pixmap = QPixmap(size, size)
        target_pixmap.fill(Qt.transparent)

        painter = QPainter(target_pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        path = QPainterPath()
        path.addEllipse(0, 0, size, size)
        painter.setClipPath(path)

        if self.chat.avatar_path and Path(self.chat.avatar_path).exists():
            img_pixmap = QPixmap(self.chat.avatar_path)
            if not img_pixmap.isNull():
                painter.drawPixmap(0, 0, size, size, img_pixmap.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
                painter.end()
                return target_pixmap

        palette = ["#5C8DFF", "#3DDC84", "#F5A623", "#A855F7", "#F1554C", "#7AA2FF"]
        bg_color = QColor(palette[abs(self.chat.id) % len(palette)])

        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.NoPen)
        painter.drawRect(0, 0, size, size)

        initial = (self.chat.display_name or "?")[0].upper()
        painter.setPen(QColor("#FFFFFF"))
        font = QFont("Inter", 12)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(QRectF(0, 0, size, size), Qt.AlignCenter, initial)

        painter.end()
        return target_pixmap


class ChatListWidget(QWidget):
    """280px sidebar widget for chat discovery, debounced selection, and collapsible rail."""

    chat_selected = Signal(object)  # Emits TelegramChat (64-bit safe)
    refresh_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(72)
        self.setMaximumWidth(280)
        self.resize(280, 700)
        self._all_chats: List[TelegramChat] = []
        self._current_filter: str = "ALL"
        self._is_collapsed: bool = False
        self._pending_chat: Optional[TelegramChat] = None

        # 150ms debounce timer for rapid clicking through chats
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(150)
        self._debounce_timer.timeout.connect(self._emit_debounced_chat)

        self._init_ui()

    def _init_ui(self):
        tokens = theme_manager.get_active_tokens()
        self.setStyleSheet(f"background-color: {tokens['bg_surface']}; border-right: 1px solid {tokens['border']};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Header Bar: Chats Title + Refresh button
        header_layout = QHBoxLayout()
        header_title = QLabel("Chats")
        header_font = QFont("Inter", 14)
        header_font.setBold(True)
        header_title.setFont(header_font)
        header_title.setStyleSheet(f"color: {tokens['text_primary']};")
        header_layout.addWidget(header_title)

        header_layout.addStretch()

        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.setObjectName("secondaryButton")
        self.btn_refresh.setIcon(get_icon("refresh_cw", color=tokens["text_secondary"], size=13))
        self.btn_refresh.setToolTip("Refresh chat list from Telegram")
        self.btn_refresh.setStyleSheet("padding: 4px 10px; font-size: 11px;")
        self.btn_refresh.clicked.connect(self.refresh_requested.emit)
        header_layout.addWidget(self.btn_refresh)
        layout.addLayout(header_layout)

        # Search Box
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search chats...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._apply_filter)
        layout.addWidget(self.search_input)

        # Filter Tabs: All, Private, Groups, Channels
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(4)

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
            f"""
            QListWidget {{
                background-color: transparent;
                border: none;
                outline: none;
            }}
            QListWidget::item {{
                border-radius: 10px;
                margin: 2px 0px;
            }}
            QListWidget::item:selected {{
                background-color: {tokens['bg_surface_2']};
                border-left: 3px solid {tokens['accent']};
            }}
            QListWidget::item:hover:!selected {{
                background-color: {tokens['bg_hover']};
            }}
            """
        )
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.list_widget)

    @property
    def chats(self) -> List[TelegramChat]:
        return self._all_chats

    def set_chats(self, chats: List[TelegramChat]):
        self._all_chats = chats
        self._apply_filter()

    def _set_category_filter(self, category: str):
        self._current_filter = category
        for btn, cat in self.filter_buttons:
            btn.setChecked(cat == category)
        self._apply_filter()

    def _apply_filter(self):
        query = self.search_input.text().strip().lower()
        self.list_widget.clear()

        matched = 0
        for chat in self._all_chats:
            if self._current_filter == "CHANNEL" and chat.chat_type != ChatType.CHANNEL:
                continue
            if self._current_filter == "GROUP" and chat.chat_type not in (ChatType.GROUP, ChatType.SUPERGROUP):
                continue
            if self._current_filter == "USER" and chat.chat_type not in (ChatType.USER, ChatType.BOT, ChatType.SAVED_MESSAGES):
                continue

            if query:
                in_title = query in chat.title.lower()
                in_username = chat.username and query in chat.username.lower()
                in_id = query in str(chat.id)
                if not (in_title or in_username or in_id):
                    continue

            item = QListWidgetItem(self.list_widget)
            item.setSizeHint(QSize(0, 64))
            item.setData(Qt.UserRole, chat)

            widget = ChatListItemWidget(chat)
            self.list_widget.setItemWidget(item, widget)
            matched += 1

    def _on_item_clicked(self, item: QListWidgetItem):
        """Handle chat selection with 150ms debounce to eliminate lag on fast clicking."""
        chat: TelegramChat = item.data(Qt.UserRole)
        if chat:
            self._pending_chat = chat
            self._debounce_timer.start()

    def _emit_debounced_chat(self):
        """Emit chat selection signal after debounce window settles."""
        if self._pending_chat:
            logger.info("Debounced selected chat: %s (ID: %d)", self._pending_chat.display_name, self._pending_chat.id)
            self.chat_selected.emit(self._pending_chat)
