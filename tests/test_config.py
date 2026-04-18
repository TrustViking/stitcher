"""Тесты загрузки конфигурации из TOML."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from app.config.config_loader import load_config
from app.config.settings import StitcherConfig


@pytest.fixture()
def valid_config_file(tmp_path: Path) -> Path:
    """Создать валидный config.toml во временной директории."""
    toml_text = textwrap.dedent(
        """\
        [paths]
        temp_dir = "./temp"
        output_dir = "./output"
        logs_dir = "./logs"
        state_dir = "./state"

        [tools]
        ytdlp_path = "./tools/_yt-dlp/yt-dlp.exe"
        ffmpeg_path = "./tools/_ffmpeg/bin/ffmpeg.exe"

        [ytdlp]
        auto_update = true
        update_check_interval_days = 7

        [encoding]
        gpu_profile = "./tools/_profiles/gpu_nvenc.txt"
        cpu_profile = "./tools/_profiles/cpu_libx264.txt"
        fallback_to_cpu = true

        [video]
        width = 1920
        height = 1080
        fps = 25

        [audio]
        codec = "aac"
        sample_rate = 48000
        bitrate = "512k"
        channels = "stereo"

        [thumbnail]
        duration_seconds = 3
        fade_duration_seconds = 1
        source = "youtube"

        [output]
        filename_template = "{date}_{time}_{lang}.mp4"

        [retention]
        cleanup_on_start = true
        temp_max_age_days = 3
        logs_max_age_days = 7
        """
    )
    config_path = tmp_path / "config.toml"
    config_path.write_text(toml_text, encoding="utf-8")
    return config_path


def test_load_valid_config(valid_config_file: Path) -> None:
    """Загрузка валидного config.toml возвращает StitcherConfig."""
    config = load_config(valid_config_file)
    assert isinstance(config, StitcherConfig)
    assert config.video.width == 1920
    assert config.video.height == 1080
    assert config.video.fps == 25
    assert config.audio.codec == "aac"
    assert config.paths.state_dir.name == "state"
    assert config.thumbnail.fade_duration_seconds == 1
    assert config.ytdlp.auto_update is True
    assert config.ytdlp.update_check_interval_days == 7


def test_missing_required_section(tmp_path: Path) -> None:
    """Отсутствие обязательной секции вызывает RuntimeError."""
    toml_text = textwrap.dedent(
        """\
        [paths]
        temp_dir = "./temp"
        output_dir = "./output"
        logs_dir = "./logs"

        [tools]
        ytdlp_path = "./tools/_yt-dlp/yt-dlp.exe"
        ffmpeg_path = "./tools/_ffmpeg/bin/ffmpeg.exe"
        """
    )
    config_path = tmp_path / "config.toml"
    config_path.write_text(toml_text, encoding="utf-8")
    with pytest.raises(RuntimeError, match="encoding"):
        load_config(config_path)


def test_missing_required_tool_field(tmp_path: Path) -> None:
    toml_text = textwrap.dedent(
        """\
        [paths]
        temp_dir = "./temp"
        output_dir = "./output"
        logs_dir = "./logs"

        [tools]
        ffmpeg_path = "./tools/_ffmpeg/bin/ffmpeg.exe"

        [encoding]
        gpu_profile = "./tools/_profiles/gpu_nvenc.txt"
        cpu_profile = "./tools/_profiles/cpu_libx264.txt"
        fallback_to_cpu = true
        """
    )
    config_path = tmp_path / "config.toml"
    config_path.write_text(toml_text, encoding="utf-8")

    with pytest.raises(RuntimeError, match="tools.ytdlp_path"):
        load_config(config_path)


def test_missing_config_file(tmp_path: Path) -> None:
    """Отсутствие config.toml вызывает RuntimeError."""
    with pytest.raises(RuntimeError, match="не найден"):
        load_config(tmp_path / "nonexistent.toml")
