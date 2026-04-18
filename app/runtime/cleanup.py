"""Автоочистка временных и лог-файлов при старте."""
from __future__ import annotations

import logging
import time
from pathlib import Path

_MARKER_FILENAME: str = ".last_cleanup"


def _should_run_cleanup(marker_path: Path) -> bool:
    """Вернуть True если очистка не запускалась сегодня (маркер старше 24ч или отсутствует)."""
    if not marker_path.exists():
        return True
    try:
        age_seconds: float = time.time() - marker_path.stat().st_mtime
        return age_seconds > 86400
    except OSError:
        return True


def _touch_marker(marker_path: Path) -> None:
    """Создать или обновить маркер-файл последней очистки."""
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_text(
        f"Last cleanup: {time.strftime('%Y-%m-%d %H:%M:%S')}\n",
        encoding="utf-8",
    )


def _remove_stale_files(
    directory: Path,
    *,
    max_age_seconds: float,
    logger: logging.Logger,
) -> int:
    """Удалить файлы старше max_age_seconds. Вернуть количество удалённых."""
    if not directory.is_dir():
        return 0

    removed_count: int = 0
    now_seconds: float = time.time()

    for item in directory.rglob("*"):
        if not item.is_file():
            continue
        if item.name.startswith("."):
            continue
        try:
            age = now_seconds - item.stat().st_mtime
            if age <= max_age_seconds:
                continue
            item.unlink()
            removed_count += 1
            logger.debug("cleanup: removed %s (age=%.0fh)", item, age / 3600.0)
        except OSError as error:
            logger.warning("cleanup: failed to remove %s: %s", item, error)

    # Удалить пустые поддиректории
    for sub in sorted(directory.rglob("*"), reverse=True):
        if not sub.is_dir():
            continue
        try:
            sub.rmdir()
        except OSError:
            continue

    return removed_count


def run_startup_cleanup(
    *,
    logger: logging.Logger,
    temp_dir: Path,
    logs_dir: Path,
    state_dir: Path,
    temp_max_age_days: int,
    logs_max_age_days: int,
) -> None:
    """Запустить очистку temp и logs при старте.

    Пропускает очистку если уже запускалась сегодня.
    Ошибки очистки не останавливают пайплайн — логируются как WARNING.
    """
    marker_path = state_dir / _MARKER_FILENAME
    if not _should_run_cleanup(marker_path):
        logger.debug("cleanup: skipped (already ran within 24h)")
        return

    logger.info(
        "cleanup: starting (temp_max_age=%dd, logs_max_age=%dd)",
        temp_max_age_days,
        logs_max_age_days,
    )
    total_removed: int = 0

    if temp_max_age_days > 0:
        try:
            total_removed += _remove_stale_files(
                temp_dir,
                max_age_seconds=float(temp_max_age_days) * 86400.0,
                logger=logger,
            )
        except Exception as error:
            logger.warning("cleanup: temp cleanup failed: %s", error)

    if logs_max_age_days > 0:
        try:
            total_removed += _remove_stale_files(
                logs_dir,
                max_age_seconds=float(logs_max_age_days) * 86400.0,
                logger=logger,
            )
        except Exception as error:
            logger.warning("cleanup: logs cleanup failed: %s", error)

    _touch_marker(marker_path)
    logger.info("cleanup: done, removed %d stale file(s)", total_removed)
