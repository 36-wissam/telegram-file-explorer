"""Design system styling for Telegram File Explorer conforming strictly to the UI/UX specification."""

DARK_THEME = """
/* Global Application Reset - Dark Theme */
QMainWindow, QDialog {
    background-color: #111113;
    color: #F4F4F5;
    font-family: "Inter", "Segoe UI", -apple-system, BlinkMacSystemFont, Roboto, Helvetica, Arial, sans-serif;
    font-size: 14px;
}

QWidget {
    font-family: "Inter", "Segoe UI", -apple-system, BlinkMacSystemFont, Roboto, Helvetica, Arial, sans-serif;
    font-size: 14px;
    color: #F4F4F5;
}

/* Top Menu Bar */
QMenuBar {
    background-color: #18181B;
    color: #A1A1AA;
    border-bottom: 1px solid #3F3F46;
    padding: 2px 8px;
    font-size: 12px;
}

QMenuBar::item {
    background: transparent;
    padding: 4px 10px;
    border-radius: 6px;
}

QMenuBar::item:selected {
    background-color: #27272A;
    color: #F4F4F5;
}

QMenu {
    background-color: #1C1C1F;
    color: #F4F4F5;
    border: 1px solid #3F3F46;
    border-radius: 8px;
    padding: 6px;
}

QMenu::item {
    padding: 6px 20px;
    border-radius: 6px;
    font-size: 13px;
}

QMenu::item:selected {
    background-color: #229ED9;
    color: #FFFFFF;
}

/* Status Bar */
QStatusBar {
    background-color: #18181B;
    color: #71717A;
    border-top: 1px solid #3F3F46;
    font-size: 12px;
    padding: 4px 12px;
}

/* Standard Buttons */
QPushButton {
    background-color: #27272A;
    color: #F4F4F5;
    border: 1px solid #3F3F46;
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #3F3F46;
    border-color: #71717A;
}

QPushButton:pressed {
    background-color: #1C1C1F;
}

QPushButton:disabled {
    background-color: #18181B;
    color: #71717A;
    border-color: #27272A;
}

/* Primary Action Button */
QPushButton#primaryButton {
    background-color: #229ED9;
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    padding: 8px 18px;
    font-weight: 600;
    font-size: 13px;
}

QPushButton#primaryButton:hover {
    background-color: #3AAFE8;
}

QPushButton#primaryButton:pressed {
    background-color: #1B8CC1;
}

/* Secondary Button */
QPushButton#secondaryButton {
    background-color: transparent;
    color: #A1A1AA;
    border: 1px solid #3F3F46;
    border-radius: 8px;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 500;
}

QPushButton#secondaryButton:hover {
    background-color: #27272A;
    color: #F4F4F5;
    border-color: #71717A;
}

/* Filter Tab / Pill Button */
QPushButton#filterTabButton {
    background-color: transparent;
    color: #A1A1AA;
    border: none;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 12px;
    font-weight: 500;
}

QPushButton#filterTabButton:hover {
    background-color: #27272A;
    color: #F4F4F5;
}

QPushButton#filterTabButton:checked {
    background-color: #27272A;
    color: #229ED9;
    font-weight: 600;
}

/* Media Navigation Tabs */
QPushButton#mediaTabButton {
    background-color: transparent;
    color: #A1A1AA;
    border: none;
    border-bottom: 2px solid transparent;
    border-radius: 0px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 500;
}

QPushButton#mediaTabButton:hover {
    color: #F4F4F5;
}

QPushButton#mediaTabButton:checked {
    color: #229ED9;
    border-bottom: 2px solid #229ED9;
    font-weight: 600;
}

/* Text Inputs & Search Boxes */
QLineEdit {
    background-color: #1C1C1F;
    color: #F4F4F5;
    border: 1px solid #3F3F46;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 13px;
    selection-background-color: #229ED9;
}

QLineEdit:focus {
    border-color: #229ED9;
    background-color: #1C1C1F;
}

QLineEdit::placeholder {
    color: #71717A;
}

/* Combo Boxes */
QComboBox {
    background-color: #1C1C1F;
    color: #F4F4F5;
    border: 1px solid #3F3F46;
    border-radius: 8px;
    padding: 6px 12px;
    font-size: 12px;
}

QComboBox:hover {
    border-color: #71717A;
}

QComboBox:focus {
    border-color: #229ED9;
}

QComboBox::drop-down {
    border: none;
    padding-right: 8px;
}

QComboBox QAbstractItemView {
    background-color: #1C1C1F;
    color: #F4F4F5;
    border: 1px solid #3F3F46;
    border-radius: 8px;
    selection-background-color: #27272A;
    selection-color: #229ED9;
    padding: 4px;
}

/* Progress Bar */
QProgressBar {
    border: 1px solid #3F3F46;
    border-radius: 6px;
    text-align: center;
    background-color: #18181B;
    color: #F4F4F5;
    font-size: 11px;
}

QProgressBar::chunk {
    background-color: #229ED9;
    border-radius: 5px;
}

/* Scrollbars */
QScrollBar:vertical {
    border: none;
    background-color: #111113;
    width: 8px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background-color: #3F3F46;
    min-height: 24px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background-color: #71717A;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    border: none;
    background-color: #111113;
    height: 8px;
    margin: 0;
}

QScrollBar::handle:horizontal {
    background-color: #3F3F46;
    min-width: 24px;
    border-radius: 4px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #71717A;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}
"""

