from types import SimpleNamespace

import pytest

from nanobot.bus.queue import MessageBus
from nanobot.channels.telegram import TelegramChannel
from nanobot.config.schema import TelegramConfig


class DummyMessage:
    def __init__(self, chat_id: int, text: str):
        self.chat_id = chat_id
        self.text = text
        self.reply_calls: list[str] = []

    async def reply_text(self, text: str) -> None:
        self.reply_calls.append(text)


def _make_update(chat_id: int, user_id: int, username: str, text: str):
    message = DummyMessage(chat_id=chat_id, text=text)
    user = SimpleNamespace(id=user_id, username=username)
    return SimpleNamespace(message=message, effective_user=user)


def _help_handler(channel: TelegramChannel):
    return getattr(channel, "_on_help", channel._forward_command)


@pytest.mark.asyncio
async def test_help_command_bypasses_allowlist():
    bus = MessageBus()
    config = TelegramConfig(allow_from=["allowed-user"])
    channel = TelegramChannel(config=config, bus=bus)

    update = _make_update(chat_id=100, user_id=999, username="blocked", text="/help")

    await _help_handler(channel)(update, None)

    assert update.message.reply_calls, "Expected /help to reply directly"
    assert "nanobot commands" in update.message.reply_calls[0]


@pytest.mark.asyncio
async def test_non_help_command_still_requires_allowlist():
    bus = MessageBus()
    config = TelegramConfig(allow_from=["allowed-user"])
    channel = TelegramChannel(config=config, bus=bus)

    update = _make_update(chat_id=101, user_id=999, username="blocked", text="/new")

    await channel._forward_command(update, None)

    assert update.message.reply_calls == []
    assert bus.inbound_size == 0


@pytest.mark.asyncio
async def test_start_command_still_replies_without_allowlist():
    bus = MessageBus()
    config = TelegramConfig(allow_from=["allowed-user"])
    channel = TelegramChannel(config=config, bus=bus)

    update = _make_update(chat_id=102, user_id=999, username="blocked", text="/start")
    update.effective_user.first_name = "Casey"

    await channel._on_start(update, None)

    assert update.message.reply_calls, "Expected /start to reply directly"
    assert "Hi Casey" in update.message.reply_calls[0]
