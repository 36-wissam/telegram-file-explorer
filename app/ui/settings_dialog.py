"""Settings and preferences modal dialog conforming to design system specifications."""

from pathlib import Path
from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..core.config import settings
from ..core.logger import get_logger
from ..database.repository import DatabaseRepository
from ..telegram.auth import TelegramAuthService

logger = get_logger("ui.settings_dialog")


class SettingsDialog(QDialog):
    """Clean settings dialog with tabbed configuration sections."""

    theme_changed = Signal(str)
    logout_requested = Signal()

    def __init__(
        self,
        auth_service: Optional[TelegramAuthService] = None,
        repo: Optional[DatabaseRepository] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.auth_service = auth_service
        self.repo = repo or DatabaseRepository()
        self.setWindowTitle("Settings")
        self.resize(580, 480)
        self.setMinimumSize(500, 400)
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet(
            """
            QDialog {
                background-color: #111113;
                color: #F4F4F5;
            }
            QTabWidget::pane {
                border: 1px solid #27272A;
                background-color: #18181B;
                border-radius: 8px;
                padding: 16px;
            }
            QTabBar::tab {
                background-color: #18181B;
                color: #A1A1AA;
                border: 1px solid #27272A;
                border-bottom: none;
                padding: 8px 16px;
                margin-right: 4px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: 500;
                font-size: 13px;
            }
            QTabBar::tab:selected {
                background-color: #27272A;
                color: #F4F4F5;
                font-weight: 600;
            }
            QTabBar::tab:hover:!selected {
                background-color: #1C1C1F;
                color: #E4E4E7;
            }
            QLabel {
                color: #F4F4F5;
                font-size: 13px;
            }
            QLineEdit {
                background-color: #111113;
                border: 1px solid #27272A;
                border-radius: 6px;
                color: #F4F4F5;
                padding: 6px 12px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #229ED9;
            }
            QComboBox {
                background-color: #111113;
                border: 1px solid #27272A;
                border-radius: 6px;
                color: #F4F4F5;
                padding: 6px 12px;
                font-size: 13px;
            }
            QPushButton {
                background-color: #27272A;
                border: 1px solid #3F3F46;
                border-radius: 6px;
                color: #F4F4F5;
                padding: 6px 14px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #3F3F46;
                color: #FFFFFF;
            }
            QPushButton#primaryButton {
                background-color: #229ED9;
                border: none;
                color: #FFFFFF;
                font-weight: 600;
            }
            QPushButton#primaryButton:hover {
                background-color: #3AAFE8;
            }
            QPushButton#dangerButton {
                background-color: #7F1D1D;
                border: 1px solid #991B1B;
                color: #FECACA;
                font-weight: 500;
            }
            QPushButton#dangerButton:hover {
                background-color: #991B1B;
                color: #FFFFFF;
            }
            QGroupBox {
                border: 1px solid #27272A;
                border-radius: 6px;
                margin-top: 14px;
                padding-top: 14px;
                font-weight: 600;
                color: #A1A1AA;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 6px;
            }
            """
        )

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        # Tab Widget
        self.tabs = QTabWidget(self)
        self.tabs.addTab(self._create_account_tab(), "Account")
        self.tabs.addTab(self._create_appearance_tab(), "Appearance")
        self.tabs.addTab(self._create_storage_tab(), "Storage")
        self.tabs.addTab(self._create_database_tab(), "Database")
        self.tabs.addTab(self._create_about_tab(), "About")
        main_layout.addWidget(self.tabs)

        # Bottom Action Row
        bottom_row = QHBoxLayout()
        bottom_row.addStretch()

        btn_close = QPushButton("Done", self)
        btn_close.setObjectName("primaryButton")
        btn_close.setFixedWidth(100)
        btn_close.clicked.connect(self.accept)
        bottom_row.addWidget(btn_close)

        main_layout.addLayout(bottom_row)

    def _create_account_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(14)

        # Account Info Card
        group_user = QGroupBox("Active Telegram Session", tab)
        g_layout = QGridLayout(group_user)
        g_layout.setSpacing(10)

        user_name = "Not connected"
        user_phone = "-"
        user_id = "-"
        if self.auth_service and self.auth_service.current_user:
            u = self.auth_service.current_user
            user_name = f"{u.get('first_name', '')} {u.get('last_name', '')}".strip()
            if u.get('username'):
                user_name += f" (@{u['username']})"
            user_phone = u.get('phone', '-')
            user_id = str(u.get('id', '-'))

        g_layout.addWidget(QLabel("User:"), 0, 0)
        lbl_user = QLabel(user_name)
        lbl_user.setStyleSheet("color: #229ED9; font-weight: 600;")
        g_layout.addWidget(lbl_user, 0, 1)

        g_layout.addWidget(QLabel("Phone:"), 1, 0)
        g_layout.addWidget(QLabel(user_phone), 1, 1)

        g_layout.addWidget(QLabel("User ID:"), 2, 0)
        g_layout.addWidget(QLabel(user_id), 2, 1)

        layout.addWidget(group_user)

        # Telegram API Details
        group_api = QGroupBox("Telegram MTProto API Credentials", tab)
        api_layout = QGridLayout(group_api)
        api_layout.setSpacing(10)

        api_layout.addWidget(QLabel("API ID:"), 0, 0)
        api_id_val = str(settings.api_id) if settings.api_id else "Not set"
        api_layout.addWidget(QLabel(api_id_val), 0, 1)

        api_layout.addWidget(QLabel("API Hash:"), 1, 0)
        api_hash_val = (settings.api_hash[:4] + "..." + settings.api_hash[-4:]) if settings.api_hash else "Not set"
        api_layout.addWidget(QLabel(api_hash_val), 1, 1)

        layout.addWidget(group_api)

        # Logout Button
        logout_row = QHBoxLayout()
        logout_row.addStretch()

        btn_sign_out = QPushButton("Sign Out", tab)
        btn_sign_out.setObjectName("dangerButton")
        btn_sign_out.clicked.connect(self._on_logout_click)
        logout_row.addWidget(btn_sign_out)

        layout.addLayout(logout_row)
        layout.addStretch()
        return tab

    def _create_appearance_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(14)

        group_theme = QGroupBox("Interface Theme", tab)
        t_layout = QGridLayout(group_theme)
        t_layout.setSpacing(12)

        t_layout.addWidget(QLabel("Theme Mode:"), 0, 0)
        self.combo_theme = QComboBox(group_theme)
        self.combo_theme.addItems(["Dark (Default)", "Light", "System Synchronized"])
        t_layout.addWidget(self.combo_theme, 0, 1)

        layout.addWidget(group_theme)

        group_grid = QGroupBox("Media Viewport", tab)
        g_layout = QGridLayout(group_grid)
        g_layout.setSpacing(12)

        g_layout.addWidget(QLabel("Thumbnail Size:"), 0, 0)
        self.combo_thumb_size = QComboBox(group_grid)
        self.combo_thumb_size.addItems(["Standard (200px)", "Compact (160px)", "Large (240px)"])
        g_layout.addWidget(self.combo_thumb_size, 0, 1)

        layout.addWidget(group_grid)
        layout.addStretch()
        return tab

    def _create_storage_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(14)

        group_dl = QGroupBox("Downloads Directory", tab)
        d_layout = QVBoxLayout(group_dl)
        d_layout.setSpacing(10)

        path_row = QHBoxLayout()
        self.edit_dl_path = QLineEdit(str(settings.download_dir), tab)
        self.edit_dl_path.setReadOnly(True)
        path_row.addWidget(self.edit_dl_path)

        btn_browse = QPushButton("Browse...", tab)
        btn_browse.clicked.connect(self._on_browse_dl_path)
        path_row.addWidget(btn_browse)
        d_layout.addLayout(path_row)

        btn_open_folder = QPushButton("Open Folder in Explorer", tab)
        btn_open_folder.clicked.connect(self._on_open_dl_folder)
        d_layout.addWidget(btn_open_folder, alignment=Qt.AlignLeft)

        layout.addWidget(group_dl)

        group_cache = QGroupBox("Thumbnails Cache", tab)
        c_layout = QHBoxLayout(group_cache)
        c_layout.setSpacing(10)

        cache_size_str = self._get_cache_size_str()
        lbl_cache = QLabel(f"Cached Thumbnails: {cache_size_str}")
        c_layout.addWidget(lbl_cache)
        c_layout.addStretch()

        btn_clear_cache = QPushButton("Clear Cache", tab)
        btn_clear_cache.clicked.connect(lambda: self._on_clear_cache(lbl_cache))
        c_layout.addWidget(btn_clear_cache)

        layout.addWidget(group_cache)
        layout.addStretch()
        return tab

    def _create_database_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(14)

        group_db = QGroupBox("Local Metadata Database", tab)
        db_layout = QGridLayout(group_db)
        db_layout.setSpacing(12)

        file_count = 0
        chat_count = 0
        try:
            file_count = self.repo.get_files_count()
            chat_count = len(self.repo.get_chats())
        except Exception:
            pass

        db_layout.addWidget(QLabel("Indexed Files:"), 0, 0)
        db_layout.addWidget(QLabel(f"{file_count:,} records"), 0, 1)

        db_layout.addWidget(QLabel("Discovered Chats:"), 1, 0)
        db_layout.addWidget(QLabel(f"{chat_count:,} chats"), 1, 1)

        db_layout.addWidget(QLabel("Database Location:"), 2, 0)
        db_path_lbl = QLabel(str(self.repo.db_path))
        db_path_lbl.setStyleSheet("color: #71717A; font-size: 11px;")
        db_layout.addWidget(db_path_lbl, 2, 1)

        layout.addWidget(group_db)

        # Danger zone
        btn_clear_db = QPushButton("Clear Indexed Metadata", tab)
        btn_clear_db.setObjectName("dangerButton")
        btn_clear_db.clicked.connect(self._on_clear_database)
        layout.addWidget(btn_clear_db, alignment=Qt.AlignLeft)

        layout.addStretch()
        return tab

    def _create_about_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(14)

        title = QLabel(f"{settings.app_name} v{settings.app_version}")
        title_font = QFont()
        title_font.setPointSize(15)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: #229ED9;")
        layout.addWidget(title)

        subtitle = QLabel("Desktop Telegram MTProto File Manager & Explorer")
        subtitle.setStyleSheet("color: #A1A1AA; font-size: 13px;")
        layout.addWidget(subtitle)

        # Runtime Info Box
        import sys
        import PySide6
        import telethon

        info_box = QFrame(tab)
        info_box.setStyleSheet(
            "background-color: #111113; border: 1px solid #27272A; border-radius: 6px; padding: 12px;"
        )
        ib_layout = QGridLayout(info_box)
        ib_layout.setSpacing(8)

        ib_layout.addWidget(QLabel("Python Runtime:"), 0, 0)
        ib_layout.addWidget(QLabel(sys.version.split()[0]), 0, 1)

        ib_layout.addWidget(QLabel("Qt / PySide6:"), 1, 0)
        ib_layout.addWidget(QLabel(PySide6.__version__), 1, 1)

        ib_layout.addWidget(QLabel("Telethon Engine:"), 2, 0)
        ib_layout.addWidget(QLabel(telethon.__version__), 2, 1)

        ib_layout.addWidget(QLabel("Search Engine:"), 3, 0)
        ib_layout.addWidget(QLabel("SQLite FTS5 Full-Text Search"), 3, 1)

        layout.addWidget(info_box)

        # Privacy Notice
        privacy = QLabel(
            "100% Local-First Architecture: All session data, SQLite metadata indices, "
            "and downloaded files reside exclusively in your local application directory (data/). "
            "No telemetry or file data is ever transmitted to third-party servers."
        )
        privacy.setStyleSheet("color: #71717A; font-size: 11px; line-height: 1.4;")
        privacy.setWordWrap(True)
        layout.addWidget(privacy)

        layout.addStretch()
        return tab

    def _on_browse_dl_path(self):
        chosen = QFileDialog.getExistingDirectory(
            self,
            "Select Download Directory",
            str(settings.download_dir),
        )
        if chosen:
            settings.download_dir = Path(chosen)
            self.edit_dl_path.setText(chosen)

    def _on_open_dl_folder(self):
        from ..services.preview import PreviewService
        PreviewService.open_in_system_viewer(str(settings.download_dir))

    def _get_cache_size_str(self) -> str:
        cache_dir = settings.thumbnail_dir
        if not cache_dir.exists():
            return "0 KB"
        total = sum(f.stat().st_size for f in cache_dir.glob("*") if f.is_file())
        mb = total / (1024 * 1024)
        if mb >= 1.0:
            return f"{mb:.1f} MB"
        return f"{total / 1024:.1f} KB"

    def _on_clear_cache(self, label: QLabel):
        cache_dir = settings.thumbnail_dir
        if cache_dir.exists():
            for f in cache_dir.glob("*"):
                if f.is_file():
                    try:
                        f.unlink()
                    except Exception:
                        pass
        label.setText("Cached Thumbnails: 0 KB")
        QMessageBox.information(self, "Cache Cleared", "Thumbnail cache has been cleared.")

    def _on_clear_database(self):
        confirm = QMessageBox.question(
            self,
            "Clear Database",
            "Are you sure you want to clear all indexed metadata?\n\nThis will remove indexed records from SQLite. Your local downloaded files will not be deleted.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            try:
                with self.repo._get_conn() as conn:
                    conn.execute("DELETE FROM files")
                    conn.execute("DELETE FROM chats")
                    conn.execute("DELETE FROM sync_state")
                    conn.commit()
                QMessageBox.information(self, "Database Cleared", "Local media metadata has been cleared.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to clear database: {e}")

    def _on_logout_click(self):
        self.accept()
        self.logout_requested.emit()
