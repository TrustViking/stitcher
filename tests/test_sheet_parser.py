"""Тесты парсинга дат и времени из строк Google Sheet."""
from __future__ import annotations

from datetime import timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pytest

from app.input.sheet_parser import parse_sheet_datetime

try:
    _KYIV = ZoneInfo("Europe/Kyiv")
except ZoneInfoNotFoundError:
    _KYIV = timezone.utc


def test_date_dot_format() -> None:
    dt = parse_sheet_datetime("23.03.2026", "14:00", _KYIV)
    assert dt.day == 23
    assert dt.month == 3
    assert dt.year == 2026
    assert dt.hour == 14
    assert dt.minute == 0


def test_date_slash_format() -> None:
    dt = parse_sheet_datetime("23/03/2026", "14:00", _KYIV)
    assert dt.day == 23
    assert dt.month == 3
    assert dt.year == 2026


def test_date_iso_format() -> None:
    dt = parse_sheet_datetime("2026-03-23", "14:00", _KYIV)
    assert dt.day == 23
    assert dt.month == 3
    assert dt.year == 2026


def test_time_dot_format() -> None:
    dt = parse_sheet_datetime("23.03.2026", "14.00", _KYIV)
    assert dt.hour == 14
    assert dt.minute == 0


def test_time_no_separator() -> None:
    dt = parse_sheet_datetime("23.03.2026", "1400", _KYIV)
    assert dt.hour == 14
    assert dt.minute == 0


def test_time_with_seconds() -> None:
    dt = parse_sheet_datetime("23.03.2026", "14:00:30", _KYIV)
    assert dt.hour == 14
    assert dt.minute == 0


def test_invalid_date_raises() -> None:
    with pytest.raises(ValueError, match="формат даты"):
        parse_sheet_datetime("not-a-date", "14:00", _KYIV)


def test_invalid_time_raises() -> None:
    with pytest.raises(ValueError, match="формат времени"):
        parse_sheet_datetime("23.03.2026", "not-a-time", _KYIV)


def test_timezone_attached() -> None:
    dt = parse_sheet_datetime("23.03.2026", "14:00", _KYIV)
    assert dt.tzinfo == _KYIV
