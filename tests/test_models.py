"""Тесты создания доменных моделей."""
from __future__ import annotations

from pathlib import Path

from app.models.domain import (
    DownloadedThumbnail,
    DownloadedVideo,
    EnrichedRow,
    NormalizedSegment,
    RawSheetRow,
    RenderProfile,
    SlotKey,
    SourceVideo,
    StitchJob,
    VideoMetadata,
    WorkerProgress,
    WorkerResult,
)


def test_raw_sheet_row() -> None:
    row = RawSheetRow(
        row_number=2,
        link="https://youtu.be/X",
        date_raw="23.03.2026",
        time_raw="14:00",
    )
    assert row.row_number == 2
    assert row.link == "https://youtu.be/X"


def test_enriched_row() -> None:
    row = EnrichedRow(
        row_number=2,
        link="https://youtu.be/X",
        original_link="https://youtube.com/watch?v=X",
        date_raw="23.03.2026",
        time_raw="14:00",
        title="Тест",
        language="uk",
    )
    assert row.original_link.endswith("v=X")
    assert row.language == "uk"
    assert row.thumbnail_url == ""


def test_video_metadata() -> None:
    metadata = VideoMetadata(
        url="https://youtu.be/X",
        title="Title",
        description="Desc",
        thumbnail_url="https://i.ytimg.com/vi/X/hqdefault.jpg",
    )
    assert metadata.url == "https://youtu.be/X"
    assert metadata.audio_languages == ()


def test_source_video() -> None:
    video = SourceVideo(url="https://youtu.be/X", title="Video 1", order=1)
    assert video.order == 1


def test_slot_key_str() -> None:
    key = SlotKey(date="23-03-2026", time="14-00", language="uk")
    assert str(key) == "23-03-2026_14-00_uk"


def test_stitch_job() -> None:
    key = SlotKey(date="23-03-2026", time="14-00", language="uk")
    videos = [SourceVideo(url="https://youtu.be/X", title="V1", order=1)]
    job = StitchJob(slot_key=key, videos=videos)
    assert len(job.videos) == 1
    assert job.thumbnail_source == "youtube"


def test_downloaded_video() -> None:
    src = SourceVideo(url="u", title="t", order=1)
    downloaded = DownloadedVideo(source=src, file_path=Path("/tmp/v.mkv"), duration_seconds=120.5)
    assert downloaded.duration_seconds == 120.5


def test_downloaded_thumbnail() -> None:
    src = SourceVideo(url="u", title="t", order=1)
    thumbnail = DownloadedThumbnail(source=src, file_path=Path("/tmp/thumb.jpg"))
    assert thumbnail.file_path.name == "thumb.jpg"


def test_normalized_segment() -> None:
    segment = NormalizedSegment(file_path=Path("/tmp/1_normalized.mp4"), segment_type="video", order=1)
    assert segment.segment_type == "video"


def test_render_profile() -> None:
    profile = RenderProfile(name="gpu_nvenc", ffmpeg_args=["-c:v", "h264_nvenc"])
    assert profile.name == "gpu_nvenc"


def test_worker_progress() -> None:
    progress = WorkerProgress(stage="download", current_video=2, total_videos=5, message="ok")
    assert progress.stage == "download"


def test_worker_result_success() -> None:
    result = WorkerResult(
        success=True,
        output_path=Path("/out/video.mp4"),
        duration_seconds=45.2,
        output_size_bytes=123,
    )
    assert result.success is True
    assert result.error_message is None
    assert result.output_size_bytes == 123


def test_worker_result_failure() -> None:
    result = WorkerResult(success=False, error_message="download failed")
    assert result.output_path is None
    assert result.output_size_bytes == 0
