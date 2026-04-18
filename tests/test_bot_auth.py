"""Тесты проверки доступа Telegram-бота."""
from __future__ import annotations

from app.bot.auth import BotAuth


def test_empty_allowed_user_ids_allows_everyone() -> None:
    auth = BotAuth(allowed_user_ids=())
    assert auth.is_allowed(123)
    assert auth.is_allowed(999)


def test_user_in_allowed_list_is_permitted() -> None:
    auth = BotAuth(allowed_user_ids=(100, 200, 300))
    assert auth.is_allowed(200)


def test_user_not_in_allowed_list_is_denied() -> None:
    auth = BotAuth(allowed_user_ids=(100, 200, 300))
    assert auth.is_allowed(777) is False
