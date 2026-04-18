"""Google Sheets клиент — читает строки и возвращает RawSheetRow."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple, cast

from app.models.domain import RawSheetRow
from app.runtime.logging_config import get_logger

try:
    from googleapiclient.errors import HttpError
except ImportError:
    HttpError = Exception  # type: ignore


LOGGER = get_logger(__name__)


class GoogleSheetsClient:
    """Клиент для чтения данных из Google Sheets."""

    def __init__(self, sheets_service: Any) -> None:
        self._sheets_service: Any = sheets_service

    def ping_access(self, spreadsheet_id: str) -> Tuple[str, str]:
        """Проверить доступ к таблице. Вернуть (spreadsheet_id, title)."""
        response: Dict[str, Any] = cast(
            Dict[str, Any],
            self._sheets_service.spreadsheets()
            .get(
                spreadsheetId=spreadsheet_id,
                fields="spreadsheetId,properties(title)",
            )
            .execute(),
        )
        resolved_id: str = str(response.get("spreadsheetId") or spreadsheet_id).strip()
        props: Dict[str, Any] = cast(Dict[str, Any], response.get("properties", {}))
        title: str = str(props.get("title") or "unknown").strip() or "unknown"
        return (resolved_id, title)

    def read_rows(self, spreadsheet_id: str, range_name: str) -> List[RawSheetRow]:
        """Прочитать строки из таблицы и вернуть список RawSheetRow.

        Ищет только 3 обязательные колонки: Links, Date, Time.
        Все остальные колонки (L, Chips, Preview, Comments и любые другие)
        игнорируются — язык и title определяются скриптом через yt-dlp.
        """
        try:
            response = (
                self._sheets_service.spreadsheets()
                .values()
                .get(spreadsheetId=spreadsheet_id, range=range_name)
                .execute()
            )
        except HttpError as error:
            error_text: str = str(error)
            if "Unable to parse range" not in error_text:
                raise
            LOGGER.warning(
                "Range %s невалиден для таблицы %s; fallback на A:Z.",
                range_name,
                spreadsheet_id,
            )
            response = (
                self._sheets_service.spreadsheets()
                .values()
                .get(spreadsheetId=spreadsheet_id, range="A:Z")
                .execute()
            )

        values: List[List[str]] = cast(List[List[str]], response.get("values", []))
        if not values:
            LOGGER.warning("Google Sheets диапазон пустой: %s", range_name)
            return []

        header: List[str] = [str(v).strip() for v in values[0]]
        norm_header: List[str] = [_normalize_header(h) for h in header]

        links_index = _find_col(norm_header, ("links", "link", "url", "video", "youtube", "ссылка"))
        date_index = _find_col(norm_header, ("date", "дата", "day"))
        time_index = _find_col(norm_header, ("time", "время", "час", "hour"))

        LOGGER.debug(
            "Sheets header: links=%s date=%s time=%s (найдены колонки: %r)",
            links_index,
            date_index,
            time_index,
            header,
        )

        missing: List[str] = []
        if links_index is None:
            missing.append("links/url")
        if date_index is None:
            missing.append("date/дата")
        if time_index is None:
            missing.append("time/время")

        if missing:
            raise RuntimeError(
                f"Google Sheets header не распознан. "
                f"Не найдены колонки: {missing!r}. "
                f"Найдены колонки: {header!r}."
            )

        rows: List[RawSheetRow] = []
        for row_number, row_values in enumerate(values[1:], start=2):
            rows.append(
                RawSheetRow(
                    row_number=row_number,
                    link=_cell(row_values, links_index),  # type: ignore[arg-type]
                    date_raw=_cell(row_values, date_index),  # type: ignore[arg-type]
                    time_raw=_cell(row_values, time_index),  # type: ignore[arg-type]
                )
            )
        LOGGER.debug("Прочитано %d строк из таблицы.", len(rows))
        return rows


def _cell(row_values: List[str], index: int) -> str:
    """Безопасно извлечь значение ячейки по индексу."""
    if index >= len(row_values):
        return ""
    return str(row_values[index]).strip()


def _normalize_header(value: str) -> str:
    """Нормализовать имя колонки: нижний регистр, убрать не-буквенно-цифровые символы."""
    return re.sub(r"[^a-zа-я0-9]+", "", value.strip().lower(), flags=re.IGNORECASE)


def _find_col(
    normalized_header: List[str],
    aliases: Tuple[str, ...],
) -> Optional[int]:
    """Найти индекс колонки по списку псевдонимов."""
    norm_aliases = tuple(_normalize_header(a) for a in aliases)
    # Точное совпадение
    for i, name in enumerate(normalized_header):
        if name in norm_aliases:
            return i
    # Вхождение подстроки
    for i, name in enumerate(normalized_header):
        if any(alias in name for alias in norm_aliases if alias):
            return i
    return None
