"""Main application window for Telegram File Explorer."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from ..core.config import settings
from ..core.logger import get_logger

logger = get_logger("ui.main_window")


class MainWindow(QMainWindow):
    """Main desktop application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{settings.app_name} v{settings.app_version}")
        self.setMinimumSize(850, 580)
        self.resize(1080, 720)

        self._init_menu_bar()
        self._init_ui()
        self._init_status_bar()

        logger.info("MainWindow initialized successfully.")

    def _init_menu_bar(self):
        """Build top menu bar."""
        menu_bar = self.menuBar()

        # File Menu
        file_menu = menu_bar.addMenu("&File")
        exit_action = QAction("&Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Help Menu
        help_menu = menu_bar.addMenu("&Help")
        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _init_ui(self):
        """Construct central widget layout."""
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(32, 32, 32, 32)
        main_layout.setSpacing(20)

        # Welcome Card Container
        card = QFrame(self)
        card.setStyleSheet(
            """
            QFrame {
                background-color: #1e1f22;
                border: 1px solid #2b2d31;
                border-radius: 12px;
                padding: 24px;
            }
            """
        )
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(14)
        card_layout.setAlignment(Qt.AlignCenter)

        # App Icon / Title
        title_label = QLabel(f"📂 {settings.app_name}")
        title_font = QFont()
        title_font.setPointSize(22)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color: #ffffff;")
        card_layout.addWidget(title_label)

        # Subtitle / Tagline
        subtitle_label = QLabel(
            "Browse, index, search, preview, and download files from your Telegram account."
        )
        subtitle_label.setAlignment(Qt.AlignCenter)
        subtitle_label.setStyleSheet("color: #949ba4; font-size: 14px;")
        card_layout.addWidget(subtitle_label)

        # Status badge container
        status_box = QFrame(self)
        status_box.setStyleSheet(
            """
            QFrame {
                background-color: #2b2d31;
                border-radius: 8px;
                padding: 12px;
                max-width: 520px;
            }
            """
        )
        status_box_layout = QVBoxLayout(status_box)
        status_box_layout.setSpacing(6)

        config_status = "Configured" if settings.is_telegram_configured else "Not Configured (Requires API credentials)"
        config_color = "#57f287" if settings.is_telegram_configured else "#fee75c"

        config_label = QLabel(
            f"<b>Telegram API Status:</b> <span style='color: {config_color};'>{config_status}</span>"
        )
        config_label.setStyleSheet("font-size: 13px;")
        status_box_layout.addWidget(config_label)

        stage_label = QLabel(
            "<b>Current Stage:</b> <span style='color: #5865f2;'>Stage 1 — Project Foundation</span>"
        )
        stage_label.setStyleSheet("font-size: 13px;")
        status_box_layout.addWidget(stage_label)

        card_layout.addWidget(status_box, alignment=Qt.AlignCenter)

        main_layout.addStretch()
        main_layout.addWidget(card)
        main_layout.addStretch()

    def _init_status_bar(self):
        """Set up bottom status bar."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready. Project foundation initialized.")

    def _show_about(self):
        """Show about message."""
        self.status_bar.showMessage(
            f"{settings.app_name} v{settings.app_version} - MTProto Client File Explorer",
            5000,
        )
