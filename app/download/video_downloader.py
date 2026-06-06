"""Скачивание видео через yt-dlp."""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Optional

from app.models.domain import DownloadedVideo, SourceVideo


class TemporaryDownloadError(RuntimeError):
    """Временная сетевая ошибка при скачивании. Слот можно повторить позже."""


class VideoDownloader:
    """Скачивание видео через yt-dlp."""

    def __init__(
        self,
        *,
        ytdlp_path: Path,
        ffmpeg_path: Path,
        ytdlp_args: list[str],
        logger: logging.Logger,
        cookies_file: Optional[Path] = None,
        deno_path: Optional[Path] = None,
    ) -> None:
        self._ytdlp_path = ytdlp_path
        self._ffmpeg_path = ffmpeg_path
        self._ytdlp_args = ytdlp_args
        self._logger = logger
        self._cookies_file = cookies_file
        self._deno_path = deno_path

    _NETWORK_TIMEOUT_PATTERNS = (
        "timed out",
        "read timed out",
        "connection timed out",
        "giving up after",
        "unable to connect",
        "network unreachable",
    )

    def _is_network_timeout(self, stderr: str) -> bool:
        """Вернуть True, если stderr содержит признаки временной сетевой ошибки."""
        lower = stderr.lower()
        return any(pattern in lower for pattern in self._NETWORK_TIMEOUT_PATTERNS)

    def download(self, video: SourceVideo, slot_temp_dir: Path) -> DownloadedVideo:
        """Скачать видео в slot_temp_dir и вернуть DownloadedVideo."""
        slot_temp_dir.mkdir(parents=True, exist_ok=True)
        output_path = slot_temp_dir / f"{video.order}_source.mkv"

        command = [
            str(self._ytdlp_path),
            "--ffmpeg-location",
            str(self._ffmpeg_path.parent),
            *self._ytdlp_args,
        ]

        if self._cookies_file and self._cookies_file.exists():
            command += ["--cookies", str(self._cookies_file)]

        if self._deno_path and self._deno_path.exists():
            command += ["--js-runtimes", f"deno:{self._deno_path}"]

        command += ["-o", str(output_path), video.url]
        command_str = subprocess.list2cmdline(command)
        self._logger.debug(
            "yt-dlp download start: order=%d url=%s output=%s command=%s",
            video.order,
            video.url,
            output_path,
            command_str,
        )

        last_stderr = ""
        network_failure_seen = False

        for attempt in (1, 2):
            result = self._run_command(command)
            if result.returncode == 0:
                if not output_path.exists():
                    raise RuntimeError(
                        f"yt-dlp завершился успешно, но файл не найден: {output_path}"
                    )
                return DownloadedVideo(source=video, file_path=output_path, duration_seconds=0.0)

            last_stderr = result.stderr or ""
            if self._is_network_timeout(last_stderr):
                network_failure_seen = True

            if attempt == 1:
                self._logger.warning(
                    "Повторная попытка скачивания (attempt=2, order=%d, url=%s)",
                    video.order,
                    video.url,
                )

        if network_failure_seen:
            stderr_lines = [l.strip() for l in last_stderr.splitlines() if l.strip()]
            error_hint = stderr_lines[-1] if stderr_lines else "no stderr"
            raise TemporaryDownloadError(
                f"[temporary-network] Сетевая ошибка при скачивании: {video.url} — {error_hint}"
            )
        raise RuntimeError(f"Не удалось скачать видео после retry: {video.url}")

    def _run_command(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        self._logger.debug("yt-dlp command: %s", " ".join(command))
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            self._logger.debug("yt-dlp stdout:\n%s", (result.stdout or "").strip())
            self._logger.debug("yt-dlp stderr:\n%s", (result.stderr or "").strip())
            stderr_lines = [l for l in (result.stderr or "").splitlines() if l.strip()]
            error_line = next(
                (l for l in stderr_lines if "ERROR:" in l),
                stderr_lines[-1] if stderr_lines else "(no stderr output)",
            )
            self._logger.warning(
                "yt-dlp завершился с ошибкой (rc=%d): %s — подробности в лог-файле",
                result.returncode,
                error_line.strip(),
            )
        return result
