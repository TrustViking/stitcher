"""Настройка логирования для CLI."""
from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

from app.runtime.paths import PROJECT_ROOT

LOGGER_NAME_DEFAULT: str = "stitcher"
LOG_FORMAT_FILE: str = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
LOG_FORMAT_STREAM: str = "%(asctime)s | %(levelname)s | %(message)s"
def get_logger(module_name: str) -> logging.Logger:
    """Вернуть логгер с именем относительно корневого имени stitcher."""
    base = LOGGER_NAME_DEFAULT
    name = str(module_name or "").strip()
    if not name or name == "__main__":
        return logging.getLogger(base)
    if name == base or name.startswith(f"{base}."):
        return logging.getLogger(name)
    if name.startswith("app."):
        suffix = name[4:]
        return logging.getLogger(f"{base}.{suffix}") if suffix else logging.getLogger(base)
    if name.startswith("__"):
        return logging.getLogger(base)
    return logging.getLogger(f"{base}.{name}")


def resolve_log_dir(logs_dir: Path | None = None) -> Path:
    """Вернуть директорию логов (logs/ в корне проекта)."""
    if logs_dir is not None:
        return logs_dir
    return PROJECT_ROOT / "logs"


def resolve_log_file_path(
    *, label: str = LOGGER_NAME_DEFAULT, logs_dir: Path | None = None
) -> Path:
    """Сгенерировать путь к лог-файлу с timestamp."""
    log_dir = resolve_log_dir(logs_dir)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return log_dir / f"{stamp}_{label}.log"


def _remove_and_close_handlers(logger: logging.Logger) -> None:
    """Удалить и закрыть все хэндлеры логгера."""
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()


def setup_logging(debug: bool = False, logs_dir: Path | None = None) -> None:
    """Настроить логирование для CLI-режима.

    - file handler: DEBUG (все записи)
    - stream handler: INFO (stdout)
    """
    log_file = resolve_log_file_path(label=LOGGER_NAME_DEFAULT, logs_dir=logs_dir)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    file_fmt = logging.Formatter(LOG_FORMAT_FILE)
    stream_fmt = logging.Formatter(LOG_FORMAT_STREAM)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.WARNING)
    for h in list(root_logger.handlers):
        root_logger.removeHandler(h)

    base_logger = logging.getLogger(LOGGER_NAME_DEFAULT)
    base_logger.setLevel(logging.DEBUG if debug else logging.DEBUG)
    base_logger.propagate = False
    _remove_and_close_handlers(base_logger)

    stream_handler = logging.StreamHandler(stream=sys.stdout)
    stream_handler.setLevel(logging.WARNING)
    stream_handler.setFormatter(stream_fmt)
    base_logger.addHandler(stream_handler)

    file_handler = logging.FileHandler(filename=str(log_file), mode="a", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_fmt)
    base_logger.addHandler(file_handler)

    logging.getLogger("requests_oauthlib").setLevel(logging.WARNING)
    logging.getLogger("oauthlib").setLevel(logging.WARNING)
    logging.getLogger("googleapiclient.http").setLevel(logging.ERROR)

    base_logger.debug("Logging initialized: file=%s debug=%s", log_file, debug)
