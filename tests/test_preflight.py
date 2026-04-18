"""Тесты preflight checks CLI."""
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
from main import _collect_preflight_errors, _preflight_checks


def _make_config(
    tmp_path: Path,
    *,
    ytdlp_path: Path,
    ffmpeg_path: Path,
) -> StitcherConfig:
    gpu_profile = tmp_path / "gpu.txt"
    cpu_profile = tmp_path / "cpu.txt"
    gpu_profile.write_text("-c:v h264_nvenc\n", encoding="utf-8")
    cpu_profile.write_text("-c:v libx264\n", encoding="utf-8")

    return StitcherConfig(
        paths=PathsConfig(
            temp_dir=tmp_path / "temp",
            output_dir=tmp_path / "output",
            logs_dir=tmp_path / "logs",
            state_dir=tmp_path / "state",
        ),
        tools=ToolsConfig(ytdlp_path=ytdlp_path, ffmpeg_path=ffmpeg_path),
        ytdlp=YtDlpConfig(auto_update=True, update_check_interval_days=7),
        encoding=EncodingConfig(
            gpu_profile=gpu_profile,
            cpu_profile=cpu_profile,
            fallback_to_cpu=True,
        ),
        video=VideoConfig(width=1920, height=1080, fps=25),
        audio=AudioConfig(codec="aac", sample_rate=48000, bitrate="512k", channels="stereo"),
        thumbnail=ThumbnailConfig(duration_seconds=3, source="youtube"),
        output=OutputConfig(filename_template="{date}_{time}_{lang}.mp4"),
        retention=RetentionConfig(cleanup_on_start=False, temp_max_age_days=3, logs_max_age_days=7),
    )


def _make_env(*, sheets_id: str) -> EnvConfig:
    return EnvConfig(
        google_sheets_id=sheets_id,
        google_drive_folder_id="",
        telegram_bot_token="",
        telegram_chat_id="",
        telegram_admin_user_ids=(),
        telegram_user_ids=(),
    )


def test_collect_preflight_errors_aggregates_all_messages(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("main.PROJECT_ROOT", tmp_path)

    config = _make_config(
        tmp_path,
        ytdlp_path=tmp_path / "missing_ytdlp.exe",
        ffmpeg_path=tmp_path / "missing_ffmpeg.exe",
    )
    env = _make_env(sheets_id="")
    logger = logging.getLogger("test_preflight")

    errors = _collect_preflight_errors(config, env, logger)

    assert len(errors) >= 4
    assert any("GOOGLE_SHEETS_ID не задан" in item for item in errors)
    assert any("OAuth credentials не найдены" in item for item in errors)
    assert any("yt-dlp не найден" in item for item in errors)
    assert any("ffmpeg не найден" in item for item in errors)


def test_preflight_prints_readable_error_block(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr("main.PROJECT_ROOT", tmp_path)

    config = _make_config(
        tmp_path,
        ytdlp_path=tmp_path / "missing_ytdlp.exe",
        ffmpeg_path=tmp_path / "missing_ffmpeg.exe",
    )
    env = _make_env(sheets_id="")
    logger = logging.getLogger("test_preflight")

    ok = _preflight_checks(config, env, logger)
    captured = capsys.readouterr().out

    assert ok is False
    assert "Preflight checks failed" in captured
    assert "GOOGLE_SHEETS_ID не задан" in captured
    assert "Исправьте ошибки выше и запустите снова." in captured


def test_preflight_passes_when_everything_available(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("main.PROJECT_ROOT", tmp_path)

    secrets_dir = tmp_path / "secrets"
    secrets_dir.mkdir(parents=True, exist_ok=True)
    (secrets_dir / "credentials.json").write_text("{}", encoding="utf-8")

    ytdlp = tmp_path / "yt-dlp.exe"
    ffmpeg = tmp_path / "ffmpeg.exe"
    ytdlp.write_text("", encoding="utf-8")
    ffmpeg.write_text("", encoding="utf-8")

    config = _make_config(tmp_path, ytdlp_path=ytdlp, ffmpeg_path=ffmpeg)
    env = _make_env(sheets_id="sheet-id")
    logger = logging.getLogger("test_preflight")

    assert _preflight_checks(config, env, logger) is True
