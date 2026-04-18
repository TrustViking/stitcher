"""Проверка доступа пользователей Telegram-бота."""
from __future__ import annotations


class BotAuth:
    """Проверка доступа по allowed_user_ids."""

    def __init__(
        self,
        user_ids: tuple[int, ...] = (),
        admin_ids: tuple[int, ...] = (),
        *,
        allowed_user_ids: tuple[int, ...] | None = None,
    ) -> None:
        source_user_ids = allowed_user_ids if allowed_user_ids is not None else user_ids
        self._allowed = set(source_user_ids) | set(admin_ids)

    def is_allowed(self, user_id: int) -> bool:
        """Проверить доступ. Если allowed пуст — разрешить всем."""
        if not self._allowed:
            return True
        return user_id in self._allowed
