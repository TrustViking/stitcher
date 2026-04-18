"""Тесты SlotLoader — группировка строк Google Sheet в слоты."""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import List
from unittest.mock import MagicMock
from datetime import timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pytest

from app.config.settings import (
    AudioConfig,
    EncodingConfig,
    OutputConfig,
    PathsConfig,
    RetentionConfig,
    StitcherConfig,
    ThumbnailConfig,
    ToolsConfig,
    VideoConfig,
    YtDlpConfig,
)
from app.input.sheet_reader import SlotLoader
from app.models.domain import EnrichedRow

try:
    _KYIV = ZoneInfo("Europe/Kyiv")
except ZoneInfoNotFoundError:
    _KYIV = timezone.utc


def _make_config() -> StitcherConfig:
    """Создать минимальный StitcherConfig для тестов."""
    return StitcherConfig(
        paths=PathsConfig(
            temp_dir=Path("/tmp/stitcher_test/temp"),
            output_dir=Path("/tmp/stitcher_test/output"),
            logs_dir=Path("/tmp/stitcher_test/logs"),
            state_dir=Path("/tmp/stitcher_test/state"),
        ),
        tools=ToolsConfig(ytdlp_path=Path("yt-dlp"), ffmpeg_path=Path("ffmpeg")),
        ytdlp=YtDlpConfig(auto_update=True, update_check_interval_days=7),
        encoding=EncodingConfig(
            gpu_profile=Path("gpu.txt"),
            cpu_profile=Path("cpu.txt"),
            ytdlp_video_profile=Path("ytdlp_video.txt"),
            ytdlp_thumbnail_profile=Path("ytdlp_thumbnail.txt"),
            fallback_to_cpu=True,
        ),
        video=VideoConfig(width=1920, height=1080, fps=25),
        audio=AudioConfig(codec="aac", sample_rate=48000, bitrate="512k", channels="stereo"),
        thumbnail=ThumbnailConfig(duration_seconds=3, source="youtube"),
        output=OutputConfig(filename_template="{date}_{time}_{lang}.mp4"),
        retention=RetentionConfig(cleanup_on_start=False, temp_max_age_days=3, logs_max_age_days=7),
    )


def _future_date(days_ahead: int = 5) -> datetime:
    """Вернуть дату в будущем."""
    return datetime.now(_KYIV) + timedelta(days=days_ahead)


def _past_date(days_ago: int = 5) -> datetime:
    """Вернуть дату в прошлом."""
    return datetime.now(_KYIV) - timedelta(days=days_ago)


def _make_rows(
    dt: datetime,
    language: str,
    count: int,
    *,
    start_row: int = 2,
) -> List[EnrichedRow]:
    """Создать count строк с одинаковой датой/временем/языком."""
    date_str = dt.strftime("%d.%m.%Y")
    time_str = dt.strftime("%H:%M")
    return [
        EnrichedRow(
            row_number=start_row + i,
            link=f"https://youtu.be/vid{i + 1}",
            original_link=f"https://youtu.be/vid{i + 1}",
            date_raw=date_str,
            time_raw=time_str,
            title=f"Video {i + 1}",
            language=language,
        )
        for i in range(count)
    ]


def _make_loader(rows: List[EnrichedRow]) -> SlotLoader:
    mock_client = MagicMock()
    mock_client.read_rows.return_value = []
    mock_enricher = MagicMock()
    mock_enricher.enrich.return_value = rows
    return SlotLoader(
        mock_client,
        mock_enricher,
        config=_make_config(),
        sheets_id="test_id",
    )


def test_group_same_slot() -> None:
    """6 строк с одинаковым date+time+language -> 1 слот с 6 видео."""
    future = _future_date()
    rows = _make_rows(future, "uk", 6)

    loader = _make_loader(rows)
    report = loader.load_future_slots()
    jobs = report.jobs

    assert len(jobs) == 1
    assert len(jobs[0].videos) == 6
    assert jobs[0].slot_key.language == "uk"


def test_filter_past_slots() -> None:
    """Прошлые слоты отфильтровываются."""
    past = _past_date()
    future = _future_date()
    rows = _make_rows(past, "uk", 3) + _make_rows(future, "en", 2, start_row=10)

    loader = _make_loader(rows)
    report = loader.load_future_slots()
    jobs = report.jobs

    assert len(jobs) == 1
    assert jobs[0].slot_key.language == "en"


def test_filter_empty_links() -> None:
    """Строки с пустыми ссылками пропускаются."""
    future = _future_date()
    rows = _make_rows(future, "uk", 3)
    loader = _make_loader(rows)
    report = loader.load_future_slots()
    jobs = report.jobs

    assert len(jobs) == 1
    assert len(jobs[0].videos) == 3


def test_sort_slots_by_date() -> None:
    """Слоты сортируются по дате/времени."""
    later = _future_date(10)
    sooner = _future_date(2)

    rows = _make_rows(later, "uk", 2) + _make_rows(sooner, "en", 2, start_row=10)

    loader = _make_loader(rows)
    report = loader.load_future_slots()
    jobs = report.jobs

    assert len(jobs) == 2
    assert jobs[0].slot_key.language == "en"
    assert jobs[1].slot_key.language == "uk"


def test_video_order_preserved() -> None:
    """Порядок видео внутри слота соответствует порядку строк."""
    future = _future_date()
    rows = _make_rows(future, "uk", 4)

    loader = _make_loader(rows)
    report = loader.load_future_slots()
    jobs = report.jobs

    orders = [video.order for video in jobs[0].videos]
    assert orders == [1, 2, 3, 4]


def test_load_slot_by_key() -> None:
    """load_slot_by_key возвращает конкретный слот."""
    future = _future_date()
    rows = _make_rows(future, "uk", 2)

    loader = _make_loader(rows)
    report = loader.load_future_slots()
    jobs = report.jobs
    key_str = str(jobs[0].slot_key)

    found = loader.load_slot_by_key(key_str)
    assert found is not None
    assert str(found.slot_key) == key_str


def test_load_slot_by_key_not_found() -> None:
    """load_slot_by_key возвращает None для несуществующего ключа."""
    loader = _make_loader([])
    assert loader.load_slot_by_key("99-99-9999_99-99_xx") is None


def test_empty_sheets_id_raises() -> None:
    """Пустой sheets_id вызывает RuntimeError."""
    mock_client = MagicMock()
    mock_client.read_rows.return_value = []
    mock_enricher = MagicMock()
    mock_enricher.enrich.return_value = []
    loader = SlotLoader(mock_client, mock_enricher, config=_make_config(), sheets_id="")
    with pytest.raises(RuntimeError, match="GOOGLE_SHEETS_ID"):
        loader.load_future_slots()
