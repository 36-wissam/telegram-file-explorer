"""
Image loader service for asynchronous thumbnail generation and caching.
"""
from typing import Optional
from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import (
    QObject,
    QRunnable,
    QThreadPool,
    Signal,
    Slot,
    Qt
)
from PySide6.QtGui import QImage, QPixmap


class WorkerSignals(QObject):
    """Signals for the ImageDecodeWorker."""
    decoded = Signal(int, str, QImage)
    failed = Signal(int, str)


class ImageDecodeWorker(QRunnable):
    """
    Worker to decode and scale images off the GUI thread.
    Uses QImage as QPixmap cannot be used outside the main thread.
    """
    def __init__(self, request_id: int, file_id: str, image_path: str, target_width: int, target_height: int):
        super().__init__()
        self.request_id = request_id
        self.file_id = file_id
        self.image_path = image_path
        self.target_width = target_width
        self.target_height = target_height
        self.signals = WorkerSignals()

    def run(self):
        """Executes the image loading and scaling on a background thread."""
        try:
            # Check if file exists to avoid unnecessary Qt warnings
            path = Path(self.image_path)
            if not path.is_file():
                self.signals.failed.emit(self.request_id, self.file_id)
                return

            # Load image from path using QImage
            image = QImage(str(self.image_path))
            if image.isNull():
                self.signals.failed.emit(self.request_id, self.file_id)
                return
            
            # Scale image
            scaled_image = image.scaled(
                self.target_width,
                self.target_height,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
            
            self.signals.decoded.emit(self.request_id, self.file_id, scaled_image)
        except Exception as e:
            print(f"Error decoding image {self.image_path}: {e}")
            self.signals.failed.emit(self.request_id, self.file_id)


class AsyncThumbnailManager(QObject):
    """
    Manages thumbnail caching and asynchronous loading.
    """
    thumbnail_ready = Signal(int, str, QPixmap)

    def __init__(self, max_lru_size: int = 150, max_threads: int = 4, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.max_lru_size = max_lru_size
        self._cache: OrderedDict[str, QPixmap] = OrderedDict()
        
        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(max_threads)

    @property
    def _lru_cache(self) -> OrderedDict[str, QPixmap]:
        return self._cache
        
    def get_cached_pixmap(self, file_id: str) -> Optional[QPixmap]:
        """Gets a QPixmap from the LRU cache if it exists."""
        if file_id in self._cache:
            # Move to end to mark as recently used
            self._cache.move_to_end(file_id)
            return self._cache[file_id]
        return None
        
    def request_thumbnail(self, request_id: int, file_id: str, local_path: Optional[str], width: int = 160, height: int = 120) -> Optional[QPixmap]:
        """
        Requests a thumbnail. Returns it immediately if cached.
        Otherwise, queues a background worker to load and scale it.
        """
        cached = self.get_cached_pixmap(file_id)
        if cached is not None:
            return cached
            
        if not local_path:
            return None
            
        worker = ImageDecodeWorker(
            request_id=request_id,
            file_id=file_id,
            image_path=local_path,
            target_width=width,
            target_height=height
        )
        worker.signals.decoded.connect(self._on_worker_decoded)
        worker.signals.failed.connect(self._on_worker_failed)
        
        self.thread_pool.start(worker)
        return None

    @Slot(int, str, QImage)
    def _on_worker_decoded(self, request_id: int, file_id: str, image: QImage):
        """Slot called when a worker finishes decoding an image."""
        if image.isNull():
            return
            
        # Convert QImage to QPixmap on the GUI thread
        pixmap = QPixmap.fromImage(image)
        
        # Add to cache and manage LRU eviction
        self._cache[file_id] = pixmap
        self._cache.move_to_end(file_id)
        
        if len(self._cache) > self.max_lru_size:
            self._cache.popitem(last=False)
            
        # Emit signal to notify UI
        self.thumbnail_ready.emit(request_id, file_id, pixmap)
        
    @Slot(int, str)
    def _on_worker_failed(self, request_id: int, file_id: str):
        """Slot called when a worker fails to decode an image."""
        pass

    def clear_memory_cache(self):
        """Clears the thumbnail cache."""
        self._cache.clear()


# Export singleton
thumbnail_manager = AsyncThumbnailManager(max_lru_size=150, max_threads=4)
