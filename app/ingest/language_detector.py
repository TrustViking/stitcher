"""Определение языка видео по metadata + langdetect fallback."""
from __future__ import annotations

import re
from typing import Optional

from langdetect import DetectorFactory, detect
from langdetect.lang_detect_exception import LangDetectException

from app.models.domain import VideoMetadata
from app.runtime.logging_config import get_logger

LOGGER = get_logger(__name__)
DetectorFactory.seed = 0

_LANGUAGE_ALIASES: dict[str, str] = {
    "ua": "uk",
    "uk": "uk",
    "ukr": "uk",
    "en": "en",
    "eng": "en",
    "ru": "ru",
    "rus": "ru",
}


def normalize_language(raw: Optional[str]) -> Optional[str]:
    """Нормализовать код языка к ISO 639-1 (uk/en/ru/...). None если мусор."""
    normalized = str(raw or "").strip().lower().replace("_", "-")
    if not normalized:
        return None
    if normalized in _LANGUAGE_ALIASES:
        return _LANGUAGE_ALIASES[normalized]
    match = re.fullmatch(r"([a-z]{2,3})(?:-[a-z]{2,3})?", normalized)
    if match:
        short = match.group(1)
        return _LANGUAGE_ALIASES.get(short, short)
    for prefix, canonical in (("uk", "uk"), ("ua", "uk"), ("en", "en"), ("ru", "ru")):
        if normalized.startswith(prefix):
            return canonical
    return None


def detect_language(metadata: VideoMetadata) -> str:
    """Определить язык видео по приоритету сигналов.

    Порядок:
        1. youtube_language (проставлен автором в YouTube)
        2. channel_language
        3. первый audio track language
        4. langdetect на title + description (если текста >= 20 символов)
        5. "unknown"
    """
    lang = normalize_language(metadata.youtube_language)
    if lang:
        LOGGER.debug("language=%s source=youtube_language", lang)
        return lang

    lang = normalize_language(metadata.channel_language)
    if lang:
        LOGGER.debug("language=%s source=channel_language", lang)
        return lang

    if metadata.audio_languages:
        lang = normalize_language(metadata.audio_languages[0])
        if lang:
            LOGGER.debug("language=%s source=audio_first", lang)
            return lang

    text = f"{metadata.title} {metadata.description}".strip()
    if len(text) >= 20:
        try:
            detected = detect(text)
            lang = normalize_language(detected)
            if lang:
                LOGGER.debug("language=%s source=langdetect", lang)
                return lang
        except LangDetectException:
            pass

    LOGGER.debug("language=unknown source=fallback")
    return "unknown"

