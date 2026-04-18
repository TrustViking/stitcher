"""Получение YouTube metadata через локальный yt-dlp.exe бинарник."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from app.models.domain import VideoMetadata
from app.runtime.logging_config import get_logger

LOGGER = get_logger(__name__)


class YouTubeMetadataFetcher:
    """Абстрактный fetcher — для возможности мокать в тестах."""

    def fetch(self, video_url: str) -> VideoMetadata:
        raise NotImplementedError


class YtDlpBinaryMetadataFetcher(YouTubeMetadataFetcher):
    """Fetcher через локальный бинарник yt-dlp.exe."""

    def __init__(self, ytdlp_path: Path, timeout_seconds: float = 30.0) -> None:
        self._ytdlp_path = ytdlp_path
        self._timeout_seconds = timeout_seconds

    def fetch(self, video_url: str) -> VideoMetadata:
        command = [
            str(self._ytdlp_path),
            "--dump-single-json",
            "--no-warnings",
            "--skip-download",
            "--no-playlist",
            video_url,
        ]
        LOGGER.debug("yt-dlp metadata command: %s", " ".join(command))

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=self._timeout_seconds,
            encoding="utf-8",
            errors="replace",
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"yt-dlp не смог получить metadata для {video_url}. "
                f"stderr: {(result.stderr or '').strip()}"
            )

        try:
            info: Dict[str, Any] = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"yt-dlp вернул невалидный JSON для {video_url}: {exc}"
            ) from exc

        return self._build_metadata(video_url=video_url, info=info)

    def _build_metadata(self, *, video_url: str, info: Dict[str, Any]) -> VideoMetadata:
        title: str = str(info.get("title") or "").strip()
        description: str = str(info.get("description") or "").strip()
        thumbnail_url: str = str(info.get("thumbnail") or "").strip()
        video_id: str = str(info.get("id") or "").strip()
        youtube_language: Optional[str] = str(info.get("language") or "").strip() or None
        channel_language: Optional[str] = str(info.get("channel_language") or "").strip() or None

        duration_value = info.get("duration")
        duration_seconds: Optional[int] = None
        if isinstance(duration_value, (int, float)) and duration_value > 0:
            duration_seconds = int(duration_value)

        formats_list = info.get("formats") or []
        audio_langs: list[str] = []
        for fmt in formats_list:
            acodec = str(fmt.get("acodec") or "").strip()
            fmt_lang = str(fmt.get("language") or "").strip()
            if acodec and acodec != "none" and fmt_lang and fmt_lang not in audio_langs:
                audio_langs.append(fmt_lang)

        subtitle_langs = tuple((info.get("subtitles") or {}).keys())
        auto_caption_langs = tuple((info.get("automatic_captions") or {}).keys())

        if not title:
            raise ValueError(f"yt-dlp вернул пустой title для {video_url}")

        if not thumbnail_url and re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
            thumbnail_url = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
            LOGGER.warning("yt-dlp вернул пустой thumbnail_url; fallback: %s", thumbnail_url)

        LOGGER.debug(
            "metadata fetched: url=%s title=%r youtube_language=%s "
            "channel_language=%s audio_languages=%s",
            video_url,
            title,
            youtube_language,
            channel_language,
            audio_langs,
        )

        return VideoMetadata(
            url=video_url,
            title=title,
            description=description,
            thumbnail_url=thumbnail_url,
            youtube_language=youtube_language,
            channel_language=channel_language,
            duration_seconds=duration_seconds,
            audio_languages=tuple(audio_langs),
            subtitle_languages=subtitle_langs,
            auto_caption_languages=auto_caption_langs,
        )

