"""Скачивание видео через yt-dlp."""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from app.models.domain import DownloadedVideo, SourceVideo


class VideoDownloader:
    """Скачивание видео через yt-dlp."""

    def __init__(self, *, ytdlp_path: Path, ytdlp_args: list[str], logger: logging.Logger) -> None:
        self._ytdlp_path = ytdlp_path
        self._ytdlp_args = ytdlp_args
        self._logger = logger

    def download(self, video: SourceVideo, slot_temp_dir: Path) -> DownloadedVideo:
        """Скачать видео в slot_temp_dir и вернуть DownloadedVideo."""
        slot_temp_dir.mkdir(parents=True, exist_ok=True)
        output_path = slot_temp_dir / f"{video.order}_source.mkv"

        command = [
            str(self._ytdlp_path),
            *self._ytdlp_args,
            "-o",
            str(output_path),
            video.url,
        ]
        command_str = subprocess.list2cmdline(command)
        self._logger.debug(
            "yt-dlp download start: order=%d url=%s output=%s command=%s",
            video.order,
            video.url,
            output_path,
            command_str,
        )

        for attempt in (1, 2):
            result = self._run_command(command)
            if result.returncode == 0:
                if not output_path.exists():
                    raise RuntimeError(
                        f"yt-dlp завершился успешно, но файл не найден: {output_path}"
                    )
                return DownloadedVideo(source=video, file_path=output_path, duration_seconds=0.0)

            self._logger.error(
                "yt-dlp ошибка (attempt=%d, order=%d): %s",
                attempt,
                video.order,
                (result.stderr or "").strip(),
            )
            if attempt == 1:
                self._logger.warning(
                    "Повторная попытка скачивания видео order=%d.",
                    video.order,
                )

        raise RuntimeError(f"Не удалось скачать видео после retry: {video.url}")

    def _run_command(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        self._logger.debug("yt-dlp command: %s", " ".join(command))
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            self._logger.error("yt-dlp stdout: %s", (result.stdout or "").strip())
            self._logger.error("yt-dlp stderr: %s", (result.stderr or "").strip())
        return result
