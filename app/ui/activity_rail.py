"""Leftmost activity icon rail navigation bar for Telegram File Explorer."""

from typing import Optional
from PySide6.QtCore import Qt, Signal, QRectF
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class RailIconButton(QPushButton):
    """Activity rail icon button with active orange indicator bar."""

    def __init__(self, icon_text: str, tooltip: str, parent=None):
        super().__init__(parent)
        self.icon_text = icon_text
        self.setToolTip(tooltip)
        self.setFixedSize(48, 44)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self._is_active = False

    def set_active(self, active: bool):
        self._is_active = active
        self.setChecked(active)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect()

        # Background on hover / active
        if self._is_active:
            # Active orange left indicator pill
            painter.setBrush(QBrush(QColor("#ff7a00")))
            painter.setPen(Qt.NoPen)
            indicator_path = QPainterPath()
            indicator_path.addRoundedRect(0, 8, 4, rect.height() - 16, 2, 2)
            painter.drawPath(indicator_path)

            # Highlighted background
            painter.setBrush(QBrush(QColor("#1e2130")))
            painter.drawRoundedRect(6, 4, rect.width() - 10, rect.height() - 8, 6, 6)
        elif self.underMouse():
            painter.setBrush(QBrush(QColor("#1a1c29")))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(6, 4, rect.width() - 10, rect.height() - 8, 6, 6)

        # Draw Icon Text
        font = QFont()
        font.setPointSize(16 if len(self.icon_text) <= 2 else 12)
        font.setBold(True)
        painter.setFont(font)

        if self._is_active:
            painter.setPen(QColor("#ff9933"))
        elif self.underMouse():
            painter.setPen(QColor("#ffffff"))
        else:
            painter.setPen(QColor("#64748b"))

        painter.drawText(rect, Qt.AlignCenter, self.icon_text)


class ActivityRailWidget(QWidget):
    """Slim 56px leftmost navigation rail matching modern SaaS aesthetics."""

    nav_changed = Signal(int)       # Emits index: 0=Chats, 1=Files, 2=Indexer, 3=Downloads, 4=Search
    profile_clicked = Signal()
    activity_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(56)
        self._current_index = 0
        self._user_avatar: Optional[QPixmap] = None
        self._user_name: str = "Guest"
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet(
            """
            QWidget {
                background-color: #13141f;
                border-right: 1px solid #1a1c29;
            }
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 12, 4, 12)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignHCenter)

        # Top App Logo Icon (Clean Text Brand)
        self.logo_btn = QPushButton("TG")
        self.logo_btn.setFixedSize(40, 40)
        self.logo_btn.setToolTip("Telegram File Explorer")
        self.logo_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #229ED9;
                color: #ffffff;
                border: none;
                border-radius: 10px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3AAFE8;
            }
            """
        )
        self.logo_btn.clicked.connect(lambda: self.set_current_index(0))
        layout.addWidget(self.logo_btn, alignment=Qt.AlignCenter)

        layout.addSpacing(8)

        # Navigation Buttons
        self.btn_chats = RailIconButton("CH", "Chats & Channels Discovery")
        self.btn_chats.clicked.connect(lambda: self._on_btn_clicked(0))
        layout.addWidget(self.btn_chats, alignment=Qt.AlignCenter)

        self.btn_files = RailIconButton("FL", "All Files Explorer")
        self.btn_files.clicked.connect(lambda: self._on_btn_clicked(1))
        layout.addWidget(self.btn_files, alignment=Qt.AlignCenter)

        self.btn_indexer = RailIconButton("IX", "Media Indexing Manager")
        self.btn_indexer.clicked.connect(lambda: self._on_btn_clicked(2))
        layout.addWidget(self.btn_indexer, alignment=Qt.AlignCenter)

        self.btn_downloads = RailIconButton("DL", "Downloads Inspector")
        self.btn_downloads.clicked.connect(lambda: self._on_btn_clicked(3))
        layout.addWidget(self.btn_downloads, alignment=Qt.AlignCenter)

        self.btn_search = RailIconButton("SR", "Full-Text Search")
        self.btn_search.clicked.connect(lambda: self._on_btn_clicked(4))
        layout.addWidget(self.btn_search, alignment=Qt.AlignCenter)

        self.buttons = [self.btn_chats, self.btn_files, self.btn_indexer, self.btn_downloads, self.btn_search]
        self.set_current_index(0)

        layout.addStretch()

        # Bottom Activity Button (Status)
        self.btn_activity = RailIconButton("ST", "System & Network Activity")
        self.btn_activity.clicked.connect(self.activity_clicked.emit)
        layout.addWidget(self.btn_activity, alignment=Qt.AlignCenter)

        # Bottom Circular Profile Avatar Button
        self.btn_avatar = QPushButton()
        self.btn_avatar.setFixedSize(36, 36)
        self.btn_avatar.setCursor(Qt.PointingHandCursor)
        self.btn_avatar.setToolTip("Account Profile & Settings")
        self.btn_avatar.setStyleSheet("background: transparent; border: none;")
        self.btn_avatar.clicked.connect(self.profile_clicked.emit)
        self._render_avatar_btn()
        layout.addWidget(self.btn_avatar, alignment=Qt.AlignCenter)

    def _on_btn_clicked(self, index: int):
        self.set_current_index(index)
        self.nav_changed.emit(index)

    def set_current_index(self, index: int):
        self._current_index = index
        for i, btn in enumerate(self.buttons):
            btn.set_active(i == index)

    def set_user_info(self, name: str, is_authenticated: bool):
        self._user_name = name or "Guest"
        self._render_avatar_btn(is_authenticated)

    def _render_avatar_btn(self, is_authenticated: bool = False):
        size = 36
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # Circle clip
        path = QPainterPath()
        path.addEllipse(1, 1, size - 2, size - 2)
        painter.setClipPath(path)

        bg_color = QColor("#2f66ee") if is_authenticated else QColor("#334155")
        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.NoPen)
        painter.drawRect(0, 0, size, size)

        # Letter
        initial = (self._user_name or "G")[0].upper()
        painter.setPen(QColor("#ffffff"))
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(QRectF(0, 0, size, size), Qt.AlignCenter, initial)

        painter.end()

        from PySide6.QtGui import QIcon
        self.btn_avatar.setIcon(QIcon(pixmap))
        self.btn_avatar.setIconSize(self.btn_avatar.size())
