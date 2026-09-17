import os
import sys
from PySide6.QtCore import QObject, Signal, QSettings
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

DARK_TOKENS = {
    "bg_base": "#0B0D10",
    "bg_surface": "#14171C",
    "bg_surface_2": "#1B1F26",
    "bg_hover": "#232830",
    "border": "#2A2F38",
    "text_primary": "#ECEDEE",
    "text_secondary": "#9BA1AC",
    "text_tertiary": "#5F6672",
    "accent": "#5C8DFF",
    "accent_hover": "#7AA2FF",
    "accent_muted": "rgba(92,141,255,0.12)",
    "success": "#3DDC84",
    "warning": "#F5A623",
    "danger": "#F1554C",
}

LIGHT_TOKENS = {
    "bg_base": "#F7F8FA",
    "bg_surface": "#FFFFFF",
    "bg_surface_2": "#F0F1F4",
    "bg_hover": "#E9EBEF",
    "border": "#E1E3E8",
    "text_primary": "#1A1D21",
    "text_secondary": "#5B616B",
    "text_tertiary": "#8A909B",
    "accent": "#3D6FE0",
    "accent_hover": "#2F5BC4",
    "accent_muted": "rgba(61,111,224,0.10)",
    "success": "#1FA971",
    "warning": "#C97F0E",
    "danger": "#D6423A",
}


