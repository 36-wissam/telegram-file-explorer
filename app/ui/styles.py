"""Modern SaaS theme and stylesheet matching the high-polish reference design."""

DARK_THEME = """
/* Global Application Reset */
QMainWindow, QDialog {
    background-color: #13141f;
    color: #f1f5f9;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    font-size: 13px;
}

QWidget {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    font-size: 13px;
}

/* Menu Bar */
QMenuBar {
    background-color: #13141f;
    color: #94a3b8;
    border-bottom: 1px solid #1e202e;
    padding: 2px 8px;
    font-size: 12px;
}

QMenuBar::item {
    background: transparent;
    padding: 4px 10px;
    border-radius: 4px;
}

QMenuBar::item:selected {
    background-color: #1e202e;
    color: #ffffff;
}

QMenu {
    background-color: #1a1c29;
    color: #f1f5f9;
    border: 1px solid #2b2e42;
    border-radius: 8px;
    padding: 6px;
}

QMenu::item {
    padding: 6px 20px;
    border-radius: 4px;
    font-size: 12px;
}

QMenu::item:selected {
    background-color: #2f66ee;
    color: #ffffff;
}

/* Status Bar */
QStatusBar {
    background-color: #13141f;
    color: #64748b;
    border-top: 1px solid #1e202e;
    font-size: 11px;
    padding: 3px 8px;
}

/* Standard Buttons */
QPushButton {
    background-color: #1e202e;
    color: #ffffff;
    border: 1px solid #2e3248;
    border-radius: 6px;
    padding: 7px 14px;
    font-size: 12px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #2a2d42;
    border-color: #3e4460;
}

QPushButton:pressed {
    background-color: #181926;
}

QPushButton:disabled {
    background-color: #181924;
    color: #475569;
    border-color: #1e202e;
}

/* Primary Action Button (Vibrant Royal Blue) */
QPushButton#primaryButton {
    background-color: #2f66ee;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 8px 18px;
    font-weight: 700;
    font-size: 13px;
}

QPushButton#primaryButton:hover {
    background-color: #2554c7;
}

QPushButton#primaryButton:pressed {
    background-color: #1e44a5;
}

/* Dark Pill Button */
QPushButton#darkPillButton {
    background-color: #1a1c29;
    color: #ffffff;
    border: 1px solid #2b2e42;
    border-radius: 6px;
    padding: 7px 14px;
    font-weight: 700;
    font-size: 12px;
}

QPushButton#darkPillButton:hover {
    background-color: #24273b;
    border-color: #3a3f5a;
}

/* Light / Pill Filter Buttons */
QPushButton#filterPillButton {
    background-color: #ffffff;
    color: #334155;
    border: 1px solid #cbd5e1;
    border-radius: 14px;
    padding: 4px 12px;
    font-size: 12px;
    font-weight: 500;
}

QPushButton#filterPillButton:hover {
    background-color: #f1f5f9;
    border-color: #94a3b8;
}

QPushButton#filterPillButton:checked {
    background-color: #eff6ff;
    color: #2f66ee;
    border-color: #2f66ee;
    font-weight: 600;
}

/* Text Inputs & Search Boxes */
QLineEdit {
    background-color: #ffffff;
    color: #0f172a;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 13px;
    selection-background-color: #2f66ee;
}

QLineEdit:focus {
    border-color: #2f66ee;
    background-color: #ffffff;
}

QLineEdit::placeholder {
    color: #94a3b8;
}

/* Dark Search Input (in Dark Sidebar) */
QLineEdit#darkSearchInput {
    background-color: #13141f;
    color: #f1f5f9;
    border: 1px solid #2b2e42;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}

QLineEdit#darkSearchInput:focus {
    border-color: #2f66ee;
}

QLineEdit#darkSearchInput::placeholder {
    color: #64748b;
}

/* Combo Boxes */
QComboBox {
    background-color: #ffffff;
    color: #334155;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 12px;
}

QComboBox:hover {
    border-color: #94a3b8;
}

QComboBox:focus {
    border-color: #2f66ee;
}

QComboBox::drop-down {
    border: none;
    padding-right: 6px;
}

QComboBox QAbstractItemView {
    background-color: #ffffff;
    color: #0f172a;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    selection-background-color: #eff6ff;
    selection-color: #2f66ee;
    padding: 4px;
}

/* Progress Bar */
QProgressBar {
    border: 1px solid #2b2e42;
    border-radius: 6px;
    text-align: center;
    background-color: #13141f;
    color: #f1f5f9;
    font-size: 11px;
}

QProgressBar::chunk {
    background-color: #2f66ee;
    border-radius: 5px;
}

/* Modern Minimal Scrollbars */
QScrollBar:vertical {
    border: none;
    background-color: #f8fafc;
    width: 8px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background-color: #cbd5e1;
    min-height: 24px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background-color: #94a3b8;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    border: none;
    background-color: #f8fafc;
    height: 8px;
    margin: 0;
}

QScrollBar::handle:horizontal {
    background-color: #cbd5e1;
    min-width: 24px;
    border-radius: 4px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #94a3b8;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}
"""
