"""SlotLoader — читает Google Sheet и группирует строки в StitchJob."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.config.settings import StitcherConfig
from app.google.sheets_client import GoogleSheetsClient
from app.ingest.youtube_metadata import YtDlpBinaryMetadataFetcher
from app.input.row_enricher import RowEnricher
from app.input.sheet_parser import parse_sheet_datetime
from app.models.domain import SlotKey, SourceVideo, StitchJob
from app.runtime.logging_config import get_logger

LOGGER = get_logger(__name__)
try:
    _KYIV_TZ = ZoneInfo("Europe/Kyiv")
except ZoneInfoNotFoundError:
    _KYIV_TZ = timezone.utc
SHEETS_RANGE = "A:Z"


@dataclass
class SlotLoadReport:
    jobs: list[StitchJob]
    total_rows: int
    enriched_rows: int
    recognized_columns: list[str]
    rows_by_language: dict[str, int] = field(default_factory=dict)


class SlotLoader:
    """Загружает будущие слоты из Google Sheet."""

    def __init__(
        self,
        sheets_client: GoogleSheetsClient,
        enricher: RowEnricher | None = None,
        *,
        config: StitcherConfig,
        sheets_id: str,
    ) -> None:
        self._sheets_client = sheets_client
        self._enricher = enricher
        self._config = config
        self._sheets_id = sheets_id.strip()

    def load_future_slots(self) -> SlotLoadReport:
        """Загрузить строки из Google Sheet и вернуть отчет по будущим слотам.

        Алгоритм:
        1. Читаем сырые строки через sheets_client.
        2. Обогащаем строки через RowEnricher (metadata + language).
        3. Парсим date_raw + time_raw (Kyiv TZ).
        4. Отфильтровываем прошлые слоты.
        5. Группируем по SlotKey(date, time, language).
        6. Внутри слота сохраняем порядок видео по row_number.
        7. Возвращаем отсортированный список StitchJob.
        """
        if not self._sheets_id:
            raise RuntimeError(
                "google.sheets_id не задан в config.toml. "
                "Укажите ID Google Sheets таблицы в секцию [google]."
            )

        raw_rows = self._sheets_client.read_rows(self._sheets_id, SHEETS_RANGE)
        LOGGER.debug("Прочитано %d сырых строк из Google Sheets.", len(raw_rows))

        if self._enricher is None:
            self._enricher = RowEnricher(
                metadata_fetcher=YtDlpBinaryMetadataFetcher(
                    ytdlp_path=self._config.tools.ytdlp_path
                )
            )

        rows = self._enricher.enrich(raw_rows)
        LOGGER.debug("Обогащено %d строк.", len(rows))

        now = datetime.now(_KYIV_TZ)

        # --- Группировка: slot_key → list[(slot_datetime, SourceVideo)] ---
        groups: Dict[SlotKey, List[tuple[datetime, SourceVideo]]] = defaultdict(list)
        slot_datetimes: Dict[SlotKey, datetime] = {}

        for row in rows:
            LOGGER.debug(
                "row %d: title=%r url=%r date=%r time=%r language=%r",
                row.row_number,
                row.title,
                row.link,
                row.date_raw,
                row.time_raw,
                row.language,
            )
            try:
                slot_dt = parse_sheet_datetime(row.date_raw, row.time_raw, _KYIV_TZ)
            except ValueError as exc:
                LOGGER.warning(
                    "row %d: не удалось распарсить дату/время (%r / %r): %s — пропускаем.",
                    row.row_number,
                    row.date_raw,
                    row.time_raw,
                    exc,
                )
                continue

            if slot_dt <= now:
                LOGGER.debug(
                    "row %d: слот %s в прошлом, пропускаем.",
                    row.row_number,
                    slot_dt.strftime("%d.%m.%Y %H:%M"),
                )
                continue

            key = SlotKey(
                date=slot_dt.strftime("%d-%m-%Y"),
                time=slot_dt.strftime("%H-%M"),
                language=row.language.strip().lower() or "unknown",
            )
            video = SourceVideo(
                url=row.link,
                title=row.title,
                order=row.row_number,  # временно используем row_number, переиндексируем ниже
            )
            groups[key].append((slot_dt, video))
            if key not in slot_datetimes:
                slot_datetimes[key] = slot_dt

        if not groups:
            LOGGER.debug("Будущих слотов не найдено.")
            return SlotLoadReport(
                jobs=[],
                total_rows=len(raw_rows),
                enriched_rows=len(rows),
                recognized_columns=["Links", "Date", "Time"],
                rows_by_language={},
            )

        # --- Сборка StitchJob из каждой группы ---
        jobs: List[StitchJob] = []
        for key, entries in groups.items():
            # Сортируем видео внутри слота по row_number (order = исходный номер строки)
            sorted_entries = sorted(entries, key=lambda e: e[1].order)
            # Переиндексируем order: 1, 2, 3...
            videos = tuple(
                SourceVideo(url=v.url, title=v.title, order=idx)
                for idx, (_, v) in enumerate(sorted_entries, start=1)
            )
            jobs.append(
                StitchJob(
                    slot_key=key,
                    videos=videos,
                    thumbnail_source=self._config.thumbnail.source,
                    output_dir=self._config.paths.output_dir,
                    temp_dir=self._config.paths.temp_dir,
                    render_profile="",
                )
            )

        # Сортируем слоты по дате/времени
        jobs.sort(key=lambda j: slot_datetimes[j.slot_key])
        LOGGER.debug("Найдено %d будущих слотов.", len(jobs))

        rows_by_language: dict[str, int] = {}
        for job in jobs:
            lang = job.slot_key.language
            rows_by_language[lang] = rows_by_language.get(lang, 0) + len(job.videos)

        return SlotLoadReport(
            jobs=jobs,
            total_rows=len(raw_rows),
            enriched_rows=len(rows),
            recognized_columns=["Links", "Date", "Time"],
            rows_by_language=rows_by_language,
        )

    def load_slot_by_key(self, key: str) -> Optional[StitchJob]:
        """Найти конкретный слот по строковому ключу вида 'DD-MM-YYYY_HH-MM_lang'.

        Вернуть None если слот не найден.
        """
        report = self.load_future_slots()
        for job in report.jobs:
            if str(job.slot_key) == key:
                return job
        LOGGER.warning("Слот с ключом %r не найден среди будущих слотов.", key)
        return None
