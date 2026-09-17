import os
from PySide6.QtCore import QObject, QPoint, QRect, QRectF, QSize, Qt, Signal, QEvent
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPixmap, QPen, QMouseEvent
from PySide6.QtWidgets import QStyledItemDelegate, QStyle, QStyleOptionViewItem, QToolTip, QApplication

from .theme_manager import theme_manager
from .icons import get_pixmap, get_icon
from ..services.image_loader import thumbnail_manager
from .media_card import format_bytes
from .media_model import (
    FileIdRole, FilenameRole, SizeRole, DateRole, MediaTypeRole, 
    ThumbnailPathRole, FileModelRole, HasThumbnailRole, CaptionRole, IsDownloadedRole
)

class MediaGridDelegate(QStyledItemDelegate):
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
        
        # Draw card background
        bg_color = QColor(tokens["bg_surface"])
        border_color = QColor(tokens["border"])
        border_width = 1

        if is_selected:
            bg_color = QColor(tokens["bg_surface_2"])
            border_color = QColor(tokens["accent"])
            border_width = 2
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
            # Scale pixmap to fit the area
            scaled_pixmap = pixmap.scaled(
                thumb_rect.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
            # Center the pixmap
            x_offset = (scaled_pixmap.width() - thumb_rect.width()) // 2
            y_offset = (scaled_pixmap.height() - thumb_rect.height()) // 2
            painter.drawPixmap(thumb_rect.topLeft(), scaled_pixmap, QRect(x_offset, y_offset, thumb_rect.width(), thumb_rect.height()))
        else:
            # Fallback icon
            painter.fillRect(thumb_rect, QColor(tokens["bg_surface_2"]))
            
            icon_name = "file_text"
            if mtype == "image":
                icon_name = "image"
            elif mtype == "video":
                icon_name = "video"
            elif mtype == "audio":
                icon_name = "audio"
            elif mtype == "archive":
                icon_name = "archive"
                
            icon_pixmap = get_pixmap(icon_name, 48, tokens["text_secondary"])
            if not icon_pixmap.isNull():
                ix = thumb_rect.center().x() - icon_pixmap.width() // 2
                iy = thumb_rect.center().y() - icon_pixmap.height() // 2
                painter.drawPixmap(ix, iy, icon_pixmap)

        # Remove clip for remaining elements
        painter.setClipping(False)

        # Draw text
        filename = index.data(FilenameRole) or "Unknown File"
        file_size = index.data(SizeRole) or 0
        
        text_rect = QRect(rect.left() + 8, thumb_rect.bottom() + 8, rect.width() - 16, 20)
        
        font = QFont("Inter", 10)
        painter.setFont(font)
        painter.setPen(QColor(tokens["text_primary"]))
        
        fm = QFontMetrics(font)
        elided_text = fm.elidedText(filename, Qt.TextElideMode.ElideRight, text_rect.width())
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, elided_text)
        
        size_rect = QRect(rect.left() + 8, text_rect.bottom() + 4, rect.width() - 16, 16)
        size_font = QFont("Inter", 9)
        painter.setFont(size_font)
        painter.setPen(QColor(tokens["text_tertiary"]))
        
        painter.drawText(size_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, format_bytes(file_size))

        # Hover actions
        if is_hovered:
            btn_size = 28
            margin = 8
            
            # Open button
            open_rect = QRect(rect.right() - btn_size - margin, rect.top() + margin, btn_size, btn_size)
            # Download button
            download_rect = QRect(open_rect.left() - btn_size - 4, rect.top() + margin, btn_size, btn_size)
            
            # Semi-transparent background
            btn_bg = QColor(0, 0, 0, 153) # rgba(0,0,0,0.6)
            painter.setBrush(QBrush(btn_bg))
            painter.setPen(Qt.PenStyle.NoPen)
            
            painter.drawRoundedRect(open_rect, 6, 6)
            painter.drawRoundedRect(download_rect, 6, 6)
            
            open_pixmap = get_pixmap("external_link", 16, "#FFFFFF")
            if not open_pixmap.isNull():
                painter.drawPixmap(open_rect.center().x() - 8, open_rect.center().y() - 8, open_pixmap)
                
            download_pixmap = get_pixmap("download", 16, "#FFFFFF")
            if not download_pixmap.isNull():
                painter.drawPixmap(download_rect.center().x() - 8, download_rect.center().y() - 8, download_pixmap)

        painter.restore()

    def get_button_rects(self, option: QStyleOptionViewItem):
        rect = option.rect.adjusted(4, 4, -4, -4)
        btn_size = 28
        margin = 8
        open_rect = QRect(rect.right() - btn_size - margin, rect.top() + margin, btn_size, btn_size)
        download_rect = QRect(open_rect.left() - btn_size - 4, rect.top() + margin, btn_size, btn_size)
        return download_rect, open_rect

    def editorEvent(self, event, model, option, index):
        if event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
            download_rect, open_rect = self.get_button_rects(option)
            file_model = index.data(FileModelRole)
            
            if download_rect.contains(event.position().toPoint()):
                self.download_clicked.emit(file_model)
                return True
            elif open_rect.contains(event.position().toPoint()):
                self.open_clicked.emit(file_model)
                return True
                
        return super().editorEvent(event, model, option, index)

class MediaListDelegate(QStyledItemDelegate):
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
            # Clip
            clip_path = QPainterPath()
            clip_path.addRoundedRect(QRectF(thumb_rect), 6, 6)
            painter.setClipPath(clip_path)
            
            x_offset = (scaled.width() - thumb_rect.width()) // 2
            y_offset = (scaled.height() - thumb_rect.height()) // 2
            painter.drawPixmap(thumb_rect.topLeft(), scaled, QRect(x_offset, y_offset, thumb_rect.width(), thumb_rect.height()))
            painter.setClipping(False)
        else:
            icon_name = "file_text"
            if mtype == "image":
                icon_name = "image"
            elif mtype == "video":
                icon_name = "video"
            elif mtype == "audio":
                icon_name = "audio"
            elif mtype == "archive":
                icon_name = "archive"
                
            icon_pixmap = get_pixmap(icon_name, 20, tokens["text_secondary"])
            if not icon_pixmap.isNull():
                ix = thumb_rect.center().x() - icon_pixmap.width() // 2
                iy = thumb_rect.center().y() - icon_pixmap.height() // 2
                painter.drawPixmap(ix, iy, icon_pixmap)

        # Date (right side)
        date_str = index.data(DateRole) or ""
        date_font = QFont("Inter", 11)
        fm_date = QFontMetrics(date_font)
        date_width = fm_date.horizontalAdvance(date_str) + 16
        
        date_rect = QRect(rect.right() - date_width, rect.top(), date_width, rect.height())
        painter.setFont(date_font)
        painter.setPen(QColor(tokens["text_tertiary"]))
        painter.drawText(date_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, date_str)

        # Filename
        filename = index.data(FilenameRole) or "Unknown File"
        name_font = QFont("Inter", 10)
        fm_name = QFontMetrics(name_font)
        
        # Size
        file_size = index.data(SizeRole) or 0
        size_str = format_bytes(file_size)
        size_font = QFont("Inter", 9)
        
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
