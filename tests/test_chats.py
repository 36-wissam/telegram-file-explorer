"""Unit tests for Stage 4: Telegram Chat Discovery."""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from pathlib import Path

from app.core.config import Settings
from app.telegram.chats import ChatType, TelegramChat, TelegramChatService
from app.ui.chat_detail import ChatDetailWidget
from app.ui.chat_list import ChatListItemWidget, ChatListWidget


def test_telegram_chat_display_name():
    """Verify display_name fallback hierarchy."""
    chat1 = TelegramChat(id=1, title="Tech News", chat_type=ChatType.CHANNEL)
    assert chat1.display_name == "Tech News"

    chat2 = TelegramChat(id=2, title="", chat_type=ChatType.USER, username="john_doe")
    assert chat2.display_name == "@john_doe"

    chat3 = TelegramChat(id=3, title="", chat_type=ChatType.GROUP)
    assert chat3.display_name == "Chat 3"


def test_determine_chat_type():
    """Verify classification of different Telegram entities and dialogs."""
    manager = MagicMock()
    service = TelegramChatService(manager)

    # User
    user_entity = MagicMock(is_self=False, bot=False)
    dialog_user = MagicMock(is_user=True, is_channel=False, is_group=False)
    assert service._determine_chat_type(user_entity, dialog_user) == ChatType.USER

    # Bot
    bot_entity = MagicMock(is_self=False, bot=True)
    dialog_bot = MagicMock(is_user=True, is_channel=False, is_group=False)
    assert service._determine_chat_type(bot_entity, dialog_bot) == ChatType.BOT

    # Saved Messages
    self_entity = MagicMock(is_self=True, bot=False)
    dialog_self = MagicMock(is_user=True, is_channel=False, is_group=False)
    assert service._determine_chat_type(self_entity, dialog_self) == ChatType.SAVED_MESSAGES

    # Channel
    channel_entity = MagicMock(megagroup=False, gigagroup=False)
    dialog_channel = MagicMock(is_user=False, is_channel=True, is_group=False)
    assert service._determine_chat_type(channel_entity, dialog_channel) == ChatType.CHANNEL

    # Supergroup
    supergroup_entity = MagicMock(megagroup=True, gigagroup=False)
    assert service._determine_chat_type(supergroup_entity, dialog_channel) == ChatType.SUPERGROUP

    # Basic Group
    group_entity = MagicMock()
    dialog_group = MagicMock(is_user=False, is_channel=False, is_group=True)
    assert service._determine_chat_type(group_entity, dialog_group) == ChatType.GROUP


def test_get_dialogs_discovery(tmp_path):
    """Verify dialog fetching and model conversion."""
    settings = Settings()
    settings.data_dir = tmp_path
    settings.sessions_dir = tmp_path / "sessions"
    settings.ensure_directories()

    manager = MagicMock()
    manager.settings = settings
    client = MagicMock()
    client.is_connected.return_value = True
    client.download_profile_photo = AsyncMock(return_value=None)

    # Mock dialog generator
    async def mock_iter_dialogs(limit=100):
        # Dialog 1: Channel
        d1 = MagicMock()
        d1.id = -100112233
        d1.name = "Awesome Tech"
        d1.is_user = False
        d1.is_channel = True
        d1.is_group = False
        d1.unread_count = 5
        d1.pinned = True
        d1.archived = False
        d1.date = datetime(2026, 9, 1, 12, 0)
        d1.entity = MagicMock(megagroup=False, gigagroup=False, username="awesometech")
        yield d1

        # Dialog 2: User
        d2 = MagicMock()
        d2.id = 998877
        d2.name = "John Doe"
        d2.is_user = True
        d2.is_channel = False
        d2.is_group = False
        d2.unread_count = 0
        d2.pinned = False
        d2.archived = False
        d2.date = datetime(2026, 9, 2, 15, 30)
        d2.entity = MagicMock(is_self=False, bot=False, username="johndoe")
        yield d2

    client.iter_dialogs = mock_iter_dialogs
    manager.client = client

    service = TelegramChatService(manager)
    chats = asyncio.run(service.get_dialogs(limit=10))

    assert len(chats) == 2
    assert chats[0].id == -100112233
    assert chats[0].title == "Awesome Tech"
    assert chats[0].chat_type == ChatType.CHANNEL
    assert chats[0].unread_count == 5
    assert chats[0].pinned is True

    assert chats[1].id == 998877
    assert chats[1].title == "John Doe"
    assert chats[1].chat_type == ChatType.USER
    assert chats[1].username == "johndoe"


def test_chat_list_widget_and_filtering(qapp):
    """Verify ChatListWidget populates and filters items correctly."""
    widget = ChatListWidget()

    chats = [
        TelegramChat(id=1, title="Python Developers", chat_type=ChatType.SUPERGROUP, unread_count=2),
        TelegramChat(id=2, title="Daily News", chat_type=ChatType.CHANNEL, unread_count=10),
        TelegramChat(id=3, title="Alice Smith", chat_type=ChatType.USER, username="alice"),
    ]

    widget.set_chats(chats)
    assert widget.list_widget.count() == 3

    # Test category filter: Channels
    widget._set_category_filter("CHANNEL")
    assert widget.list_widget.count() == 1

    # Test category filter: Groups
    widget._set_category_filter("GROUP")
    assert widget.list_widget.count() == 1

    # Test search query filter
    widget._set_category_filter("ALL")
    widget.search_input.setText("Alice")
    assert widget.list_widget.count() == 1

    widget.close()


def test_chat_detail_widget_display(qapp):
    """Verify ChatDetailWidget displays chat information."""
    detail = ChatDetailWidget()
    detail.show()
    assert detail.empty_card.isVisible() is True
    assert detail.content_card.isVisible() is False

    test_chat = TelegramChat(
        id=-100998877,
        title="Secret Lab",
        chat_type=ChatType.SUPERGROUP,
        unread_count=7,
        username="secret_lab",
        last_message_date=datetime(2026, 9, 16, 20, 0),
    )

    detail.set_chat(test_chat)
    assert detail.empty_card.isVisible() is False
    assert detail.content_card.isVisible() is True
    assert "Secret Lab" in detail.title_label.text()
    assert "-100998877" in detail.chat_id_label.text()
    assert "7" in detail.unread_label.text()

    detail.close()

