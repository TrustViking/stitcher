"""Тесты language detector — приоритет сигналов."""
from __future__ import annotations

from app.ingest.language_detector import detect_language, normalize_language
from app.models.domain import VideoMetadata


def _md(**kwargs) -> VideoMetadata:
    defaults = dict(
        url="https://youtu.be/abc",
        title="",
        description="",
        thumbnail_url="",
    )
    defaults.update(kwargs)
    return VideoMetadata(**defaults)


def test_normalize_language_aliases() -> None:
    assert normalize_language("ua") == "uk"
    assert normalize_language("UKR") == "uk"
    assert normalize_language("en-US") == "en"
    assert normalize_language("") is None
    assert normalize_language(None) is None
    assert normalize_language("garbage") is None


def test_youtube_language_wins() -> None:
    metadata = _md(youtube_language="uk", channel_language="en")
    assert detect_language(metadata) == "uk"


def test_channel_language_when_no_youtube() -> None:
    metadata = _md(youtube_language=None, channel_language="en")
    assert detect_language(metadata) == "en"


def test_audio_language_when_no_metadata() -> None:
    metadata = _md(audio_languages=("ru",))
    assert detect_language(metadata) == "ru"


def test_langdetect_fallback() -> None:
    metadata = _md(
        title="Привет мир",
        description="Это большой текст на русском языке для определения через langdetect.",
    )
    result = detect_language(metadata)
    assert result == "ru"


def test_unknown_when_nothing() -> None:
    metadata = _md(title="x", description="")
    assert detect_language(metadata) == "unknown"