class ThemeManager(QObject):
    theme_changed = Signal(dict)

    def __init__(self):
        super().__init__()
        self.settings = QSettings("TelegramFileExplorer", "Appearance")
        self._current_theme_mode = self.settings.value("theme_mode", "system", type=str)

    @property
    def current_theme_mode(self) -> str:
        return self._current_theme_mode

    @current_theme_mode.setter
    def current_theme_mode(self, value: str):
        self.set_theme(value)

    def is_system_dark(self) -> bool:
        """Attempt to detect if the OS is in dark mode."""
        if sys.platform == "win32":
            try:
                import winreg
                registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
                key = winreg.OpenKey(registry, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                return value == 0
            except Exception:
                pass
        
        # Fallback to QGuiApplication palette if possible
        app = QGuiApplication.instance()
        if app:
            palette = app.palette()
            window_color = palette.color(palette.ColorRole.Window)
            return window_color.lightness() < 128

        return True  # Fallback to dark mode

    def get_tokens(self, mode: str = "dark") -> dict:
        """Return token dictionary for specified mode."""
        if mode == "light":
            return LIGHT_TOKENS
        elif mode == "dark":
            return DARK_TOKENS
        return self.get_active_tokens()

    def get_active_tokens(self) -> dict:
        mode = self._current_theme_mode
        if mode == "system":
            if self.is_system_dark():
                return DARK_TOKENS
            else:
                return LIGHT_TOKENS
        elif mode == "light":
            return LIGHT_TOKENS
        return DARK_TOKENS

    def set_theme(self, mode: str):
        if mode not in ["dark", "light", "system"]:
            mode = "system"
            
        self._current_theme_mode = mode
        self.settings.setValue("theme_mode", mode)
        
        tokens = self.get_active_tokens()
        qss = self.generate_qss(tokens)
        
        app = QApplication.instance()
        if app:
            app.setStyleSheet(qss)
            
        self.theme_changed.emit(tokens)

    def toggle_theme(self):
        """1-click toggle between dark and light themes."""
        tokens = self.get_active_tokens()
        if tokens == DARK_TOKENS:
            self.set_theme("light")
        else:
            self.set_theme("dark")


    def generate_qss(self, tokens: dict) -> str:
        # Build complete, beautiful, clean QSS adhering strictly to Obsidian design system rules
        qss = f"""
        * {{
            font-family: "Inter", "Cairo", "IBM Plex Sans Arabic", "Segoe UI", -apple-system, BlinkMacSystemFont, Arial, sans-serif;
            color: {tokens["text_primary"]};
        }}

        /* Main Window */
        QMainWindow {{
            background-color: {tokens["bg_base"]};
        }}
        
        QWidget#MainWindow {{
            background-color: {tokens["bg_base"]};
            border: 1px solid {tokens["border"]};
        }}

        /* Scrollbars */
        QScrollBar:vertical {{
            border: none;
            background: transparent;
            width: 6px;
            margin: 0px;
        }}
        QScrollBar::handle:vertical {{
            background: {tokens["bg_surface_2"]};
            border-radius: 3px;
            min-height: 20px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {tokens["accent_muted"]};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
            background: none;
        }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: none;
        }}

        QScrollBar:horizontal {{
            border: none;
            background: transparent;
            height: 6px;
            margin: 0px;
        }}
        QScrollBar::handle:horizontal {{
            background: {tokens["bg_surface_2"]};
            border-radius: 3px;
            min-width: 20px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: {tokens["accent_muted"]};
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
            background: none;
        }}
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
            background: none;
        }}

        /* Buttons */
        QPushButton {{
            font-size: 13px;
            font-weight: 400;
            border-radius: 6px;
            padding: 8px 16px;
            height: 36px;
        }}
        
        QPushButton[type="primary"], QPushButton#primaryButton {{
            background-color: {tokens["accent"]};
            color: #FFFFFF;
            border: none;
        }}
        QPushButton[type="primary"]:hover, QPushButton#primaryButton:hover {{
            background-color: {tokens["accent_hover"]};
        }}

        QPushButton[type="secondary"], QPushButton#secondaryButton {{
            background-color: transparent;
            color: {tokens["text_primary"]};
            border: 1px solid {tokens["border"]};
        }}
        QPushButton[type="secondary"]:hover, QPushButton#secondaryButton:hover {{
            background-color: {tokens["bg_hover"]};
        }}

        /* Segmented pill controls */
        QRadioButton[type="pill"] {{
            background-color: transparent;
            color: {tokens["text_secondary"]};
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 13px;
            border: none;
        }}
        QRadioButton[type="pill"]::indicator {{
            width: 0px;
            height: 0px;
        }}
        QRadioButton[type="pill"]:checked {{
            background-color: {tokens["accent_muted"]};
            color: {tokens["accent"]};
        }}
        QRadioButton[type="pill"]:hover:!checked {{
            background-color: {tokens["bg_hover"]};
            color: {tokens["text_primary"]};
        }}

        /* Inputs */
        QLineEdit, QTextEdit, QPlainTextEdit {{
            background-color: {tokens["bg_surface"]};
            border: 1px solid {tokens["border"]};
            border-radius: 6px;
            padding: 8px;
            font-size: 13px;
            color: {tokens["text_primary"]};
            selection-background-color: {tokens["accent_muted"]};
            selection-color: {tokens["text_primary"]};
        }}
        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
            border: 1px solid {tokens["accent"]};
        }}

        /* Panels/Dialogs */
        QDialog, QMenu {{
            background-color: {tokens["bg_surface"]};
            border: 1px solid {tokens["border"]};
            border-radius: 14px;
        }}

        /* Cards/Rows */
        QFrame[type="card"], QListView, QTreeView, QTableView {{
            background-color: {tokens["bg_surface"]};
            border: 1px solid {tokens["border"]};
            border-radius: 10px;
        }}
        
        QListView::item, QTreeView::item, QTableView::item {{
            border-radius: 6px;
        }}
        QListView::item:hover, QTreeView::item:hover, QTableView::item:hover {{
            background-color: {tokens["bg_hover"]};
        }}
        QListView::item:selected, QTreeView::item:selected, QTableView::item:selected {{
            background-color: {tokens["accent_muted"]};
            color: {tokens["accent"]};
        }}
        
        /* Headers / Typography Helpers */
        QLabel[type="title"] {{
            font-size: 18px;
            font-weight: 600;
        }}
        QLabel[type="section_header"] {{
            font-size: 14px;
            font-weight: 600;
        }}
        QLabel[type="body"] {{
            font-size: 13px;
            font-weight: 400;
        }}
        QLabel[type="secondary"] {{
            font-size: 12px;
            font-weight: 400;
            color: {tokens["text_secondary"]};
        }}
        QLabel[type="caption"] {{
            font-size: 11px;
            font-weight: 400;
            color: {tokens["text_tertiary"]};
        }}
        """
        return qss

# Singleton instance
theme_manager = ThemeManager()
