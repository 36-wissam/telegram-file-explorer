import os
from PySide6.QtCore import QObject, QPoint, QRect, QRectF, QSize, Qt, Signal, QEvent
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPixmap, QPen
from PySide6.QtWidgets import QStyledItemDelegate, QStyle, QStyleOptionViewItem

from .theme_manager import theme_manager
from .icons import get_pixmap, get_icon
from .fonts import get_font_for_text, get_body_font, get_caption_font, get_secondary_font
from ..services.image_loader import thumbnail_manager
from .media_card import format_bytes
from .media_model import (
    FileIdRole, FilenameRole, SizeRole, DateRole, MediaTypeRole, 
    ThumbnailPathRole, FileModelRole, HasThumbnailRole, CaptionRole, IsDownloadedRole
)


def _get_icon_name_for_type(mtype: str) -> str:
    mtype_str = str(mtype or "").upper()
    if mtype_str == "IMAGE":
        return "image"
    elif mtype_str in ("VIDEO", "ROUND_VIDEO"):
        return "video"
    elif mtype_str in ("AUDIO", "VOICE"):
        return "music"
    elif mtype_str == "ARCHIVE":
        return "archive"
    return "file_text"


class MediaGridDelegate(QStyledItemDelegate):
    """Grid item delegate with persistent 1px accent border on selection and high-contrast icons."""

    download_clicked = Signal(object)
    open_clicked = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_request_id: int = 0

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        return QSize(170, 200)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = option.rect.adjusted(4, 4, -4, -4)
        is_hovered = bool(option.state & QStyle.State_MouseOver)
        is_selected = bool(option.state & QStyle.State_Selected)

        tokens = theme_manager.get_active_tokens()
        
        # Determine background and border
        bg_color = QColor(tokens["bg_surface"])
        border_color = QColor(tokens["border"])
        border_width = 1

        if is_selected:
            bg_color = QColor(tokens["bg_surface_2"])
            border_color = QColor(tokens["accent"])
            border_width = 1  # Persistent 1px accent border per specification
        elif is_hovered:
            bg_color = QColor(tokens["bg_hover"])

        painter.setBrush(QBrush(bg_color))
        pen = QPen(border_color, border_width)
        painter.setPen(pen)
        painter.drawRoundedRect(rect, 10, 10)

        # Thumbnail area (height: 115)
        thumb_rect = QRect(rect.left(), rect.top(), rect.width(), 115)
        
        clip_path = QPainterPath()
        clip_path.addRoundedRect(QRectF(rect), 10, 10)
        painter.setClipPath(clip_path)

        file_id = index.data(FileIdRole)
        thumb_path = index.data(ThumbnailPathRole)
        mtype = index.data(MediaTypeRole)
        
        pixmap = thumbnail_manager.get_cached_pixmap(file_id)
        if not pixmap and thumb_path:
            self.current_request_id += 1
            pixmap = thumbnail_manager.request_thumbnail(self.current_request_id, file_id, thumb_path, 160, 115)
            
        if pixmap and not pixmap.isNull():
            scaled_pixmap = pixmap.scaled(
                thumb_rect.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
            x_offset = (scaled_pixmap.width() - thumb_rect.width()) // 2
            y_offset = (scaled_pixmap.height() - thumb_rect.height()) // 2
            painter.drawPixmap(thumb_rect.topLeft(), scaled_pixmap, QRect(x_offset, y_offset, thumb_rect.width(), thumb_rect.height()))
        else:
            painter.fillRect(thumb_rect, QColor(tokens["bg_surface_2"]))
            icon_name = _get_icon_name_for_type(mtype)
            # High-contrast icon color (text_secondary provides strong contrast in both dark and light modes)
            icon_color = tokens["text_secondary"]
            icon_pixmap = get_pixmap(icon_name, color=icon_color, size=34)
            if not icon_pixmap.isNull():
                ix = thumb_rect.center().x() - icon_pixmap.width() // 2
                iy = thumb_rect.center().y() - icon_pixmap.height() // 2
                painter.drawPixmap(ix, iy, icon_pixmap)

        painter.setClipping(False)

        # Filename
        filename = index.data(FilenameRole) or "Unknown File"
        file_size = index.data(SizeRole) or 0
        
        text_rect = QRect(rect.left() + 8, thumb_rect.bottom() + 8, rect.width() - 16, 20)
        
        font = get_font_for_text(filename, pixel_size=13, weight=500)
        painter.setFont(font)
        painter.setPen(QColor(tokens["text_primary"]))
        
        fm = QFontMetrics(font)
        elided_text = fm.elidedText(filename, Qt.TextElideMode.ElideRight, text_rect.width())
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, elided_text)
        
        # File Size
        size_str = format_bytes(file_size)
        size_rect = QRect(rect.left() + 8, text_rect.bottom() + 4, rect.width() - 16, 16)
        size_font = get_caption_font(size_str)
        painter.setFont(size_font)
        painter.setPen(QColor(tokens["text_tertiary"]))
        painter.drawText(size_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, size_str)

        painter.restore()


