"""Download manager window and task item row for PySide6."""

from pathlib import Path
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core.config import settings
from ..services.downloader import DownloadManager, DownloadStatus, DownloadTask
from ..services.preview import PreviewService

STATUS_COLORS = {
    DownloadStatus.QUEUED: "#fee75c",
    DownloadStatus.DOWNLOADING: "#5865f2",
    DownloadStatus.COMPLETED: "#57f287",
    DownloadStatus.CANCELLED: "#949ba4",
    DownloadStatus.FAILED: "#ed4245",
}


class DownloadRowWidget(QWidget):
    """Widget rendered for an individual download task."""

    def __init__(self, task: DownloadTask, manager: DownloadManager, parent=None):
        super().__init__(parent)
        self.task = task
        self.manager = manager
        self._init_ui()
        self.update_task(task)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # Top Row: Filename, Status Badge, and Action Buttons
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        self.name_label = QLabel(self.task.filename)
        name_font = QFont()
        name_font.setBold(True)
        name_font.setPointSize(11)
        self.name_label.setFont(name_font)
        self.name_label.setStyleSheet("color: #ffffff;")
        top_row.addWidget(self.name_label, stretch=1)

        self.status_badge = QLabel(self.task.status.value)
        self.status_badge.setStyleSheet(
            "background-color: #5865f2; color: #ffffff; border-radius: 4px; font-weight: bold; font-size: 10px; padding: 2px 6px;"
        )
        top_row.addWidget(self.status_badge)

        # Action Buttons
        self.btn_cancel = QPushButton("✕ Cancel")
        self.btn_cancel.setStyleSheet("padding: 2px 8px; font-size: 11px;")
        self.btn_cancel.clicked.connect(self._on_cancel)
        top_row.addWidget(self.btn_cancel)

        self.btn_retry = QPushButton("🔄 Retry")
        self.btn_retry.setStyleSheet("padding: 2px 8px; font-size: 11px;")
        self.btn_retry.clicked.connect(self._on_retry)
        self.btn_retry.setVisible(False)
        top_row.addWidget(self.btn_retry)

        self.btn_open = QPushButton("↗ Open")
        self.btn_open.setStyleSheet("padding: 2px 8px; font-size: 11px;")
        self.btn_open.clicked.connect(self._on_open)
        self.btn_open.setVisible(False)
        top_row.addWidget(self.btn_open)

        layout.addLayout(top_row)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)

        # Bottom Details: Downloaded / Total Size • Speed • Errors
        bottom_row = QHBoxLayout()
        self.details_label = QLabel("Waiting...")
        self.details_label.setStyleSheet("color: #949ba4; font-size: 11px;")
        bottom_row.addWidget(self.details_label)

        bottom_row.addStretch()
        layout.addLayout(bottom_row)

    def update_task(self, task: DownloadTask):
        """Refresh widget with latest task progress and state."""
        self.task = task
        self.progress_bar.setValue(int(task.progress_percent))

        color = STATUS_COLORS.get(task.status, "#5865f2")
        self.status_badge.setText(f" {task.status.value} ")
        self.status_badge.setStyleSheet(
            f"background-color: {color}; color: #ffffff; border-radius: 4px; font-weight: bold; font-size: 10px; padding: 2px 6px;"
        )

        if task.status == DownloadStatus.DOWNLOADING:
            self.details_label.setText(
                f"{task.human_downloaded} of {task.human_total} • {task.human_speed} ({task.progress_percent:.1f}%)"
            )
            self.btn_cancel.setVisible(True)
            self.btn_retry.setVisible(False)
            self.btn_open.setVisible(False)

        elif task.status == DownloadStatus.COMPLETED:
            self.details_label.setText(f"Completed • {task.human_total} saved to {task.destination_path.name}")
            self.details_label.setStyleSheet("color: #57f287; font-size: 11px;")
            self.btn_cancel.setVisible(False)
            self.btn_retry.setVisible(False)
            self.btn_open.setVisible(True)

        elif task.status == DownloadStatus.FAILED:
            err = task.error_message or "Unknown error"
            self.details_label.setText(f"Failed: {err}")
            self.details_label.setStyleSheet("color: #ed4245; font-size: 11px;")
            self.btn_cancel.setVisible(False)
            self.btn_retry.setVisible(True)
            self.btn_open.setVisible(False)

        elif task.status == DownloadStatus.CANCELLED:
            self.details_label.setText("Cancelled by user.")
            self.details_label.setStyleSheet("color: #949ba4; font-size: 11px;")
            self.btn_cancel.setVisible(False)
            self.btn_retry.setVisible(True)
            self.btn_open.setVisible(False)

    def _on_cancel(self):
        self.manager.cancel_download(self.task.task_id)

    def _on_retry(self):
        self.manager.retry_download(self.task.task_id)

    def _on_open(self):
        PreviewService.open_in_system_viewer(str(self.task.destination_path))


