"""Application entry point for Telegram File Explorer."""

import sys
from PySide6.QtWidgets import QApplication

from app.core.config import settings
from app.core.logger import setup_logging, get_logger
from app.ui.main_window import MainWindow
from app.ui.styles import DARK_THEME


def main():
    """Main execution function."""
    # Initialize logging system
    logger = setup_logging()
    logger.info("==========================================")
    logger.info("Starting %s v%s", settings.app_name, settings.app_version)
    logger.info("Base directory: %s", settings.base_dir)
    logger.info("Data directory: %s", settings.data_dir)
    logger.info("Logs directory: %s", settings.logs_dir)
    logger.info(
        "Telegram configured: %s",
        "Yes" if settings.is_telegram_configured else "No (Credentials missing in .env)",
    )
    logger.info("==========================================")

    # Initialize PySide6 Application
    app = QApplication(sys.argv)
    app.setApplicationName(settings.app_name)
    app.setApplicationVersion(settings.app_version)

    # Apply application-wide dark styling
    app.setStyleSheet(DARK_THEME)

    # Create and show main window
    window = MainWindow()
    window.show()

    logger.info("Application UI launched. Entering Qt event loop.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
