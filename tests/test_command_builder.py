"""Тесты построения ffmpeg-команд."""
from __future__ import annotations

from pathlib import Path

from app.ffmpeg.command_builder import (
    build_concat_command,
    build_normalize_command,
    build_thumbnail_clip_command,
    load_profile,
)


def test_load_profile_skips_empty_lines_and_comments(tmp_path: Path) -> None:
    profile = tmp_path / "profile.txt"
    profile.write_text(
        "# comment\n\n-c:v h264_nvenc\n-b:v 10M\n-c:a aac\n",
        encoding="utf-8",
    )

    args = load_profile(profile)
    assert args == ["-c:v", "h264_nvenc", "-b:v", "10M", "-c:a", "aac"]


def test_build_normalize_command() -> None:
    command = build_normalize_command(
        input_path=Path("in.mkv"),
        output_path=Path("out.mp4"),
        profile_args=["-c:v", "libx264", "-b:v", "10M"],
        ffmpeg_path=Path("ffmpeg"),
    )

    assert command == [
        "ffmpeg",
        "-y",
        "-i",
        "in.mkv",
        "-c:v",
        "libx264",
        "-b:v",
        "10M",
        "out.mp4",
    ]


def test_build_thumbnail_clip_command_contains_required_flags() -> None:
    command = build_thumbnail_clip_command(
        thumbnail_path=Path("thumb.jpg"),
        output_path=Path("thumb_clip.mp4"),
        duration_seconds=3,
        width=1920,
        height=1080,
        profile_args=["-c:v", "h264_nvenc", "-c:a", "libopus", "-b:a", "64k"],
        ffmpeg_path=Path("ffmpeg"),
        audio_codec="aac",
        audio_bitrate="320k",
        audio_sample_rate=44100,
        audio_channels=1,
    )

    assert "-loop" in command and "1" in command
    assert "-t" in command and "3" in command
    assert "anullsrc=channel_layout=mono:sample_rate=44100" in command
    assert "libopus" not in command
    assert "320k" in command
    assert command[-1] == "thumb_clip.mp4"


def test_build_concat_command() -> None:
    command = build_concat_command(
        manifest_path=Path("manifest.txt"),
        output_path=Path("result.mp4"),
        ffmpeg_path=Path("ffmpeg"),
    )

    assert command == [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        "manifest.txt",
        "-c",
        "copy",
        "result.mp4",
    ]