class MediaListDelegate(QStyledItemDelegate):
    """List item delegate with persistent 1px accent highlight on selection."""

    download_clicked = Signal(object)
    open_clicked = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_request_id: int = 0

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        return QSize(option.rect.width(), 48)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = option.rect
        is_hovered = bool(option.state & QStyle.State_MouseOver)
        is_selected = bool(option.state & QStyle.State_Selected)

        tokens = theme_manager.get_active_tokens()
        
        if is_selected:
            painter.fillRect(rect, QColor(tokens["bg_surface_2"]))
            pen = QPen(QColor(tokens["accent"]), 1)
            painter.setPen(pen)
            painter.drawRect(rect.adjusted(0, 0, -1, -1))
        elif is_hovered:
            painter.fillRect(rect, QColor(tokens["bg_hover"]))

        # Thumbnail/Icon (40x40, rounded 6px)
        thumb_rect = QRect(rect.left() + 8, rect.top() + 4, 40, 40)
        
        file_id = index.data(FileIdRole)
        thumb_path = index.data(ThumbnailPathRole)
        mtype = index.data(MediaTypeRole)
        
        pixmap = thumbnail_manager.get_cached_pixmap(file_id)
        if not pixmap and thumb_path:
            self.current_request_id += 1
            pixmap = thumbnail_manager.request_thumbnail(self.current_request_id, file_id, thumb_path, 40, 40)
            
        painter.setBrush(QBrush(QColor(tokens["bg_surface_2"])))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(thumb_rect, 6, 6)
        
        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(
                thumb_rect.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
            clip_path = QPainterPath()
            clip_path.addRoundedRect(QRectF(thumb_rect), 6, 6)
            painter.setClipPath(clip_path)
            
            x_offset = (scaled.width() - thumb_rect.width()) // 2
            y_offset = (scaled.height() - thumb_rect.height()) // 2
            painter.drawPixmap(thumb_rect.topLeft(), scaled, QRect(x_offset, y_offset, thumb_rect.width(), thumb_rect.height()))
            painter.setClipping(False)
        else:
            icon_name = _get_icon_name_for_type(mtype)
            icon_pixmap = get_pixmap(icon_name, color=tokens["text_secondary"], size=20)
            if not icon_pixmap.isNull():
                ix = thumb_rect.center().x() - icon_pixmap.width() // 2
                iy = thumb_rect.center().y() - icon_pixmap.height() // 2
                painter.drawPixmap(ix, iy, icon_pixmap)

        # Date (right side)
        date_str = str(index.data(DateRole) or "")
        date_font = get_caption_font(date_str)
        fm_date = QFontMetrics(date_font)
        date_width = fm_date.horizontalAdvance(date_str) + 16
        
        date_rect = QRect(rect.right() - date_width, rect.top(), date_width, rect.height())
        painter.setFont(date_font)
        painter.setPen(QColor(tokens["text_tertiary"]))
        painter.drawText(date_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, date_str)

        # Filename
        filename = index.data(FilenameRole) or "Unknown File"
        name_font = get_font_for_text(filename, pixel_size=13, weight=500)
        fm_name = QFontMetrics(name_font)
        
        # Size
        file_size = index.data(SizeRole) or 0
        size_str = format_bytes(file_size)
        size_font = get_caption_font(size_str)
        
        text_left = thumb_rect.right() + 12
        available_width = rect.right() - date_width - text_left - 8
        
        name_rect = QRect(text_left, rect.top() + 6, available_width, 18)
        elided_name = fm_name.elidedText(filename, Qt.TextElideMode.ElideRight, available_width)
        
        painter.setFont(name_font)
        painter.setPen(QColor(tokens["text_primary"]))
        painter.drawText(name_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided_name)
        
        size_rect = QRect(text_left, rect.top() + 24, available_width, 16)
        painter.setFont(size_font)
        painter.setPen(QColor(tokens["text_tertiary"]))
        painter.drawText(size_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, size_str)

        painter.restore()
