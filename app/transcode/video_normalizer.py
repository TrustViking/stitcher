"""Нормализация видео через ffmpeg."""
from __future__ import annotations

import logging
from pathlib import Path

from app.ffmpeg.codec_fallback import run_with_fallback
from app.ffmpeg.command_builder import build_normalize_command, load_profile
from app.models.domain import DownloadedVideo, NormalizedSegment


class VideoNormalizer:
    """Нормализация видео через ffmpeg."""

    def __init__(
        self,
        *,
        ffmpeg_path: Path,
        gpu_profile_path: Path,
        cpu_profile_path: Path,
        fallback_to_cpu: bool,
        logger: logging.Logger,
    ) -> None:
        self._ffmpeg_path = ffmpeg_path
        self._gpu_profile_args = load_profile(gpu_profile_path)
        self._cpu_profile_args = load_profile(cpu_profile_path)
        self._fallback_to_cpu = fallback_to_cpu
        self._logger = logger

    def normalize(self, downloaded: DownloadedVideo, slot_temp_dir: Path) -> NormalizedSegment:
        """Нормализовать видео и вернуть NormalizedSegment."""
        slot_temp_dir.mkdir(parents=True, exist_ok=True)
        output_path = slot_temp_dir / f"{downloaded.source.order}_normalized.mp4"

        gpu_command = build_normalize_command(
            input_path=downloaded.file_path,
            output_path=output_path,
            profile_args=self._gpu_profile_args,
            ffmpeg_path=self._ffmpeg_path,
        )
        cpu_command = build_normalize_command(
            input_path=downloaded.file_path,
            output_path=output_path,
            profile_args=self._cpu_profile_args,
            ffmpeg_path=self._ffmpeg_path,
        )
        self._logger.debug(
            "Normalize prepare: order=%d input=%s output=%s gpu_cmd=%s cpu_cmd=%s",
            downloaded.source.order,
            downloaded.file_path,
            output_path,
            " ".join(gpu_command),
            " ".join(cpu_command),
        )

        encode_result = run_with_fallback(
            gpu_command=gpu_command,
            cpu_command=cpu_command,
            fallback_enabled=self._fallback_to_cpu,
            logger=self._logger,
        )

        if not output_path.exists():
            raise RuntimeError(f"Нормализованный файл не создан: {output_path}")

        return NormalizedSegment(
            file_path=output_path,
            segment_type="video",
            order=downloaded.source.order,
            used_gpu=encode_result.used_gpu,
        )
