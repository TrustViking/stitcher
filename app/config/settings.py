"""Frozen dataclass модели конфигурации stitcher."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class PathsConfig:
    """Рабочие папки проекта."""

    temp_dir: Path
    output_dir: Path
    logs_dir: Path
    state_dir: Path


@dataclass(frozen=True)
class ToolsConfig:
    """Пути к внешним инструментам."""

    ytdlp_path: Path
    ffmpeg_path: Path


@dataclass(frozen=True)
class YtDlpConfig:
    auto_update: bool
    update_check_interval_days: int
    cookies_file: Optional[Path] = None
    deno_path: Optional[Path] = None
    cookies_warn_age_days: int = 7
    deno_auto_update: bool = True
    deno_update_interval_days: int = 7


@dataclass(frozen=True)
class EncodingConfig:
    """Профили кодирования ffmpeg и fallback-политика."""

    gpu_profile: Path
    cpu_profile: Path
    ytdlp_video_profile: Path
    ytdlp_thumbnail_profile: Path
    fallback_to_cpu: bool


@dataclass(frozen=True)
class VideoConfig:
    width: int
    height: int
    fps: int


@dataclass(frozen=True)
class AudioConfig:
    codec: str
    sample_rate: int
    bitrate: str
    channels: str


@dataclass(frozen=True)
class ThumbnailConfig:
    duration_seconds: int
    source: str
    fade_duration_seconds: int = 1


@dataclass(frozen=True)
class OutputConfig:
    filename_template: str


@dataclass(frozen=True)
class RetentionConfig:
    cleanup_on_start: bool
    temp_max_age_days: int
    logs_max_age_days: int


@dataclass(frozen=True)
class GoogleConfig:
    """Настройки интеграции с Google."""

    sheets_id: str


@dataclass(frozen=True)
class StitcherConfig:
    """Технические параметры из config.toml."""

    paths: PathsConfig
    tools: ToolsConfig
    ytdlp: YtDlpConfig
    encoding: EncodingConfig
    video: VideoConfig
    audio: AudioConfig
    thumbnail: ThumbnailConfig
    output: OutputConfig
    retention: RetentionConfig
    google: GoogleConfig


@dataclass(frozen=True)
class EnvConfig:
    """Пользовательские настройки из secrets/.env."""

    google_drive_folder_id: str
    telegram_bot_token: str
    telegram_chat_id: str
    telegram_admin_user_ids: tuple[int, ...]
    telegram_user_ids: tuple[int, ...]
