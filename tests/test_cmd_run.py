"""Тесты главного CLI-сценария _cmd_run."""
from __future__ import annotations

import logging
from pathlib import Path

from app.config.settings import (
    AudioConfig,
    EncodingConfig,
    EnvConfig,
    OutputConfig,
    PathsConfig,
    RetentionConfig,
    StitcherConfig,
    ThumbnailConfig,
    ToolsConfig,
    VideoConfig,
    YtDlpConfig,
)
from app.input.sheet_reader import SlotLoadReport
from app.models.domain import SlotKey, SourceVideo, StitchJob, WorkerResult
from main import _cmd_run


def _make_config(tmp_path: Path) -> StitcherConfig:
    gpu_profile = tmp_path / "gpu.txt"
    cpu_profile = tmp_path / "cpu.txt"
    ytdlp_video_profile = tmp_path / "ytdlp_video.txt"
    ytdlp_thumbnail_profile = tmp_path / "ytdlp_thumbnail.txt"
    gpu_profile.write_text("-c:v h264_nvenc\n", encoding="utf-8")
    cpu_profile.write_text("-c:v libx264\n", encoding="utf-8")
    ytdlp_video_profile.write_text("-f bestvideo+bestaudio\n--merge-output-format mkv\n", encoding="utf-8")
    ytdlp_thumbnail_profile.write_text("--write-thumbnail\n--skip-download\n", encoding="utf-8")

    return StitcherConfig(
        paths=PathsConfig(
            temp_dir=tmp_path / "temp",
            output_dir=tmp_path / "output",
            logs_dir=tmp_path / "logs",
            state_dir=tmp_path / "state",
        ),
        tools=ToolsConfig(
            ytdlp_path=tmp_path / "yt-dlp.exe",
            ffmpeg_path=tmp_path / "ffmpeg.exe",
        ),
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
        thumbnail=ThumbnailConfig(duration_seconds=3, source="youtube"),
        output=OutputConfig(filename_template="{date}_{time}_{lang}.mp4"),
        retention=RetentionConfig(cleanup_on_start=False, temp_max_age_days=3, logs_max_age_days=7),
    )


def _make_env() -> EnvConfig:
    return EnvConfig(
        google_sheets_id="sheet-id",
        google_drive_folder_id="",
        telegram_bot_token="",
        telegram_chat_id="",
        telegram_admin_user_ids=(),
        telegram_user_ids=(),
    )


def _make_job(index: int) -> StitchJob:
    key = SlotKey(date=f"2{index}-03-2026", time="14-00", language="ru")
    videos = (
        SourceVideo(url=f"https://youtu.be/{index}a", title=f"V{index}a", order=1),
        SourceVideo(url=f"https://youtu.be/{index}b", title=f"V{index}b", order=2),
    )
    return StitchJob(slot_key=key, videos=videos)


def test_cmd_run_processes_all_slots_and_continues_after_failure(tmp_path: Path, monkeypatch) -> None:
    config = _make_config(tmp_path)
    env = _make_env()
    logger = logging.getLogger("test_cmd_run")

    jobs = [_make_job(1), _make_job(2), _make_job(3)]
    report = SlotLoadReport(
        jobs=jobs,
        total_rows=6,
        enriched_rows=6,
        recognized_columns=["Links", "Date", "Time"],
        rows_by_language={"ru": 6},
    )
    monkeypatch.setattr("main._preflight_checks", lambda *_: True)
    monkeypatch.setattr("main._load_future_slots", lambda *_: report)

    processed: list[str] = []

    class FakePipeline:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def run(self, job: StitchJob) -> WorkerResult:
            processed.append(str(job.slot_key))
            if str(job.slot_key) == str(jobs[1].slot_key):
                return WorkerResult(success=False, error_message="ffmpeg error")
            out_path = config.paths.output_dir / f"{job.slot_key}.mp4"
            return WorkerResult(
                success=True,
                output_path=out_path,
                duration_seconds=1.0,
                output_size_bytes=1024,
            )

    monkeypatch.setattr("app.worker.pipeline.StitchPipeline", FakePipeline)

    exit_code = _cmd_run(dry_run=False, config=config, env=env, logger=logger)

    assert exit_code == 1
    assert processed == [str(job.slot_key) for job in jobs]


def test_cmd_run_returns_zero_when_no_future_slots(tmp_path: Path, monkeypatch, capsys) -> None:
    config = _make_config(tmp_path)
    env = _make_env()
    logger = logging.getLogger("test_cmd_run")

    report = SlotLoadReport(
        jobs=[],
        total_rows=0,
        enriched_rows=0,
        recognized_columns=["Links", "Date", "Time"],
        rows_by_language={},
    )
    monkeypatch.setattr("main._preflight_checks", lambda *_: True)
    monkeypatch.setattr("main._load_future_slots", lambda *_: report)

    exit_code = _cmd_run(dry_run=False, config=config, env=env, logger=logger)
    captured = capsys.readouterr().out

    assert exit_code == 0
    assert "Нет будущих слотов для обработки." in captured
