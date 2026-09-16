"""Modern dark stylesheet for Telegram File Explorer."""

DARK_THEME = """
QMainWindow, QWidget {
    background-color: #18191c;
    color: #e3e5e8;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    font-size: 13px;
}

QMenuBar {
    background-color: #1e1f22;
    color: #dbdee1;
    border-bottom: 1px solid #2b2d31;
    padding: 2px 6px;
}

QMenuBar::item {
    background: transparent;
    padding: 4px 8px;
    border-radius: 4px;
}

QMenuBar::item:selected {
    background-color: #35373c;
}

QMenu {
    background-color: #2b2d31;
    color: #dbdee1;
    border: 1px solid #1e1f22;
    border-radius: 6px;
    padding: 4px;
}

QMenu::item {
    padding: 6px 24px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: #4752c4;
    color: #ffffff;
}

QStatusBar {
    background-color: #1e1f22;
    color: #949ba4;
    border-top: 1px solid #2b2d31;
    font-size: 12px;
    padding: 4px 8px;
}

QLabel {
    color: #e3e5e8;
}

QPushButton {
    background-color: #2b2d31;
    color: #ffffff;
    border: 1px solid #35373c;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #35373c;
}

QPushButton:pressed {
    background-color: #1e1f22;
}

QPushButton:disabled {
    background-color: #232428;
    color: #5c5f66;
    border-color: #2b2d31;
}

QPushButton#primaryButton {
    background-color: #5865f2;
    border: none;
}

QPushButton#primaryButton:hover {
    background-color: #4752c4;
}

QPushButton#primaryButton:pressed {
    background-color: #3c45a5;
}

QProgressBar {
    border: 1px solid #35373c;
    border-radius: 6px;
    text-align: center;
    background-color: #1e1f22;
    color: #e3e5e8;
}

QProgressBar::chunk {
    background-color: #5865f2;
    border-radius: 5px;
}
"""
