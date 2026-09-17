"""Animated controls providing smooth 100ms hover transitions and 120ms segmented control indicators."""

from typing import Dict, List, Optional, Tuple
from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QRect,
    QRectF,
    QSize,
    Qt,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .fonts import get_body_font
from .theme_manager import DARK_TOKENS, theme_manager


class AnimatedHoverButton(QPushButton):
    """Button featuring smooth 100ms ease background interpolation on hover."""

    def __init__(
        self,
        text: str = "",
        parent=None,
        icon: Optional[QIcon] = None,
        border_radius: int = 6,
        is_ghost: bool = False,
        ghost_color: Optional[str] = None,
    ):
        super().__init__(text, parent)
        if icon:
            self.setIcon(icon)
        self.border_radius = border_radius
        self.is_ghost = is_ghost
        self.ghost_color = ghost_color

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hover_progress: float = 0.0

        self._anim = QVariantAnimation(self)
        self._anim.setDuration(100)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._anim.valueChanged.connect(self._on_anim_value_changed)

    def _on_anim_value_changed(self, value: float):
        self._hover_progress = value
        self.update()

    def enterEvent(self, event):
        self._anim.stop()
        self._anim.setStartValue(self._hover_progress)
        self._anim.setEndValue(1.0)
        self._anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._anim.stop()
        self._anim.setStartValue(self._hover_progress)
        self._anim.setEndValue(0.0)
        self._anim.start()
        super().leaveEvent(event)

    def paintEvent(self, event):
        tokens = theme_manager.get_active_tokens()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        path = QPainterPath()
        path.addRoundedRect(QRectF(rect).adjusted(0.5, 0.5, -0.5, -0.5), self.border_radius, self.border_radius)

        if self.is_ghost and self.ghost_color:
            # Ghost danger / accent button
            base_c = QColor(0, 0, 0, 0)
            hover_c = QColor(self.ghost_color)
            hover_c.setAlphaF(0.12)
            bg = QColor(
                int(base_c.red() + (hover_c.red() - base_c.red()) * self._hover_progress),
                int(base_c.green() + (hover_c.green() - base_c.green()) * self._hover_progress),
                int(base_c.blue() + (hover_c.blue() - base_c.blue()) * self._hover_progress),
                int(base_c.alpha() + (hover_c.alpha() - base_c.alpha()) * self._hover_progress),
            )
            painter.fillPath(path, bg)

            pen = QPen(QColor(self.ghost_color), 1)
            painter.strokePath(path, pen)

            painter.setPen(QColor(self.ghost_color))
        else:
            # Standard secondary / tool row button
            base_c = QColor(tokens["bg_surface"])
            hover_c = QColor(tokens["bg_hover"])
            bg = QColor(
                int(base_c.red() + (hover_c.red() - base_c.red()) * self._hover_progress),
                int(base_c.green() + (hover_c.green() - base_c.green()) * self._hover_progress),
                int(base_c.blue() + (hover_c.blue() - base_c.blue()) * self._hover_progress),
                255,
            )
            painter.fillPath(path, bg)

            pen = QPen(QColor(tokens["border"]), 1)
            painter.strokePath(path, pen)

            painter.setPen(QColor(tokens["text_primary"]))

        painter.setFont(self.font())

        # Draw icon & text
        icon = self.icon()
        icon_size = self.iconSize() if not self.iconSize().isEmpty() else QSize(16, 16)
        text = self.text()

        if not icon.isNull() and text:
            fm = QFontMetrics(self.font())
            total_content_w = icon_size.width() + 8 + fm.horizontalAdvance(text)
            start_x = (rect.width() - total_content_w) // 2
            if self.styleSheet() and "text-align: left" in self.styleSheet():
                start_x = 12

            icon_y = (rect.height() - icon_size.height()) // 2
            icon.paint(painter, start_x, icon_y, icon_size.width(), icon_size.height())

            text_rect = QRect(start_x + icon_size.width() + 8, 0, rect.width() - (start_x + icon_size.width() + 8), rect.height())
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)
        elif not icon.isNull():
            icon_x = (rect.width() - icon_size.width()) // 2
            icon_y = (rect.height() - icon_size.height()) // 2
            icon.paint(painter, icon_x, icon_y, icon_size.width(), icon_size.height())
        elif text:
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

        painter.end()


