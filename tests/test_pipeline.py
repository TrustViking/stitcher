"""Тесты оркестратора StitchPipeline."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List
from unittest.mock import MagicMock, patch

from app.config.settings import (
    AudioConfig,
    EncodingConfig,
    GoogleConfig,
    OutputConfig,
    PathsConfig,
    RetentionConfig,
    StitcherConfig,
    ThumbnailConfig,
    ToolsConfig,
    VideoConfig,
    YtDlpConfig,
)
from app.models.domain import (
    DownloadedThumbnail,
    DownloadedVideo,
    NormalizedSegment,
    SlotKey,
    SourceVideo,
    StitchJob,
    WorkerProgress,
)
from app.worker.pipeline import StitchPipeline
from app.worker.progress import ProgressTracker


class RecordingTracker(ProgressTracker):
    """Трекер прогресса для тестов."""

    def __init__(self) -> None:
        self.items: List[WorkerProgress] = []

    def on_progress(self, progress: WorkerProgress) -> None:
        self.items.append(progress)


def _make_config(tmp_path: Path) -> StitcherConfig:
    temp_dir = tmp_path / "temp"
    output_dir = tmp_path / "output"
    logs_dir = tmp_path / "logs"
    state_dir = tmp_path / "state"

    gpu_profile = tmp_path / "gpu.txt"
    cpu_profile = tmp_path / "cpu.txt"
    ytdlp_video_profile = tmp_path / "ytdlp_video.txt"
    ytdlp_thumbnail_profile = tmp_path / "ytdlp_thumbnail.txt"
    gpu_profile.write_text("-c:v h264_nvenc\n", encoding="utf-8")
    cpu_profile.write_text("-c:v libx264\n", encoding="utf-8")
    ytdlp_video_profile.write_text(
        "-f bestvideo+bestaudio[ext=m4a]/bestvideo+bestaudio\n--merge-output-format mkv\n",
        encoding="utf-8",
    )
    ytdlp_thumbnail_profile.write_text(
        "--write-thumbnail\n--skip-download\n--convert-thumbnails jpg\n",
        encoding="utf-8",
    )

    return StitcherConfig(
        paths=PathsConfig(
            temp_dir=temp_dir,
            output_dir=output_dir,
            logs_dir=logs_dir,
            state_dir=state_dir,
        ),
        tools=ToolsConfig(ytdlp_path=tmp_path / "yt-dlp.exe", ffmpeg_path=tmp_path / "ffmpeg.exe"),
        ytdlp=YtDlpConfig(auto_update=True, update_check_interval_days=7),
        encoding=EncodingConfig(
            gpu_profile=gpu_profile,
            cpu_profile=cpu_profile,
            ytdlp_video_profile=ytdlp_video_profile,
            ytdlp_thumbnail_profile=ytdlp_thumbnail_profile,
            fallback_to_cpu=True,
        ),
        video=VideoConfig(width=1920, height=1080, fps=25),
        audio=AudioConfig(codec="aac", sample_rate=48000, bitrate="512k", channels="stereo"),
        thumbnail=ThumbnailConfig(duration_seconds=3, source="youtube", fade_duration_seconds=0),
        output=OutputConfig(filename_template="{date}_{time}_{lang}.mp4"),
        retention=RetentionConfig(cleanup_on_start=False, temp_max_age_days=3, logs_max_age_days=7),
        google=GoogleConfig(sheets_id=""),
    )


def _make_job() -> StitchJob:
    videos = (
        SourceVideo(url="https://youtu.be/1", title="V1", order=1),
        SourceVideo(url="https://youtu.be/2", title="V2", order=2),
    )
    return StitchJob(slot_key=SlotKey(date="23-03-2026", time="14-00", language="uk"), videos=videos)


def _configure_success_mocks(pipeline: StitchPipeline, tmp_path: Path) -> None:
    pipeline._video_downloader = MagicMock()
    pipeline._thumbnail_fetcher = MagicMock()
    pipeline._video_normalizer = MagicMock()
    pipeline._thumbnail_clip_builder = MagicMock()
    pipeline._final_concat = MagicMock()

    def download(video: SourceVideo, slot_temp_dir: Path) -> DownloadedVideo:
        return DownloadedVideo(source=video, file_path=slot_temp_dir / f"{video.order}_source.mkv")

    def fetch(video: SourceVideo, slot_temp_dir: Path) -> DownloadedThumbnail:
        return DownloadedThumbnail(source=video, file_path=slot_temp_dir / f"{video.order}_thumb.jpg")

    def normalize(downloaded: DownloadedVideo, slot_temp_dir: Path) -> NormalizedSegment:
        return NormalizedSegment(
            file_path=slot_temp_dir / f"{downloaded.source.order}_normalized.mp4",
            segment_type="video",
            order=downloaded.source.order,
        )

    def build_clip(thumbnail: DownloadedThumbnail, slot_temp_dir: Path) -> NormalizedSegment:
        return NormalizedSegment(
            file_path=slot_temp_dir / f"{thumbnail.source.order}_thumb_clip.mp4",
            segment_type="thumbnail_clip",
            order=thumbnail.source.order,
        )

    def concat(*, manifest_path: Path, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("ok", encoding="utf-8")
        return output_path

    pipeline._video_downloader.download.side_effect = download
    pipeline._thumbnail_fetcher.fetch.side_effect = fetch
    pipeline._video_normalizer.normalize.side_effect = normalize
    pipeline._thumbnail_clip_builder.build_clip.side_effect = build_clip
    pipeline._final_concat.concat.side_effect = concat


def test_pipeline_success_with_mocks(tmp_path: Path, monkeypatch) -> None:
    config = _make_config(tmp_path)
    tracker = RecordingTracker()
    pipeline = StitchPipeline(config, progress=tracker)
    _configure_success_mocks(pipeline, tmp_path)

    monkeypatch.setattr("app.worker.pipeline.build_output_filename", lambda *_: "result.mp4")

    result = pipeline.run(_make_job())

    assert result.success is True
    assert result.output_path == config.paths.output_dir / "result.mp4"
    assert result.output_path.exists()
    assert result.output_size_bytes > 0
    assert not (config.paths.temp_dir / "23-03-2026_14-00_uk").exists()


def test_pipeline_integrity_failure_on_download_error(tmp_path: Path, monkeypatch) -> None:
    config = _make_config(tmp_path)
    tracker = RecordingTracker()
    pipeline = StitchPipeline(config, progress=tracker)
    _configure_success_mocks(pipeline, tmp_path)

    monkeypatch.setattr("app.worker.pipeline.build_output_filename", lambda *_: "result.mp4")

    def failing_download(video: SourceVideo, slot_temp_dir: Path) -> DownloadedVideo:
        if video.order == 2:
            raise RuntimeError("download failed")
        return DownloadedVideo(source=video, file_path=slot_temp_dir / "1_source.mkv")

    pipeline._video_downloader.download.side_effect = failing_download

    result = pipeline.run(_make_job())

    assert result.success is False
    assert "download failed" in (result.error_message or "")
    assert (config.paths.temp_dir / "23-03-2026_14-00_uk").exists()
    pipeline._final_concat.concat.assert_not_called()


def test_pipeline_progress_callback_count(tmp_path: Path, monkeypatch) -> None:
    config = _make_config(tmp_path)
    tracker = RecordingTracker()
    pipeline = StitchPipeline(config, progress=tracker)
    _configure_success_mocks(pipeline, tmp_path)

    monkeypatch.setattr("app.worker.pipeline.build_output_filename", lambda *_: "result.mp4")

    result = pipeline.run(_make_job())

    assert result.success is True
    stages = [item.stage for item in tracker.items]
    assert stages == [
        "download",
        "download_done",
        "normalize",
        "normalize_done",
        "download",
        "download_done",
        "normalize",
        "normalize_done",
        "concat",
        "done",
    ]


def test_video_downloader_includes_ffmpeg_location(tmp_path: Path) -> None:
    from app.download.video_downloader import VideoDownloader
    from app.models.domain import SourceVideo

    ffmpeg = tmp_path / "bin" / "ffmpeg.exe"
    ytdlp = tmp_path / "bin" / "yt-dlp.exe"
    logger = logging.getLogger("test")

    downloader = VideoDownloader(
        ytdlp_path=ytdlp,
        ffmpeg_path=ffmpeg,
        ytdlp_args=["-f", "bestvideo+bestaudio"],
        logger=logger,
    )

    video = SourceVideo(url="https://youtu.be/test", title="T", order=1)
    slot_dir = tmp_path / "slot"
    slot_dir.mkdir()
    output_path = slot_dir / "1_source.mkv"
    output_path.write_text("ok")

    captured: list[list[str]] = []

    class FakeResult:
        returncode = 0

    def fake_run(cmd, **_):
        captured.append(cmd)
        return FakeResult()

    with patch("app.download.video_downloader.subprocess.run", side_effect=fake_run):
        downloader.download(video, slot_dir)

    assert len(captured) == 1
    cmd = captured[0]
    idx = cmd.index("--ffmpeg-location")
    assert cmd[idx + 1] == str(tmp_path / "bin")


def test_thumbnail_fetcher_includes_ffmpeg_location(tmp_path: Path) -> None:
    from app.download.thumbnail_fetcher import ThumbnailFetcher
    from app.models.domain import SourceVideo

    ffmpeg = tmp_path / "bin" / "ffmpeg.exe"
    ytdlp = tmp_path / "bin" / "yt-dlp.exe"
    logger = logging.getLogger("test")

    fetcher = ThumbnailFetcher(
        ytdlp_path=ytdlp,
        ffmpeg_path=ffmpeg,
        ytdlp_args=["--write-thumbnail", "--skip-download"],
        logger=logger,
    )

    video = SourceVideo(url="https://youtu.be/test", title="T", order=1)
    slot_dir = tmp_path / "slot"
    slot_dir.mkdir()
    (slot_dir / "1_thumb.jpg").write_text("img")

    captured: list[list[str]] = []

    class FakeResult:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(cmd, **_):
        captured.append(cmd)
        return FakeResult()

    with patch("app.download.thumbnail_fetcher.subprocess.run", side_effect=fake_run):
        fetcher.fetch(video, slot_dir)

    assert len(captured) == 1
    cmd = captured[0]
    idx = cmd.index("--ffmpeg-location")
    assert cmd[idx + 1] == str(tmp_path / "bin")
