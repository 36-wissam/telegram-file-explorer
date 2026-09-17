"""Chat sidebar and rail widget conforming strictly to design specifications (280px expanded, 72px collapsed rail)."""

from typing import List, Optional
from pathlib import Path
from PySide6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPoint,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..core.logger import get_logger
from ..telegram.chats import ChatType, TelegramChat
from .fonts import (
    get_body_font,
    get_caption_font,
    get_font_for_text,
    get_section_header_font,
    get_secondary_font,
    get_title_font,
)
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


def generate_avatar_pixmap(
    chat: Optional[TelegramChat],
    size: int = 40,
    is_selected: bool = False,
    custom_initial: str = "",
) -> QPixmap:
    """Create circular avatar with image or colored initials."""
    target = QPixmap(size, size)
    target.fill(Qt.transparent)

    painter = QPainter(target)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    path = QPainterPath()
    path.addEllipse(0, 0, size, size)
    painter.setClipPath(path)

    if chat and chat.avatar_path and Path(chat.avatar_path).exists():
        img = QPixmap(chat.avatar_path)
        if not img.isNull():
            painter.drawPixmap(
                0,
                0,
                size,
                size,
                img.scaled(
                    size,
                    size,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                ),
            )
            painter.end()
            return target

    tokens = theme_manager.get_active_tokens()
    if is_selected:
        bg_color = QColor(tokens["accent"])
        text_color = QColor("#FFFFFF")
    elif custom_initial == "W":
        bg_color = QColor(tokens["accent"])
        text_color = QColor("#FFFFFF")
    else:
        bg_color = QColor(tokens["bg_surface_2"])
        text_color = QColor(tokens["text_secondary"])

    painter.setBrush(QBrush(bg_color))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRect(0, 0, size, size)

    initial = custom_initial
    if not initial:
        name = (chat.display_name if chat else "?") or "?"
        parts = name.strip().split()
        if len(parts) >= 2:
            initial = (parts[0][:1] + parts[1][:1]).upper()
        else:
            initial = name[:2].upper()

    painter.setPen(text_color)
    font = get_font_for_text(initial, pixel_size=max(11, size // 3), weight=600)
    painter.setFont(font)
    painter.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, initial)
    painter.end()
    return target


class ChatListItemWidget(QWidget):
    """Custom widget rendered for each chat in QListWidget (64px row height, 40px circular avatar)."""

    def __init__(self, chat: TelegramChat, is_selected: bool = False, parent=None):
        super().__init__(parent)
        self.chat = chat
        self.is_selected = is_selected
        self.setFixedHeight(64)
        self._init_ui()

    def _init_ui(self):
        tokens = theme_manager.get_active_tokens()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        self.avatar_label = QLabel()
        self.avatar_label.setFixedSize(40, 40)
        self.avatar_label.setPixmap(generate_avatar_pixmap(self.chat, 40, is_selected=self.is_selected))
        layout.addWidget(self.avatar_label)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(3)
        text_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        top_row = QHBoxLayout()
        top_row.setSpacing(6)

        title_label = QLabel(self.chat.display_name)
        title_label.setObjectName("chatItemTitle")
        title_label.setFont(get_font_for_text(self.chat.display_name, pixel_size=13, weight=600))
        top_row.addWidget(title_label)

        top_row.addStretch()

        time_str = ""
        if self.chat.last_message_date:
            time_str = self.chat.last_message_date.strftime("%H:%M")
        time_label = QLabel(time_str)
        time_label.setObjectName("chatItemTime")
        time_label.setFont(get_caption_font(time_str))
        top_row.addWidget(time_label)

        text_layout.addLayout(top_row)

        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(6)

        info_text = f"@{self.chat.username}" if self.chat.username else self.chat.chat_type.value
        subtitle_label = QLabel(info_text)
        subtitle_label.setObjectName("chatItemSubtitle")
        subtitle_label.setFont(get_secondary_font(info_text))
        bottom_row.addWidget(subtitle_label)

        bottom_row.addStretch()

        if self.chat.unread_count > 0:
            unread_badge = QLabel(str(self.chat.unread_count))
            unread_badge.setStyleSheet(
                f"background-color: {tokens['accent']}; color: #FFFFFF; border-radius: 9px; font-size: 11px; font-weight: 600; min-width: 18px; padding: 1px 6px;"
            )
            unread_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            bottom_row.addWidget(unread_badge)

        text_layout.addLayout(bottom_row)
        layout.addLayout(text_layout)


class RailAvatarButton(QPushButton):
    """Circular 40x40 avatar button for collapsed 72px rail mode."""

    def __init__(self, chat: TelegramChat, is_selected: bool = False, parent=None):
        super().__init__(parent)
        self.chat = chat
        self._is_selected = is_selected
        self.setFixedSize(44, 44)
        self.setToolTip(f"{chat.display_name} ({chat.chat_type.value})")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("background: transparent; border: none; padding: 2px;")
        self._update_icon()

    def set_selected(self, selected: bool):
        self._is_selected = selected
        self._update_icon()

    def _update_icon(self):
        pixmap = generate_avatar_pixmap(self.chat, 40, is_selected=self._is_selected)
        self.setIcon(pixmap)
        self.setIconSize(QSize(40, 40))


class ChatListWidget(QWidget):
    """Dual-mode sidebar: Animated collapsible between 72px Rail and 280px Expanded Sidebar."""

    chat_selected = Signal(object)
    refresh_requested = Signal()
    settings_clicked = Signal()
    collapsed_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_chats: List[TelegramChat] = []
        self._current_filter: str = "ALL"
        self._is_collapsed: bool = False
        self._selected_chat_id: Optional[int] = None
        self._pending_chat: Optional[TelegramChat] = None

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(150)
        self._debounce_timer.timeout.connect(self._emit_debounced_chat)

        self._init_ui()
        self.set_collapsed(False)
        theme_manager.theme_changed.connect(self._on_theme_changed)
        theme_manager.language_changed.connect(self._on_language_changed)

    @property
    def is_collapsed(self) -> bool:
        return self._is_collapsed

    def _init_ui(self):
        tokens = theme_manager.get_active_tokens()
        self._apply_theme_styles(tokens)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.mode_stack = QStackedWidget(self)
        self.main_layout.addWidget(self.mode_stack)

        # --- Page 0: Expanded Sidebar (280px) ---
        self.expanded_container = QWidget()
        exp_layout = QVBoxLayout(self.expanded_container)
        exp_layout.setContentsMargins(12, 12, 12, 12)
        exp_layout.setSpacing(10)

        # Header: 'W' Avatar + Title 'Telegram File Explorer' + Collapse Chevron '<'
        header_row = QHBoxLayout()
        header_row.setSpacing(10)

        self.btn_user_avatar = QLabel()
        self.btn_user_avatar.setFixedSize(36, 36)
        self.btn_user_avatar.setPixmap(generate_avatar_pixmap(None, 36, custom_initial="W"))
        header_row.addWidget(self.btn_user_avatar)

        self.lbl_app_title = QLabel("Telegram File Explorer")
        self.lbl_app_title.setObjectName("sidebarAppTitle")
        self.lbl_app_title.setFont(get_section_header_font("Telegram File Explorer"))
        header_row.addWidget(self.lbl_app_title)

        header_row.addStretch()

        self.btn_collapse = QPushButton()
        self.btn_collapse.setIcon(get_icon("chevron_left", color=tokens["text_secondary"], size=16))
        self.btn_collapse.setFixedSize(28, 28)
        self.btn_collapse.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_collapse.setStyleSheet("background: transparent; border: none; border-radius: 4px;")
        self.btn_collapse.setToolTip("Collapse Sidebar")
        self.btn_collapse.clicked.connect(self.toggle_collapse)
        header_row.addWidget(self.btn_collapse)

        exp_layout.addLayout(header_row)

        # Search Input
        self.search_input = QLineEdit()
        self.search_input.setObjectName("chatSearchInput")
        self.search_input.setPlaceholderText("Search chats...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setFixedHeight(36)
        self.search_input.setFont(get_body_font("Search"))
        self.search_input.textChanged.connect(self._apply_filter)
        exp_layout.addWidget(self.search_input)

        # Compatibility refresh button
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.setObjectName("secondaryButton")
        self.btn_refresh.setIcon(get_icon("refresh_cw", color=tokens["text_secondary"], size=13))
        self.btn_refresh.clicked.connect(self.refresh_requested.emit)
        self.btn_refresh.hide()

        # Chat List Widget
        self.list_widget = QListWidget()
        self.list_widget.setObjectName("chatListWidget")
        self.list_widget.itemClicked.connect(self._on_list_item_clicked)
        exp_layout.addWidget(self.list_widget)

        # Bottom Settings Row
        bottom_settings_row = QHBoxLayout()
        self.btn_settings_expanded = QPushButton("Settings")
        self.btn_settings_expanded.setObjectName("sidebarSettingsBtn")
        self.btn_settings_expanded.setIcon(get_icon("settings", color=tokens["text_secondary"], size=18))
        self.btn_settings_expanded.setFont(get_body_font("Settings"))
        self.btn_settings_expanded.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_settings_expanded.clicked.connect(self.settings_clicked.emit)
        bottom_settings_row.addWidget(self.btn_settings_expanded)
        exp_layout.addLayout(bottom_settings_row)

        self.mode_stack.addWidget(self.expanded_container)

        # --- Page 1: Collapsed Rail (72px) ---
        self.rail_container = QWidget()
        rail_layout = QVBoxLayout(self.rail_container)
        rail_layout.setContentsMargins(8, 12, 8, 12)
        rail_layout.setSpacing(12)
        rail_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        top_rail_row = QHBoxLayout()
        top_rail_row.setSpacing(4)
        top_rail_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_rail_avatar = QPushButton()
        self.btn_rail_avatar.setFixedSize(40, 40)
        self.btn_rail_avatar.setIcon(generate_avatar_pixmap(None, 40, custom_initial="W"))
        self.btn_rail_avatar.setIconSize(QSize(40, 40))
        self.btn_rail_avatar.setStyleSheet("background: transparent; border: none;")
        self.btn_rail_avatar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_rail_avatar.clicked.connect(self.toggle_collapse)
        top_rail_row.addWidget(self.btn_rail_avatar)

        self.btn_expand = QPushButton()
        self.btn_expand.setIcon(get_icon("chevron_right", color=tokens["text_secondary"], size=14))
        self.btn_expand.setFixedSize(20, 28)
        self.btn_expand.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_expand.setStyleSheet("background: transparent; border: none;")
        self.btn_expand.setToolTip("Expand Sidebar")
        self.btn_expand.clicked.connect(self.toggle_collapse)
        top_rail_row.addWidget(self.btn_expand)

        rail_layout.addLayout(top_rail_row)

        self.rail_scroll = QScrollArea()
        self.rail_scroll.setWidgetResizable(True)
        self.rail_scroll.setStyleSheet("background: transparent; border: none;")
        self.rail_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.rail_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.rail_items_container = QWidget()
        self.rail_items_container.setStyleSheet("background: transparent;")
        self.rail_items_layout = QVBoxLayout(self.rail_items_container)
        self.rail_items_layout.setContentsMargins(0, 4, 0, 4)
        self.rail_items_layout.setSpacing(8)
        self.rail_items_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.rail_scroll.setWidget(self.rail_items_container)
        rail_layout.addWidget(self.rail_scroll)

        self.btn_settings_rail = QPushButton()
        self.btn_settings_rail.setFixedSize(40, 40)
        self.btn_settings_rail.setIcon(get_icon("settings", color=tokens["text_secondary"], size=20))
        self.btn_settings_rail.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_settings_rail.setStyleSheet("background: transparent; border: none; border-radius: 6px;")
        self.btn_settings_rail.setToolTip("Settings")
        self.btn_settings_rail.clicked.connect(self.settings_clicked.emit)
        rail_layout.addWidget(self.btn_settings_rail, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.mode_stack.addWidget(self.rail_container)

    def _apply_theme_styles(self, tokens: dict):
        pass

    def _on_theme_changed(self, tokens: dict):
        self.btn_collapse.setIcon(get_icon("chevron_left", color=tokens["text_secondary"], size=16))
        self.btn_expand.setIcon(get_icon("chevron_right", color=tokens["text_secondary"], size=14))
        self.btn_settings_rail.setIcon(get_icon("settings", color=tokens["text_secondary"], size=20))
        self.btn_settings_expanded.setIcon(get_icon("settings", color=tokens["text_secondary"], size=18))
        self.list_widget.viewport().update()
        self.rail_scroll.viewport().update()

    def _on_language_changed(self, lang: str):
        if lang == "ar":
            self.search_input.setPlaceholderText("بحث بالمحادثات...")
            self.btn_settings_expanded.setText("الإعدادات")
        else:
            self.search_input.setPlaceholderText("Search chats...")
            self.btn_settings_expanded.setText("Settings")

    @property
    def chats(self) -> List[TelegramChat]:
        return self._all_chats

    def set_chats(self, chats: List[TelegramChat]):
        self._all_chats = chats
        self._apply_filter()

    def set_collapsed(self, collapsed: bool, animate: bool = False):
        self._is_collapsed = collapsed
        target_w = 72 if collapsed else 280

        if animate:
            # 180ms ease transition
            self._anim = QPropertyAnimation(self, b"maximumWidth")
            self._anim.setDuration(180)
            self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
            self._anim.setStartValue(self.width())
            self._anim.setEndValue(target_w)

            self._anim_min = QPropertyAnimation(self, b"minimumWidth")
            self._anim_min.setDuration(180)
            self._anim_min.setEasingCurve(QEasingCurve.Type.InOutCubic)
            self._anim_min.setStartValue(self.width())
            self._anim_min.setEndValue(target_w)

            def on_finish():
                self.setFixedWidth(target_w)
                self.mode_stack.setCurrentIndex(1 if collapsed else 0)

            self._anim.finished.connect(on_finish)
            self._anim.start()
            self._anim_min.start()
        else:
            self.setFixedWidth(target_w)
            self.mode_stack.setCurrentIndex(1 if collapsed else 0)

        self.collapsed_changed.emit(collapsed)

    def toggle_collapse(self, animate: bool = False):
        self.set_collapsed(not self._is_collapsed, animate=animate)

    def _set_category_filter(self, category: str):
        self._current_filter = category
        self._apply_filter()

    def _apply_filter(self):
        query = self.search_input.text().strip().lower()
        self.list_widget.clear()

        while self.rail_items_layout.count():
            item = self.rail_items_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        filtered_chats = []
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
            filtered_chats.append(chat)

        for chat in filtered_chats:
            is_sel = (self._selected_chat_id == chat.id)

            item = QListWidgetItem(self.list_widget)
            item.setSizeHint(QSize(0, 64))
            item.setData(Qt.UserRole, chat)
            widget = ChatListItemWidget(chat, is_selected=is_sel)
            self.list_widget.setItemWidget(item, widget)

            rail_btn = RailAvatarButton(chat, is_selected=is_sel)
            rail_btn.clicked.connect(lambda checked=False, c=chat: self._on_rail_chat_clicked(c))
            self.rail_items_layout.addWidget(rail_btn)

    def _on_list_item_clicked(self, item: QListWidgetItem):
        chat: TelegramChat = item.data(Qt.UserRole)
        if chat:
            self._select_chat_internal(chat)

    def _on_rail_chat_clicked(self, chat: TelegramChat):
        self._select_chat_internal(chat)

    def _select_chat_internal(self, chat: TelegramChat):
        self._selected_chat_id = chat.id
        self._pending_chat = chat
        self._debounce_timer.start()
        self._update_selection_visuals()

    def _update_selection_visuals(self):
        for i in range(self.rail_items_layout.count()):
            w = self.rail_items_layout.itemAt(i).widget()
            if isinstance(w, RailAvatarButton):
                w.set_selected(w.chat.id == self._selected_chat_id)

    def _emit_debounced_chat(self):
        if self._pending_chat:
            logger.info("Selected chat: %s (ID: %d)", self._pending_chat.display_name, self._pending_chat.id)
            self.chat_selected.emit(self._pending_chat)
