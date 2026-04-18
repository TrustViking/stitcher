"""RowEnricher — обогащает сырые строки таблицы YouTube metadata."""
from __future__ import annotations

from typing import Dict, List

from app.ingest.language_detector import detect_language
from app.ingest.link_normalizer import normalize_youtube_link
from app.ingest.youtube_metadata import YouTubeMetadataFetcher
from app.models.domain import EnrichedRow, RawSheetRow, VideoMetadata
from app.runtime.logging_config import get_logger

LOGGER = get_logger(__name__)


class RowEnricher:
    """Обогащает RawSheetRow → EnrichedRow через yt-dlp metadata."""

    def __init__(self, *, metadata_fetcher: YouTubeMetadataFetcher) -> None:
        self._fetcher = metadata_fetcher
        self._metadata_cache: Dict[str, VideoMetadata] = {}

    def enrich(self, raw_rows: List[RawSheetRow]) -> List[EnrichedRow]:
        """Для каждой строки: normalize URL → fetch metadata → detect language.

        Строки с пустым link/date/time пропускаются.
        Строки с невалидным URL или ошибкой fetch пропускаются с логом.
        """
        enriched: List[EnrichedRow] = []
        for row in raw_rows:
            if not row.link:
                LOGGER.debug("row %d: пустой link, пропускаем.", row.row_number)
                continue
            if not row.date_raw or not row.time_raw:
                LOGGER.debug(
                    "row %d: пустые date/time (date=%r time=%r), пропускаем.",
                    row.row_number,
                    row.date_raw,
                    row.time_raw,
                )
                continue

            normalized = normalize_youtube_link(row.link)
            if not normalized:
                LOGGER.warning(
                    "row %d: не удалось извлечь YouTube video id из %r, пропускаем.",
                    row.row_number,
                    row.link,
                )
                continue

            try:
                metadata = self._metadata_cache.get(normalized)
                if metadata is None:
                    metadata = self._fetcher.fetch(normalized)
                    self._metadata_cache[normalized] = metadata
                    LOGGER.debug(
                        "row %d: metadata получен для %s (title=%r)",
                        row.row_number,
                        normalized,
                        metadata.title,
                    )
                else:
                    LOGGER.debug(
                        "row %d: metadata из кеша для %s",
                        row.row_number,
                        normalized,
                    )

                language = detect_language(metadata)
                LOGGER.debug(
                    "row %d: language=%s title=%r",
                    row.row_number,
                    language,
                    metadata.title,
                )

                enriched.append(
                    EnrichedRow(
                        row_number=row.row_number,
                        link=normalized,
                        original_link=row.link,
                        date_raw=row.date_raw,
                        time_raw=row.time_raw,
                        title=metadata.title,
                        language=language,
                        thumbnail_url=metadata.thumbnail_url,
                    )
                )
            except Exception as exc:
                LOGGER.warning(
                    "row %d: не удалось обогатить %r: %s — пропускаем.",
                    row.row_number,
                    row.link,
                    exc,
                )
                continue

        LOGGER.debug("Обогащено %d строк из %d сырых.", len(enriched), len(raw_rows))
        return enriched
