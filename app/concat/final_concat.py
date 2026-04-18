"""Финальная склейка сегментов в один MP4."""
from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path

from app.ffmpeg.command_builder import build_concat_command
from app.models.domain import SlotKey


class FinalConcat:
    """Финальная склейка всех сегментов в один MP4."""

    def __init__(self, *, ffmpeg_path: Path, logger: logging.Logger) -> None:
        self._ffmpeg_path = ffmpeg_path
        self._logger = logger

    def concat(
        self,
        *,
        manifest_path: Path,
        output_path: Path,
    ) -> Path:
        """Склеить сегменты из manifest в один файл."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        command = build_concat_command(
            manifest_path=manifest_path,
            output_path=output_path,
            ffmpeg_path=self._ffmpeg_path,
        )

        self._logger.debug(
            "Concat start: manifest=%s output=%s",
            manifest_path,
            output_path,
        )
        self._logger.debug("ffmpeg concat command: %s", " ".join(command))
        started = time.monotonic()
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        elapsed = time.monotonic() - started
        if result.stdout:
            self._logger.debug("ffmpeg concat stdout: %s", result.stdout.strip())
        if result.stderr:
            self._logger.debug("ffmpeg concat stderr: %s", result.stderr.strip())
        self._logger.debug("Concat finished: returncode=%d elapsed=%.2fs", result.returncode, elapsed)

        if result.returncode != 0:
            raise RuntimeError(f"Concat failed: {(result.stderr or '').strip()}")
        if not output_path.exists():
            raise RuntimeError(f"Выходной файл после concat не найден: {output_path}")

        return output_path


def build_output_filename(slot_key: SlotKey, template: str = "") -> str:
    """Сформировать имя выходного файла по шаблону из конфига."""
    if not template:
        template = "{date}_{time}_{lang}.mp4"
    return template.format(
        date=slot_key.date,
        time=slot_key.time,
        lang=slot_key.language.upper(),
    )


def resolve_output_path(output_dir: Path, filename: str) -> Path:
    """Return a collision-free path: if file exists, append _v2, _v3 ..."""
    candidate = output_dir / filename
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    counter = 2
    while True:
        candidate = output_dir / f"{stem}_v{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1
