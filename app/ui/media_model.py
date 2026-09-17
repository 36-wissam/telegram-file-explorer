import typing
from typing import List, Dict, Optional, Any

from PySide6.QtCore import Qt, QAbstractListModel, QModelIndex

# Custom Qt item roles
FileIdRole = Qt.UserRole + 1
FilenameRole = Qt.UserRole + 2
SizeRole = Qt.UserRole + 3
DateRole = Qt.UserRole + 4
MediaTypeRole = Qt.UserRole + 5
ThumbnailPathRole = Qt.UserRole + 6
FileModelRole = Qt.UserRole + 7
HasThumbnailRole = Qt.UserRole + 8
CaptionRole = Qt.UserRole + 9
IsDownloadedRole = Qt.UserRole + 10

class MediaListModel(QAbstractListModel):
    """
    Virtualized Model/View foundation for media files.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._files: List[Any] = []
        self._file_id_map: Dict[str, int] = {}

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._files)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._files)):
            return None
        
        file = self._files[index.row()]
        
        if role == Qt.DisplayRole:
            return getattr(file, "filename", None)
        elif role == FileIdRole:
            return getattr(file, "file_id", None)
        elif role == FilenameRole:
            return getattr(file, "filename", None)
        elif role == SizeRole:
            return getattr(file, "file_size", getattr(file, "size", 0))
        elif role == DateRole:
            return getattr(file, "message_date", getattr(file, "date", None))
        elif role == MediaTypeRole:
            return getattr(file, "media_type", None)
        elif role == ThumbnailPathRole:
            return getattr(file, "thumbnail_path", None)
        elif role == FileModelRole:
            return file
        elif role == HasThumbnailRole:
            return getattr(file, "has_thumbnail", False)
        elif role == CaptionRole:
            return getattr(file, "caption", None)
        elif role == IsDownloadedRole:
            return getattr(file, "is_downloaded", False)
            
        return None

    def set_files(self, files: List[Any]):
        """
        Set the entire list of files, resetting the model.
        """
        self.beginResetModel()
        self._files = list(files)
        self._file_id_map = {getattr(f, "file_id", str(i)): i for i, f in enumerate(self._files)}
        self.endResetModel()

    def append_files(self, files: List[Any]):
        """
        Append new files to the model without resetting it.
        Deduplicates against the existing file IDs.
        """
        new_files = []
        for file in files:
            file_id = getattr(file, "file_id", None)
            if file_id is not None and file_id not in self._file_id_map:
                new_files.append(file)
                
        if not new_files:
            return
            
        start_idx = len(self._files)
        end_idx = start_idx + len(new_files) - 1
        
        self.beginInsertRows(QModelIndex(), start_idx, end_idx)
        
        for file in new_files:
            file_id = getattr(file, "file_id", None)
            self._files.append(file)
            if file_id is not None:
                self._file_id_map[file_id] = len(self._files) - 1
                
        self.endInsertRows()

    def update_thumbnail_path(self, file_id: str, thumb_path: str):
        """
        Update the thumbnail path for a specific file.
        """
        if file_id in self._file_id_map:
            row = self._file_id_map[file_id]
            file = self._files[row]
            # Assigning to the object attribute assuming it's mutable
            setattr(file, "thumbnail_path", thumb_path)
            
            idx = self.index(row, 0)
            self.dataChanged.emit(idx, idx, [ThumbnailPathRole])

    def get_file(self, index: int) -> Optional[Any]:
        """
        Get the file at a specific index.
        """
        if 0 <= index < len(self._files):
            return self._files[index]
        return None

    def get_row_by_file_id(self, file_id: str) -> int:
        """Return row index for given file_id, or -1 if not found."""
        return self._file_id_map.get(file_id, -1)

    def get_all_files(self) -> List[Any]:
        """Return shallow copy of all files in model."""
        return list(self._files)

    def clear(self):
        """
        Clear all files from the model.
        """
        self.beginResetModel()
        self._files = []
        self._file_id_map = {}
        self.endResetModel()
