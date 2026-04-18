"""Доменные модели stitcher — плоские frozen dataclasses."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class VideoMetadata:
    """Метаданные YouTube-видео, полученные через yt-dlp."""

    url: str
    title: str
    description: str
    thumbnail_url: str
    youtube_language: str | None = None
    channel_language: str | None = None
    duration_seconds: int | None = None
    audio_languages: tuple[str, ...] = ()
    subtitle_languages: tuple[str, ...] = ()
    auto_caption_languages: tuple[str, ...] = ()


@dataclass(frozen=True)
class RawSheetRow:
    """Сырая строка из Google Sheet — только link/date/time."""

    row_number: int
    link: str
    date_raw: str
    time_raw: str


@dataclass(frozen=True)
class EnrichedRow:
    """Строка после обогащения YouTube metadata."""

    row_number: int
    link: str
    original_link: str
    date_raw: str
    time_raw: str
    title: str
    language: str
    thumbnail_url: str = ""


@dataclass(frozen=True)
class SourceVideo:
    """Одно видео внутри слота."""

    url: str
    title: str
    order: int


@dataclass(frozen=True)
class SlotKey:
    """Уникальный ключ слота: дата + время + язык."""

    date: str      # DD-MM-YYYY
    time: str      # HH-MM
    language: str  # "uk", "en", "ru"

    def __str__(self) -> str:
        return f"{self.date}_{self.time}_{self.language}"


@dataclass(frozen=True)
class StitchJob:
    """Задание на склейку одного слота."""

    slot_key: SlotKey
    videos: tuple[SourceVideo, ...]
    thumbnail_source: str = "youtube"
    output_dir: Path = field(default_factory=lambda: Path("./output"))
    temp_dir: Path = field(default_factory=lambda: Path("./temp"))
    render_profile: str = ""


@dataclass(frozen=True)
class DownloadedVideo:
    """Скачанный файл видео."""

    source: SourceVideo
    file_path: Path
    duration_seconds: float = 0.0


@dataclass(frozen=True)
class DownloadedThumbnail:
    """Скачанное превью."""

    source: SourceVideo
    file_path: Path


@dataclass(frozen=True)
class NormalizedSegment:
    """Нормализованный сегмент пайплайна."""

    file_path: Path
    segment_type: str  # "video" | "thumbnail_clip" | "fade_out"
    order: int
    used_gpu: bool = True


@dataclass(frozen=True)
class RenderProfile:
    """Профиль кодирования ffmpeg."""

    name: str                               # "gpu_nvenc" | "cpu_libx264"
    ffmpeg_args: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class WorkerProgress:
    """Прогресс обработки слота."""

    stage: str
    current_video: int
    total_videos: int
    message: str = ""
    encoder: str = ""


@dataclass(frozen=True)
class WorkerResult:
    """Результат обработки слота."""

    success: bool
    output_path: Path | None = None
    error_message: str | None = None
    duration_seconds: float = 0.0
    output_size_bytes: int = 0