LIGHT_THEME = """
/* Global Application Reset - Light Theme */
QMainWindow, QDialog {
    background-color: #F7F7F8;
    color: #18181B;
    font-family: "Inter", "Segoe UI", -apple-system, BlinkMacSystemFont, Roboto, Helvetica, Arial, sans-serif;
    font-size: 14px;
}

QWidget {
    font-family: "Inter", "Segoe UI", -apple-system, BlinkMacSystemFont, Roboto, Helvetica, Arial, sans-serif;
    font-size: 14px;
    color: #18181B;
}

/* Top Menu Bar */
QMenuBar {
    background-color: #FFFFFF;
    color: #71717A;
    border-bottom: 1px solid #E4E4E7;
    padding: 2px 8px;
    font-size: 12px;
}

QMenuBar::item {
    background: transparent;
    padding: 4px 10px;
    border-radius: 6px;
}

QMenuBar::item:selected {
    background-color: #F1F1F3;
    color: #18181B;
}

QMenu {
    background-color: #FFFFFF;
    color: #18181B;
    border: 1px solid #E4E4E7;
    border-radius: 8px;
    padding: 6px;
}

QMenu::item {
    padding: 6px 20px;
    border-radius: 6px;
    font-size: 13px;
}

QMenu::item:selected {
    background-color: #229ED9;
    color: #FFFFFF;
}

/* Status Bar */
QStatusBar {
    background-color: #FFFFFF;
    color: #71717A;
    border-top: 1px solid #E4E4E7;
    font-size: 12px;
    padding: 4px 12px;
}

/* Standard Buttons */
QPushButton {
    background-color: #FFFFFF;
    color: #18181B;
    border: 1px solid #E4E4E7;
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #F1F1F3;
    border-color: #A1A1AA;
}

QPushButton:pressed {
    background-color: #E4E4E7;
}

QPushButton:disabled {
    background-color: #F7F7F8;
    color: #A1A1AA;
    border-color: #E4E4E7;
}

/* Primary Action Button */
QPushButton#primaryButton {
    background-color: #229ED9;
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    padding: 8px 18px;
    font-weight: 600;
    font-size: 13px;
}

QPushButton#primaryButton:hover {
    background-color: #1B8CC1;
}

QPushButton#primaryButton:pressed {
    background-color: #15739F;
}

/* Secondary Button */
QPushButton#secondaryButton {
    background-color: transparent;
    color: #71717A;
    border: 1px solid #E4E4E7;
    border-radius: 8px;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 500;
}

QPushButton#secondaryButton:hover {
    background-color: #F1F1F3;
    color: #18181B;
    border-color: #A1A1AA;
}

/* Filter Tab / Pill Button */
QPushButton#filterTabButton {
    background-color: transparent;
    color: #71717A;
    border: none;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 12px;
    font-weight: 500;
}

QPushButton#filterTabButton:hover {
    background-color: #F1F1F3;
    color: #18181B;
}

QPushButton#filterTabButton:checked {
    background-color: #F1F1F3;
    color: #229ED9;
    font-weight: 600;
}

/* Media Navigation Tabs */
QPushButton#mediaTabButton {
    background-color: transparent;
    color: #71717A;
    border: none;
    border-bottom: 2px solid transparent;
    border-radius: 0px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 500;
}

QPushButton#mediaTabButton:hover {
    color: #18181B;
}

QPushButton#mediaTabButton:checked {
    color: #229ED9;
    border-bottom: 2px solid #229ED9;
    font-weight: 600;
}

/* Text Inputs & Search Boxes */
QLineEdit {
    background-color: #FFFFFF;
    color: #18181B;
    border: 1px solid #E4E4E7;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 13px;
    selection-background-color: #229ED9;
}

QLineEdit:focus {
    border-color: #229ED9;
    background-color: #FFFFFF;
}

QLineEdit::placeholder {
    color: #A1A1AA;
}

/* Combo Boxes */
QComboBox {
    background-color: #FFFFFF;
    color: #18181B;
    border: 1px solid #E4E4E7;
    border-radius: 8px;
    padding: 6px 12px;
    font-size: 12px;
}

QComboBox:hover {
    border-color: #A1A1AA;
}

QComboBox:focus {
    border-color: #229ED9;
}

QComboBox::drop-down {
    border: none;
    padding-right: 8px;
}

QComboBox QAbstractItemView {
    background-color: #FFFFFF;
    color: #18181B;
    border: 1px solid #E4E4E7;
    border-radius: 8px;
    selection-background-color: #F1F1F3;
    selection-color: #229ED9;
    padding: 4px;
}

/* Progress Bar */
QProgressBar {
    border: 1px solid #E4E4E7;
    border-radius: 6px;
    text-align: center;
    background-color: #F1F1F3;
    color: #18181B;
    font-size: 11px;
}

QProgressBar::chunk {
    background-color: #229ED9;
    border-radius: 5px;
}

/* Scrollbars */
QScrollBar:vertical {
    border: none;
    background-color: #F7F7F8;
    width: 8px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background-color: #E4E4E7;
    min-height: 24px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background-color: #A1A1AA;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    border: none;
    background-color: #F7F7F8;
    height: 8px;
    margin: 0;
}

QScrollBar::handle:horizontal {
    background-color: #E4E4E7;
    min-width: 24px;
    border-radius: 4px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #A1A1AA;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}
"""

