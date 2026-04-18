"""Загрузчик secrets/.env → EnvConfig."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from app.config.settings import EnvConfig
from app.runtime.paths import PROJECT_ROOT

ENV_FILE_PATH: Path = PROJECT_ROOT / "secrets" / ".env"


def load_env_file() -> None:
    """Загрузить secrets/.env в os.environ. Должно вызываться первым в main().

    Если файл отсутствует — молча продолжаем (preflight сам выдаст ошибку
    по отсутствию обязательных полей). Существующие переменные окружения
    НЕ перезаписываются (override=False).
    """
    if ENV_FILE_PATH.exists():
        load_dotenv(ENV_FILE_PATH, override=False)


def load_env_config() -> EnvConfig:
    """Собрать EnvConfig из os.environ. Вызывать только после load_env_file()."""
    return EnvConfig(
        google_sheets_id=_get_str("GOOGLE_SHEETS_ID"),
        google_drive_folder_id=_get_str("GOOGLE_DRIVE_FOLDER_ID"),
        telegram_bot_token=_get_str("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=_get_str("TELEGRAM_CHAT_ID"),
        telegram_admin_user_ids=_get_int_tuple("TELEGRAM_ADMIN_USER_IDS"),
        telegram_user_ids=_get_int_tuple("TELEGRAM_USER_IDS"),
    )


def _get_str(name: str) -> str:
    return (os.getenv(name) or "").strip()


def _get_int_tuple(name: str) -> tuple[int, ...]:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return ()
    result: list[int] = []
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            result.append(int(part))
        except ValueError:
            continue
    return tuple(result)
