"""Тесты для cookies_updater."""
from pathlib import Path
import logging
import pytest

from app.runtime.cookies_updater import check_cookies


def test_cookies_not_configured():
    """Если cookies_file=None — статус «не настроены», файл не найден."""
    status = check_cookies(
        cookies_file=None,
        warn_age_days=7,
        logger=logging.getLogger("test"),
    )
    assert status.cookies_file is None
    assert not status.file_exists
    assert status.file_age_days is None
    assert status.message == "не настроены"


def test_cookies_file_missing(tmp_path):
    """Если файл не существует — статус «файл не найден»."""
    missing = tmp_path / "cookies.txt"
    status = check_cookies(
        cookies_file=missing,
        warn_age_days=7,
        logger=logging.getLogger("test"),
    )
    assert not status.file_exists
    assert status.file_age_days is None
    assert "не найден" in status.message


def test_cookies_file_exists(tmp_path):
    """Если файл существует — статус содержит возраст."""
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n")
    status = check_cookies(
        cookies_file=cookies,
        warn_age_days=7,
        logger=logging.getLogger("test"),
    )
    assert status.file_exists
    assert status.file_age_days is not None
    assert status.file_age_days >= 0
