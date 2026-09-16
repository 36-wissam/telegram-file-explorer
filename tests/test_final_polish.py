"""Unit tests for Stage 15: Final Application Polish and Shortcuts."""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from main import parse_args
from app.core.config import settings
from app.database.models import IndexedFileModel
from app.database.repository import DatabaseRepository
from app.telegram.auth import AuthState, TelegramAuthService
from app.telegram.chats import TelegramChatService
from app.telegram.client import TelegramClientManager
from app.ui.file_explorer import FileExplorerWidget
from app.ui.main_window import MainWindow


@pytest.fixture
def app():
    """Ensure QApplication instance exists for GUI tests."""
    app_instance = QApplication.instance()
    if not app_instance:
        app_instance = QApplication([])
    return app_instance


def test_cli_argument_parsing():
    """Verify CLI arguments parsing for debug and version flags."""
    args = parse_args([])
    assert args.debug is False

    args_debug = parse_args(["--debug"])
    assert args_debug.debug is True

    with pytest.raises(SystemExit):
        parse_args(["--version"])


def test_file_explorer_empty_state_and_clear_filters(app, tmp_path):
    """Verify empty state switching and clearing active filters."""
    db_file = tmp_path / "empty_test.db"
    repo = DatabaseRepository(db_path=db_file)

    widget = FileExplorerWidget(repo=repo)

    # Initially with 0 files, empty state card should be shown (page 1)
    assert widget.content_stack.currentIndex() == 1
    assert "No Indexed Files Yet" in widget.empty_title.text()
    assert widget.btn_clear_filters.isHidden() is True

    # Simulate entering a search query that has no match
    widget.search_input.setText("nonexistent_filename_query")
    assert widget.content_stack.currentIndex() == 1
    assert "No Matching Files Found" in widget.empty_title.text()
    assert widget.btn_clear_filters.isHidden() is False

    # Test focus_search
    with patch.object(widget.search_input, "setFocus") as mock_set_focus:
        widget.focus_search()
        mock_set_focus.assert_called_once()

    # Clear filters via empty card button
    widget._clear_all_filters()
    assert widget.search_input.text() == ""
    assert widget._search_query == ""
    assert widget._current_category is None


def test_file_explorer_shows_table_when_files_exist(app, tmp_path):
    """Verify table is shown on index 0 when files are present."""
    db_file = tmp_path / "files_test.db"
    repo = DatabaseRepository(db_path=db_file)

    from app.services.media_parser import MediaFileMetadata, MediaType
    meta = MediaFileMetadata(
        file_id="f1",
        message_id=1,
        chat_id=100,
        chat_title="Main Chat",
        filename="report.pdf",
        extension=".pdf",
        mime_type="application/pdf",
        file_size=2048,
        media_type=MediaType.DOCUMENT,
        message_date=datetime.now(timezone.utc),
    )
    repo.save_files_batch([meta])

    widget = FileExplorerWidget(repo=repo)
    assert widget.content_stack.currentIndex() == 0
    assert widget.table.rowCount() == 1


def test_main_window_shortcuts_and_status_indicators(app, tmp_path):
    """Verify global shortcuts, menu items, and permanent status widgets."""
    db_file = tmp_path / "mw_test.db"
    repo = DatabaseRepository(db_path=db_file)

    client_manager = MagicMock(spec=TelegramClientManager)
    auth_service = MagicMock(spec=TelegramAuthService)
    auth_service.state = AuthState.UNAUTHORIZED
    auth_service.current_user = None

    chat_service = MagicMock(spec=TelegramChatService)

    window = MainWindow(
        client_manager=client_manager,
        auth_service=auth_service,
        chat_service=chat_service,
        repo=repo,
    )

    # Check shortcuts
    assert window.action_find_files.shortcut().toString() == "Ctrl+F"
    assert window.action_refresh_all.shortcut().toString() == "F5"
    assert window.action_login.shortcut().toString() == "Ctrl+L"
    assert window.action_view_downloads.shortcut().toString() == "Ctrl+J"
    assert window.action_index_manager.shortcut().toString() == "Ctrl+I"

    # Status indicators initial state (not signed in)
    assert "Not Signed In" in window.status_auth_indicator.text()
    assert "files" in window.status_files_indicator.text()

    # Transition to authorized
    auth_service.state = AuthState.AUTHORIZED
    auth_service.current_user = {
        "id": 12345,
        "first_name": "Alice",
        "last_name": "Smith",
        "username": "alicesmith",
    }
    window.update_auth_ui()

    assert "Alice Smith" in window.status_auth_indicator.text()

    # Test _on_find_files switches to file explorer and focuses search
    with patch.object(window.file_explorer_widget, "focus_search") as mock_focus:
        window._on_find_files()
        assert window.view_stack.currentIndex() == 1
        mock_focus.assert_called_once()

    # Test _show_about dialog does not raise errors
    with patch("PySide6.QtWidgets.QMessageBox.about") as mock_about:
        window._show_about()
        assert mock_about.called
