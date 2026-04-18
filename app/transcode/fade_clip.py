"""Generate a black-screen silent fade clip via ffmpeg."""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from app.models.domain import NormalizedSegment


class FadeClipBuilder:
    def __init__(
        self,
        *,
        ffmpeg_path: Path,
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
        self._duration = duration_seconds
        self._width = width
        self._height = height
        self._audio_codec = audio_codec
        self._audio_bitrate = audio_bitrate
        self._audio_sample_rate = audio_sample_rate
        self._audio_channels = audio_channels
        self._logger = logger

    def build_clip(self, order: int, slot_temp_dir: Path) -> NormalizedSegment:
        slot_temp_dir.mkdir(parents=True, exist_ok=True)
        output_path = slot_temp_dir / f"{order}_fade.mp4"
        channel_layout = "stereo" if self._audio_channels >= 2 else "mono"
        command = [
            str(self._ffmpeg_path),
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=black:s={self._width}x{self._height}:r=25:d={self._duration}",
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=channel_layout={channel_layout}:sample_rate={self._audio_sample_rate}",
            "-t",
            str(self._duration),
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-b:v",
            "500k",
            "-c:a",
            self._audio_codec,
            "-b:a",
            self._audio_bitrate,
            "-ar",
            str(self._audio_sample_rate),
            "-ac",
            str(self._audio_channels),
            "-shortest",
            str(output_path),
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        self._logger.debug("Fade clip: returncode=%d", result.returncode)
        if result.returncode != 0:
            raise RuntimeError(f"Fade clip failed: {result.stderr.strip()}")
        return NormalizedSegment(
            file_path=output_path,
            segment_type="fade_out",
            order=order,
            used_gpu=False,
        )
