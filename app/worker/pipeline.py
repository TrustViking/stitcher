"""Оркестратор полного пайплайна обработки одного слота."""
from __future__ import annotations

import shutil
import time
from pathlib import Path

from app.concat.final_concat import FinalConcat, build_output_filename, resolve_output_path
from app.concat.manifest_builder import build_manifest
from app.config.settings import StitcherConfig
from app.download.thumbnail_fetcher import ThumbnailFetcher
from app.download.video_downloader import VideoDownloader
from app.models.domain import StitchJob, WorkerProgress, WorkerResult
from app.runtime.logging_config import get_logger
from app.transcode.fade_clip import FadeClipBuilder
from app.transcode.thumbnail_clip import ThumbnailClipBuilder
from app.transcode.video_normalizer import VideoNormalizer
from app.worker.progress import NullProgressTracker, ProgressTracker


class StitchPipeline:
    """Оркестратор обработки одного StitchJob."""

    def __init__(self, config: StitcherConfig, *, progress: ProgressTracker | None = None) -> None:
        self._config = config
        self._progress = progress or NullProgressTracker()
        self._logger = get_logger(__name__)

        self._video_downloader = VideoDownloader(
            ytdlp_path=config.tools.ytdlp_path,
            logger=self._logger,
        )
        self._thumbnail_fetcher = ThumbnailFetcher(
            ytdlp_path=config.tools.ytdlp_path,
            logger=self._logger,
        )
        self._video_normalizer = VideoNormalizer(
            ffmpeg_path=config.tools.ffmpeg_path,
            gpu_profile_path=config.encoding.gpu_profile,
            cpu_profile_path=config.encoding.cpu_profile,
            fallback_to_cpu=config.encoding.fallback_to_cpu,
            logger=self._logger,
        )
        audio_channels = _audio_channels_to_int(config.audio.channels)
        self._thumbnail_clip_builder = ThumbnailClipBuilder(
            ffmpeg_path=config.tools.ffmpeg_path,
            gpu_profile_path=config.encoding.gpu_profile,
            cpu_profile_path=config.encoding.cpu_profile,
            fallback_to_cpu=config.encoding.fallback_to_cpu,
            duration_seconds=config.thumbnail.duration_seconds,
            width=config.video.width,
            height=config.video.height,
            audio_codec=config.audio.codec,
            audio_bitrate=config.audio.bitrate,
            audio_sample_rate=config.audio.sample_rate,
            audio_channels=audio_channels,
            logger=self._logger,
        )
        self._fade_clip_builder = FadeClipBuilder(
            ffmpeg_path=config.tools.ffmpeg_path,
            duration_seconds=config.thumbnail.fade_duration_seconds,
            width=config.video.width,
            height=config.video.height,
            audio_codec=config.audio.codec,
            audio_bitrate=config.audio.bitrate,
            audio_sample_rate=config.audio.sample_rate,
            audio_channels=audio_channels,
            logger=self._logger,
        )
        self._final_concat = FinalConcat(
            ffmpeg_path=config.tools.ffmpeg_path,
            logger=self._logger,
        )

    def run(self, job: StitchJob) -> WorkerResult:
        """Выполнить полный пайплайн для одного слота."""
        started = time.monotonic()
        total = len(job.videos)
        slot_temp_dir = self._config.paths.temp_dir / str(job.slot_key)
        current_index = 0

        self._config.paths.output_dir.mkdir(parents=True, exist_ok=True)
        slot_temp_dir.mkdir(parents=True, exist_ok=True)
        self._logger.debug(
            "Pipeline start: slot=%s total_videos=%d temp_dir=%s output_dir=%s",
            job.slot_key,
            total,
            slot_temp_dir,
            self._config.paths.output_dir,
        )

        segments = []
        try:
            for index, video in enumerate(job.videos, start=1):
                current_index = index
                self._logger.debug(
                    "Slot step start: slot=%s video_index=%d/%d title=%r url=%s",
                    job.slot_key,
                    index,
                    total,
                    video.title,
                    video.url,
                )

                self._notify("download", index, total, f"Скачивание: {video.url}")
                download_started = time.monotonic()
                downloaded = self._video_downloader.download(video, slot_temp_dir)
                download_duration = time.monotonic() - download_started
                downloaded_size = _safe_file_size(downloaded.file_path)
                self._logger.debug(
                    "Download done: slot=%s order=%d file=%s size_bytes=%d duration=%.2fs",
                    job.slot_key,
                    video.order,
                    downloaded.file_path,
                    downloaded_size,
                    download_duration,
                )
                self._notify(
                    "download_done",
                    index,
                    total,
                    f"Скачано ✓ ({_format_size(downloaded_size)}, {_format_mmss(download_duration)})",
                )

                thumbnail = self._thumbnail_fetcher.fetch(video, slot_temp_dir)
                self._logger.debug(
                    "Thumbnail fetched: slot=%s order=%d file=%s",
                    job.slot_key,
                    video.order,
                    thumbnail.file_path,
                )

                self._notify("normalize", index, total, f"Нормализация: {video.title}")
                normalize_started = time.monotonic()
                if self._config.thumbnail.fade_duration_seconds > 0:
                    fade_clip = self._fade_clip_builder.build_clip(video.order, slot_temp_dir)
                    segments.append(fade_clip)
                normalized = self._video_normalizer.normalize(downloaded, slot_temp_dir)
                thumb_clip = self._thumbnail_clip_builder.build_clip(thumbnail, slot_temp_dir)
                normalize_duration = time.monotonic() - normalize_started
                self._logger.debug(
                    "Normalize done: slot=%s order=%d normalized=%s thumb_clip=%s duration=%.2fs",
                    job.slot_key,
                    video.order,
                    normalized.file_path,
                    thumb_clip.file_path,
                    normalize_duration,
                )
                label = "GPU" if normalized.used_gpu else "CPU·fallback"
                self._notify(
                    "normalize_done",
                    index,
                    total,
                    f"Нормализовано ✓  ({label} · {_format_mmss(normalize_duration)})",
                    encoder=label,
                )
                segments.extend([thumb_clip, normalized])

            self._notify("concat", total, total, "Финальная склейка")
            manifest_path = build_manifest(segments, slot_temp_dir / "concat_manifest.txt")
            filename = build_output_filename(
                job.slot_key,
                self._config.output.filename_template,
            )
            output_path = resolve_output_path(self._config.paths.output_dir, filename)
            self._logger.debug(
                "Concat start: slot=%s manifest=%s output=%s",
                job.slot_key,
                manifest_path,
                output_path,
            )
            self._final_concat.concat(manifest_path=manifest_path, output_path=output_path)
            output_size = _safe_file_size(output_path)

            shutil.rmtree(slot_temp_dir, ignore_errors=True)
            duration = time.monotonic() - started
            self._logger.debug(
                "Pipeline success: slot=%s output=%s size_bytes=%d duration=%.2fs",
                job.slot_key,
                output_path,
                output_size,
                duration,
            )
            self._notify("done", total, total, f"Готово: {output_path}")
            return WorkerResult(
                success=True,
                output_path=output_path,
                duration_seconds=duration,
                output_size_bytes=output_size,
            )
        except Exception as exc:
            self._logger.error("Ошибка пайплайна слота %s: %s", job.slot_key, exc, exc_info=True)
            duration = time.monotonic() - started
            self._notify("error", current_index, total, str(exc))
            return WorkerResult(success=False, error_message=str(exc), duration_seconds=duration)

    def _notify(
        self,
        stage: str,
        current: int,
        total: int,
        message: str,
        *,
        encoder: str = "",
    ) -> None:
        self._progress.on_progress(
            WorkerProgress(
                stage=stage,
                current_video=current,
                total_videos=total,
                message=message,
                encoder=encoder,
            )
        )


def _audio_channels_to_int(value: str) -> int:
    """Преобразовать channels из конфига в число каналов ffmpeg."""
    normalized = value.strip().lower()
    if normalized == "mono":
        return 1
    if normalized == "stereo":
        return 2
    try:
        return max(1, int(normalized))
    except ValueError:
        return 2


def _safe_file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _format_mmss(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    minutes, sec = divmod(total, 60)
    return f"{minutes:02d}:{sec:02d}"


def _format_size(size_bytes: int) -> str:
    if size_bytes <= 0:
        return "0 B"
    size = float(size_bytes)
    units = ["B", "KB", "MB", "GB", "TB"]
    unit = units[0]
    for candidate in units:
        unit = candidate
        if size < 1024.0 or candidate == units[-1]:
            break
        size /= 1024.0
    if unit in {"B", "KB"}:
        return f"{int(size)} {unit}"
    return f"{size:.1f} {unit}"
