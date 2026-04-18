"""Получение превью видео через yt-dlp."""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from app.models.domain import DownloadedThumbnail, SourceVideo


class ThumbnailFetcher:
    """Получение превью видео через yt-dlp."""

    def __init__(self, *, ytdlp_path: Path, ytdlp_args: list[str], logger: logging.Logger) -> None:
        self._ytdlp_path = ytdlp_path
        self._ytdlp_args = ytdlp_args
        self._logger = logger

    def fetch(self, video: SourceVideo, slot_temp_dir: Path) -> DownloadedThumbnail:
        """Скачать thumbnail видео в slot_temp_dir."""
        slot_temp_dir.mkdir(parents=True, exist_ok=True)
        output_stem = slot_temp_dir / f"{video.order}_thumb"

        command = [
            str(self._ytdlp_path),
            *self._ytdlp_args,
            "-o",
            str(output_stem),
            video.url,
        ]

        self._logger.debug("yt-dlp thumbnail command: %s", " ".join(command))
        result = subprocess.run(command, capture_output=True, text=True, check=False)

        if result.returncode != 0:
            self._logger.error("yt-dlp thumbnail stdout: %s", (result.stdout or "").strip())
            self._logger.error("yt-dlp thumbnail stderr: %s", (result.stderr or "").strip())
            self._logger.error(
                "Ошибка скачивания thumbnail order=%d: %s",
                video.order,
                (result.stderr or "").strip(),
            )
            raise RuntimeError(f"Не удалось скачать thumbnail для {video.url}")

        thumb_candidates = sorted(slot_temp_dir.glob(f"{video.order}_thumb.*"))
        if not thumb_candidates:
            raise RuntimeError(
                f"Thumbnail не найден после yt-dlp: {video.order}_thumb.*"
            )

        preferred_jpg = [path for path in thumb_candidates if path.suffix.lower() == ".jpg"]
        thumb_path = preferred_jpg[0] if preferred_jpg else thumb_candidates[0]
        return DownloadedThumbnail(source=video, file_path=thumb_path)
