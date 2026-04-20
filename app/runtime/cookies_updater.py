"""Проверка состояния файла YouTube cookies."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class CookiesUpdateStatus:
    cookies_file: Optional[Path]   # путь к файлу (None если не настроен)
    file_exists: bool
    file_age_days: Optional[int]   # возраст файла в днях по mtime
    message: str


def check_cookies(
    *,
    cookies_file: Optional[Path],
    warn_age_days: int,
    logger: logging.Logger,
) -> CookiesUpdateStatus:
    """Проверить наличие и возраст файла cookies.

    Правила:
    - Если cookies_file is None — вернуть статус «не настроены».
    - Если файл не существует — залогировать ERROR, вернуть статус «файл не найден».
    - Если файл существует — залогировать возраст,
      WARNING если возраст > warn_age_days.
    """
    if cookies_file is None:
        logger.warning(
            "cookies: файл не настроен в config.toml. "
            "Укажите [ytdlp].cookies_file и положите файл cookies в secrets/."
        )
        return CookiesUpdateStatus(
            cookies_file=None,
            file_exists=False,
            file_age_days=None,
            message="не настроены",
        )

    if not cookies_file.exists():
        logger.error(
            "cookies: файл не найден: %s — "
            "экспортируйте cookies через расширение браузера "
            "и положите файл в secrets/cookies.txt",
            cookies_file,
        )
        return CookiesUpdateStatus(
            cookies_file=cookies_file,
            file_exists=False,
            file_age_days=None,
            message="файл не найден",
        )

    age = _file_age_days(cookies_file)

    if age > warn_age_days:
        logger.warning(
            "cookies: файл устарел (%d дн. > %d дн.): %s — "
            "рекомендуется обновить cookies через расширение браузера",
            age,
            warn_age_days,
            cookies_file,
        )
    else:
        logger.debug("cookies: файл актуален, возраст %d дн.: %s", age, cookies_file)

    return CookiesUpdateStatus(
        cookies_file=cookies_file,
        file_exists=True,
        file_age_days=age,
        message="актуальны" if age <= warn_age_days else f"устарели ({age} дн.)",
    )


def _file_age_days(path: Path) -> int:
    """Возраст файла в полных днях по mtime."""
    mtime = path.stat().st_mtime
    age_seconds = time.time() - mtime
    return max(0, int(age_seconds // 86400))