class DownloadManagerDialog(QDialog):
    """Modern modal / floating dialog to inspect all downloads and their progress."""

    def __init__(self, manager: DownloadManager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.setWindowTitle("Telegram Download Manager")
        self.resize(680, 480)
        self.setMinimumSize(540, 360)
        self._item_widgets = {}

        self._init_ui()
        self._connect_signals()
        self._populate_existing()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # Header Bar: Title + Open Folder Button
        header_row = QHBoxLayout()
        title_label = QLabel("⬇ Downloads")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        header_row.addWidget(title_label)

        header_row.addStretch()

        btn_open_folder = QPushButton("📁 Open Downloads Folder")
        btn_open_folder.clicked.connect(self._open_downloads_folder)
        header_row.addWidget(btn_open_folder)

        layout.addLayout(header_row)

        # Downloads List Widget
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(
            """
            QListWidget {
                background-color: #1e1f22;
                border: 1px solid #2b2d31;
                border-radius: 8px;
            }
            QListWidget::item {
                border-bottom: 1px solid #2b2d31;
            }
            """
        )
        layout.addWidget(self.list_widget)

        # Footer
        footer = QHBoxLayout()
        self.status_summary = QLabel("0 active downloads")
        self.status_summary.setStyleSheet("color: #949ba4; font-size: 12px;")
        footer.addWidget(self.status_summary)

        footer.addStretch()

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        footer.addWidget(btn_close)

        layout.addLayout(footer)

    def _connect_signals(self):
        self.manager.task_added.connect(self._on_task_added)
        self.manager.task_updated.connect(self._on_task_updated)

    def _populate_existing(self):
        for task in self.manager.get_all_tasks():
            self._on_task_added(task)

    def _on_task_added(self, task: DownloadTask):
        if task.task_id in self._item_widgets:
            return

        item = QListWidgetItem(self.list_widget)
        item.setSizeHint(item.sizeHint().expandedTo(QWidget().sizeHint()))
        item.setSizeHint(item.sizeHint().setHeight(75) or item.sizeHint())

        row_widget = DownloadRowWidget(task, self.manager)
        self.list_widget.setItemWidget(item, row_widget)
        self._item_widgets[task.task_id] = row_widget
        self._update_summary()

    def _on_task_updated(self, task: DownloadTask):
        widget = self._item_widgets.get(task.task_id)
        if widget:
            widget.update_task(task)
        self._update_summary()

    def _update_summary(self):
        tasks = self.manager.get_all_tasks()
        active = sum(1 for t in tasks if t.status == DownloadStatus.DOWNLOADING)
        completed = sum(1 for t in tasks if t.status == DownloadStatus.COMPLETED)
        self.status_summary.setText(f"{active} downloading • {completed} completed • {len(tasks)} total")

    def _open_downloads_folder(self):
        settings.download_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(settings.download_dir)))
