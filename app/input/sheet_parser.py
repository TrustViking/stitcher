"""Парсинг дат и времени из строк Google Sheet."""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Tuple
from zoneinfo import ZoneInfo


def parse_sheet_datetime(date_raw: str, time_raw: str, tz: ZoneInfo) -> datetime:
    """Распарсить дату и время из сырых строк Google Sheet.

    Поддерживаемые форматы даты: DD.MM.YYYY, DD.MM.YY, DD/MM/YYYY, DD/MM/YY,
    YYYY-MM-DD, DDMMYY, DDMMYYYY.
    Поддерживаемые форматы времени: HH:MM, HH.MM, HHMM, HH:MM:SS, H:MM am/pm, H am/pm.

    Выбрасывает ValueError если формат не распознан.
    """
    date_clean: str = date_raw.strip()
    time_clean: str = time_raw.strip()

    date_formats: Tuple[str, ...] = (
        "%d.%m.%Y",
        "%d.%m.%y",
        "%d/%m/%Y",
        "%d/%m/%y",
        "%Y-%m-%d",
        "%d%m%y",
        "%d%m%Y",
    )
    time_formats: Tuple[str, ...] = (
        "%H:%M",
        "%H.%M",
        "%H%M",
        "%H:%M:%S",
        "%I:%M %p",
        "%I %p",
    )

    parsed_date: Optional[datetime] = None
    for fmt in date_formats:
        try:
            parsed_date = datetime.strptime(date_clean, fmt)
            break
        except ValueError:
            continue
    if parsed_date is None:
        raise ValueError(f"Неподдерживаемый формат даты: {date_raw!r}")

    parsed_time: Optional[datetime] = None
    for fmt in time_formats:
        try:
            parsed_time = datetime.strptime(time_clean, fmt)
            break
        except ValueError:
            continue
    if parsed_time is None:
        raise ValueError(f"Неподдерживаемый формат времени: {time_raw!r}")

    return datetime(
        year=parsed_date.year,
        month=parsed_date.month,
        day=parsed_date.day,
        hour=parsed_time.hour,
        minute=parsed_time.minute,
        tzinfo=tz,
    )
