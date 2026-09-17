"""Unit tests for Obsidian design system & pixel-accurate components."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.database.repository import DatabaseRepository
from app.telegram.chats import TelegramChat, ChatType
from app.ui.fonts import (
    init_application_fonts,
    has_arabic,
    get_font_for_text,
    get_title_font,
    get_section_header_font,
    get_body_font,
    get_secondary_font,
    get_caption_font,
)
from app.ui.settings_panel import SettingsPanel
from app.ui.chat_list import ChatListWidget, generate_avatar_pixmap
from app.ui.theme_manager import theme_manager, DARK_TOKENS, LIGHT_TOKENS


def test_bundled_fonts_and_typography(qapp):
    """Verify Inter and Cairo fonts initialize and typography scale matches specification."""
    init_application_fonts()

    # Arabic script detection
    assert has_arabic("مجموعة الدراسة") is True
    assert has_arabic("A Plus (سلايدي)") is True
    assert has_arabic("lecture_notes.jpg") is False
    assert has_arabic("Slidy Explorer") is False
    assert has_arabic("") is False

    # Font selection helper
    ar_font = get_font_for_text("مجموعة الدراسة")
    assert "cairo" in ar_font.family().lower() or "cairo" in [f.lower() for f in ar_font.families()]

    en_font = get_font_for_text("lecture_notes.jpg")
    assert "inter" in en_font.family().lower() or "inter" in [f.lower() for f in en_font.families()]

    # Typography sizes and weights
    title_font = get_title_font("Title")
    assert title_font.pixelSize() == 18

    header_font = get_section_header_font("Header")
    assert header_font.pixelSize() == 14

    body_font = get_body_font("Body")
    assert body_font.pixelSize() == 13

    sec_font = get_secondary_font("Secondary")
    assert sec_font.pixelSize() == 12

    cap_font = get_caption_font("Caption")
    assert cap_font.pixelSize() == 11


def test_settings_panel_components_and_signals(qapp, tmp_path):
    """Verify SettingsPanel initializes all 5 controls matching Screenshot 4."""
    db_file = tmp_path / "settings_panel_test.db"
    repo = DatabaseRepository(db_path=db_file)

    panel = SettingsPanel(repo=repo)
    panel.show()

    # Fixed width 320px
    assert panel.width() == 320

    # 1. Theme pills
    assert len(panel.theme_buttons) == 3
    panel._on_theme_pill_clicked("light")
    assert theme_manager.current_theme_mode == "light"
    panel._on_theme_pill_clicked("dark")
    assert theme_manager.current_theme_mode == "dark"

    # 2. Download location picker
    assert panel.dl_path_input.text() != ""

    # 3. Cache limit and clear button
    assert "الذاكرة المؤقتة" in panel.cache_size_label.text()

    # 4. Stepper for concurrent downloads
    initial_val = int(panel.concurrent_val_label.text())
    panel._increment_concurrent()
    assert int(panel.concurrent_val_label.text()) == min(8, initial_val + 1)
    panel._decrement_concurrent()
    assert int(panel.concurrent_val_label.text()) == initial_val

    # 5. Language pills
    emitted_lang = []
    panel.language_changed.connect(lambda l: emitted_lang.append(l))
    panel.btn_lang_en.click()
    assert "en" in emitted_lang

    # Close signal
    close_emitted = []
    panel.close_requested.connect(lambda: close_emitted.append(True))
    panel.btn_close.click()
    assert len(close_emitted) == 1
    panel.close()


def test_chat_list_rail_and_expanded_modes(qapp):
    """Verify ChatListWidget collapsed 72px rail mode vs 280px expanded sidebar."""
    chat_list = ChatListWidget()
    chat_list.show()

    sample_chats = [
        TelegramChat(id=-1001, title="مجموعة الدراسة", chat_type=ChatType.SUPERGROUP),
        TelegramChat(id=-1002, title="Ahmed Hassan", chat_type=ChatType.USER),
        TelegramChat(id=-1003, title="Slidy Explorer", chat_type=ChatType.CHANNEL),
    ]
    chat_list.set_chats(sample_chats)

    # Expanded mode
    chat_list.set_collapsed(False)
    assert chat_list.is_collapsed is False
    assert chat_list.width() == 280
    assert chat_list.list_widget.count() == 3

    # Collapsed rail mode
    chat_list.set_collapsed(True)
    assert chat_list.is_collapsed is True
    assert chat_list.width() == 72
    assert chat_list.rail_items_layout.count() == 3

    # Toggle
    chat_list.toggle_collapse()
    assert chat_list.is_collapsed is False
    assert chat_list.width() == 280

    # Avatar generation with Arabic and Latin text
    pix_ar = generate_avatar_pixmap(sample_chats[0], size=40)
    assert not pix_ar.isNull()
    assert pix_ar.width() == 40

    pix_en = generate_avatar_pixmap(sample_chats[1], size=40)
    assert not pix_en.isNull()
    assert pix_en.width() == 40

    chat_list.close()


def test_theme_manager_toggle(qapp):
    """Verify 1-click theme toggle between dark and light."""
    theme_manager.set_theme("dark")
    assert theme_manager.get_active_tokens()["bg_base"] == DARK_TOKENS["bg_base"]

    theme_manager.toggle_theme()
    assert theme_manager.get_active_tokens()["bg_base"] == LIGHT_TOKENS["bg_base"]

    theme_manager.toggle_theme()
    assert theme_manager.get_active_tokens()["bg_base"] == DARK_TOKENS["bg_base"]
