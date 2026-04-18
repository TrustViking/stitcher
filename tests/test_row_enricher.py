"""Тесты RowEnricher — обогащение сырых строк YouTube metadata."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.ingest.youtube_metadata import YouTubeMetadataFetcher
from app.input.row_enricher import RowEnricher
from app.models.domain import EnrichedRow, RawSheetRow, VideoMetadata


def _make_metadata(
    *, url: str, title: str = "Test Title", youtube_language: str | None = "uk"
) -> VideoMetadata:
    return VideoMetadata(
        url=url,
        title=title,
        description="Some description",
        thumbnail_url="https://i.ytimg.com/vi/abc/hqdefault.jpg",
        youtube_language=youtube_language,
    )


def test_enrich_single_row() -> None:
    mock_fetcher = MagicMock(spec=YouTubeMetadataFetcher)
    mock_fetcher.fetch.return_value = _make_metadata(url="https://youtu.be/abc12345678")

    enricher = RowEnricher(metadata_fetcher=mock_fetcher)
    raw = [
        RawSheetRow(
            row_number=2,
            link="https://youtube.com/watch?v=abc12345678",
            date_raw="15.04.2026",
            time_raw="12:00",
        )
    ]

    result = enricher.enrich(raw)

    assert len(result) == 1
    row = result[0]
    assert isinstance(row, EnrichedRow)
    assert row.link == "https://youtu.be/abc12345678"
    assert row.original_link == "https://youtube.com/watch?v=abc12345678"
    assert row.title == "Test Title"
    assert row.language == "uk"


def test_enrich_skips_empty_link() -> None:
    mock_fetcher = MagicMock(spec=YouTubeMetadataFetcher)
    enricher = RowEnricher(metadata_fetcher=mock_fetcher)

    result = enricher.enrich(
        [RawSheetRow(row_number=2, link="", date_raw="15.04.2026", time_raw="12:00")]
    )

    assert result == []
    mock_fetcher.fetch.assert_not_called()


def test_enrich_skips_invalid_url() -> None:
    mock_fetcher = MagicMock(spec=YouTubeMetadataFetcher)
    enricher = RowEnricher(metadata_fetcher=mock_fetcher)

    result = enricher.enrich(
        [RawSheetRow(row_number=2, link="not a url", date_raw="15.04.2026", time_raw="12:00")]
    )

    assert result == []
    mock_fetcher.fetch.assert_not_called()


def test_enrich_caches_metadata_by_normalized_url() -> None:
    """Две строки с разным форматом одного и того же URL → один fetch."""
    mock_fetcher = MagicMock(spec=YouTubeMetadataFetcher)
    mock_fetcher.fetch.return_value = _make_metadata(url="https://youtu.be/abc12345678")

    enricher = RowEnricher(metadata_fetcher=mock_fetcher)
    raw = [
        RawSheetRow(
            row_number=2,
            link="https://youtu.be/abc12345678",
            date_raw="15.04.2026",
            time_raw="12:00",
        ),
        RawSheetRow(
            row_number=3,
            link="https://youtube.com/watch?v=abc12345678",
            date_raw="16.04.2026",
            time_raw="13:00",
        ),
    ]

    result = enricher.enrich(raw)

    assert len(result) == 2
    assert mock_fetcher.fetch.call_count == 1


def test_enrich_skips_row_when_fetch_fails() -> None:
    mock_fetcher = MagicMock(spec=YouTubeMetadataFetcher)
    mock_fetcher.fetch.side_effect = RuntimeError("network error")

    enricher = RowEnricher(metadata_fetcher=mock_fetcher)
    result = enricher.enrich(
        [
            RawSheetRow(
                row_number=2,
                link="https://youtu.be/abc12345678",
                date_raw="15.04.2026",
                time_raw="12:00",
            )
        ]
    )

    assert result == []

