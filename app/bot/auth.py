"""Проверка доступа пользователей Telegram-бота."""
from __future__ import annotations


class BotAuth:
    """Проверка доступа по allowed_user_ids."""

    def __init__(
        self,
        user_ids: tuple[int, ...],
        admin_ids: tuple[int, ...] = (),
    ) -> None:
        self._allowed = set(user_ids) | set(admin_ids)

    def is_allowed(self, user_id: int) -> bool:
        """Проверить доступ. Если allowed пуст — разрешить всем."""
        if not self._allowed:
            return True
        return user_id in self._allowed
