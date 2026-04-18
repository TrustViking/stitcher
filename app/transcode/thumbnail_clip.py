"""Создание 3-секундного превью-клипа из изображения."""
from __future__ import annotations

import logging
from pathlib import Path

from app.ffmpeg.codec_fallback import run_with_fallback
from app.ffmpeg.command_builder import build_thumbnail_clip_command, load_profile
from app.models.domain import DownloadedThumbnail, NormalizedSegment


class ThumbnailClipBuilder:
    """Создание 3-секундного превью-клипа из изображения."""

    def __init__(
        self,
        *,
        ffmpeg_path: Path,
        gpu_profile_path: Path,
        cpu_profile_path: Path,
        fallback_to_cpu: bool,
        duration_seconds: int,
        width: int,
        height: int,
        audio_codec: str,
        audio_bitrate: str,
        audio_sample_rate: int,
        audio_channels: int,
        logger: logging.Logger,
    ) -> None:
        self._ffmpeg_path = ffmpeg_path
        self._gpu_profile_args = load_profile(gpu_profile_path)
        self._cpu_profile_args = load_profile(cpu_profile_path)
        self._fallback_to_cpu = fallback_to_cpu
        self._duration_seconds = duration_seconds
        self._width = width
        self._height = height
        self._audio_codec = audio_codec
        self._audio_bitrate = audio_bitrate
        self._audio_sample_rate = audio_sample_rate
        self._audio_channels = audio_channels
        self._logger = logger

    def build_clip(self, thumbnail: DownloadedThumbnail, slot_temp_dir: Path) -> NormalizedSegment:
        """Создать превью-клип и вернуть NormalizedSegment."""
        slot_temp_dir.mkdir(parents=True, exist_ok=True)
        output_path = slot_temp_dir / f"{thumbnail.source.order}_thumb_clip.mp4"

        gpu_command = build_thumbnail_clip_command(
            thumbnail_path=thumbnail.file_path,
            output_path=output_path,
            duration_seconds=self._duration_seconds,
            width=self._width,
            height=self._height,
            profile_args=self._gpu_profile_args,
            ffmpeg_path=self._ffmpeg_path,
            audio_codec=self._audio_codec,
            audio_bitrate=self._audio_bitrate,
            audio_sample_rate=self._audio_sample_rate,
            audio_channels=self._audio_channels,
        )
        cpu_command = build_thumbnail_clip_command(
            thumbnail_path=thumbnail.file_path,
            output_path=output_path,
            duration_seconds=self._duration_seconds,
            width=self._width,
            height=self._height,
            profile_args=self._cpu_profile_args,
            ffmpeg_path=self._ffmpeg_path,
            audio_codec=self._audio_codec,
            audio_bitrate=self._audio_bitrate,
            audio_sample_rate=self._audio_sample_rate,
            audio_channels=self._audio_channels,
        )

        encode_result = run_with_fallback(
            gpu_command=gpu_command,
            cpu_command=cpu_command,
            fallback_enabled=self._fallback_to_cpu,
            logger=self._logger,
        )

        if not output_path.exists():
            raise RuntimeError(f"Thumbnail clip не создан: {output_path}")

        return NormalizedSegment(
            file_path=output_path,
            segment_type="thumbnail_clip",
            order=thumbnail.source.order,
            used_gpu=encode_result.used_gpu,
        )
