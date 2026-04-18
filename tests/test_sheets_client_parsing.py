"""Тесты GoogleSheetsClient.read_rows — парсинг реальной шапки таблицы."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.google.sheets_client import GoogleSheetsClient
from app.models.domain import RawSheetRow


def _make_mock_service(values: list[list[str]]) -> MagicMock:
    """Создать мок sheets_service, возвращающий заданные values."""
    mock_service = MagicMock()
    mock_service.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value = {
        "values": values
    }
    return mock_service


def test_reads_real_broadcaster_header() -> None:
    """Шапка реальной таблицы от broadcaster: L / Chips / Links / Date / Time / Preview / Comments."""
    values = [
        ["L", "Chips", "Links", "Date", "Time", "Preview (Google Drive)", "Comments"],
        ["", "", "https://youtu.be/abc12345678", "15.04.2026", "12:00", "", "note"],
        ["", "", "https://youtu.be/def12345678", "16.04.2026", "18:30", "", ""],
    ]
    client = GoogleSheetsClient(_make_mock_service(values))
    rows = client.read_rows("sheet_id", "A:Z")

    assert len(rows) == 2
    assert isinstance(rows[0], RawSheetRow)
    assert rows[0].row_number == 2
    assert rows[0].link == "https://youtu.be/abc12345678"
    assert rows[0].date_raw == "15.04.2026"
    assert rows[0].time_raw == "12:00"
    assert rows[1].link == "https://youtu.be/def12345678"


def test_reads_cyrillic_header() -> None:
    """Кириллическая шапка тоже должна работать."""
    values = [
        ["Ссылка", "Дата", "Время"],
        ["https://youtu.be/xyz12345678", "20.04.2026", "10:00"],
    ]
    client = GoogleSheetsClient(_make_mock_service(values))
    rows = client.read_rows("sheet_id", "A:Z")

    assert len(rows) == 1
    assert rows[0].link == "https://youtu.be/xyz12345678"


def test_missing_links_raises() -> None:
    """Если нет колонки links — RuntimeError с понятным сообщением."""
    values = [
        ["Date", "Time"],
        ["15.04.2026", "12:00"],
    ]
    client = GoogleSheetsClient(_make_mock_service(values))
    with pytest.raises(RuntimeError, match="links"):
        client.read_rows("sheet_id", "A:Z")


def test_missing_date_raises() -> None:
    values = [["Links", "Time"], ["https://youtu.be/abc", "12:00"]]
    client = GoogleSheetsClient(_make_mock_service(values))
    with pytest.raises(RuntimeError, match="date"):
        client.read_rows("sheet_id", "A:Z")


def test_empty_sheet_returns_empty_list() -> None:
    client = GoogleSheetsClient(_make_mock_service([]))
    rows = client.read_rows("sheet_id", "A:Z")
    assert rows == []


def test_ignores_extra_columns() -> None:
    """Колонки L, Chips, Preview игнорируются — язык/title НЕ из таблицы."""
    values = [
        ["L", "Chips", "Links", "Date", "Time", "Preview (Google Drive)"],
        ["uk", "Мое видео", "https://youtu.be/abc12345678", "15.04.2026", "12:00", "some_url"],
    ]
    client = GoogleSheetsClient(_make_mock_service(values))
    rows = client.read_rows("sheet_id", "A:Z")

    assert len(rows) == 1
    assert rows[0].link == "https://youtu.be/abc12345678"
    assert rows[0].date_raw == "15.04.2026"
    assert not hasattr(rows[0], "language")
    assert not hasattr(rows[0], "title")