class AnimatedSegmentedControl(QFrame):
    """Segmented bar container with 120ms animated active pill sliding indicator."""

    valueChanged = Signal(str)

    def __init__(
        self,
        options: List[Tuple[str, str]],  # (Label, Key)
        current_value: str,
        parent=None,
    ):
        super().__init__(parent)
        self.options = options
        self._current_value = current_value
        self._target_index = 0
        for i, (_, key) in enumerate(options):
            if key == current_value:
                self._target_index = i
                break

        self._indicator_pos: float = float(self._target_index)

        self._anim = QVariantAnimation(self)
        self._anim.setDuration(120)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_anim_step)

        self.buttons: List[QPushButton] = []
        self._init_ui()
        theme_manager.theme_changed.connect(self._on_theme_changed)

    def _on_theme_changed(self, _=None):
        self._update_button_visuals()
        self.update()

    def _init_ui(self):
        self.setFixedHeight(36)
        self.setMinimumWidth(0)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(3, 3, 3, 3)
        self.layout.setSpacing(2)

        for i, (label, key) in enumerate(self.options):
            btn = QPushButton(label)
            btn.setObjectName("segmentedItemButton")
            btn.setCheckable(True)
            btn.setChecked(key == self._current_value)
            btn.setFont(get_body_font(label))
            btn.setMinimumWidth(0)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, idx=i, k=key: self._on_item_clicked(idx, k))
            self.layout.addWidget(btn, 1)
            self.buttons.append(btn)
        self._update_button_visuals()

    def _update_button_visuals(self):
        for i, btn in enumerate(self.buttons):
            btn.setChecked(i == self._target_index)
        self.update()

    def _on_item_clicked(self, index: int, key: str):
        self._current_value = key
        self._target_index = index

        for i, btn in enumerate(self.buttons):
            btn.setChecked(i == index)

        self._update_button_visuals()
        self._anim.stop()
        self._anim.setStartValue(self._indicator_pos)
        self._anim.setEndValue(float(index))
        self._anim.start()

        self.valueChanged.emit(key)

    def _on_anim_step(self, val: float):
        self._indicator_pos = val
        self.update()

    def set_value(self, key: str):
        for i, (_, k) in enumerate(self.options):
            if k == key:
                self._current_value = key
                self._target_index = i
                for j, btn in enumerate(self.buttons):
                    btn.setChecked(j == i)
                self._indicator_pos = float(i)
                self._update_button_visuals()
                self.update()
                break

    def current_value(self) -> str:
        return self._current_value

    def paintEvent(self, event):
        tokens = theme_manager.get_active_tokens()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()

        # Outer segmented bar background: var(--bg-surface), 1px border, 6px radius
        bg_path = QPainterPath()
        bg_path.addRoundedRect(QRectF(rect).adjusted(0.5, 0.5, -0.5, -0.5), 6, 6)
        painter.fillPath(bg_path, QColor(tokens["bg_surface"]))
        painter.strokePath(bg_path, QPen(QColor(tokens["border"]), 1))

        # Sliding active pill indicator: var(--accent-muted) background, 4px radius
        if self.buttons:
            btn_count = len(self.buttons)
            available_w = rect.width() - 6  # 3px margins each side
            item_w = available_w / btn_count
            pill_x = 3 + self._indicator_pos * item_w
            pill_y = 3
            pill_h = rect.height() - 6

            pill_rect = QRectF(pill_x, pill_y, item_w, pill_h)
            pill_path = QPainterPath()
            pill_path.addRoundedRect(pill_rect, 4, 4)

            # Accent-muted background: Qt QColor cannot parse 'rgba(...)' string constructor
            is_dark = (tokens.get("bg_base") == DARK_TOKENS["bg_base"])
            accent_color = QColor(tokens["accent"])
            accent_color.setAlphaF(0.12 if is_dark else 0.10)
            painter.fillPath(pill_path, accent_color)

        painter.end()
        super().paintEvent(event)
