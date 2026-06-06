"""Построение команд ffmpeg из профильных файлов."""
from __future__ import annotations

import shlex
from pathlib import Path

_AUDIO_OPTIONS_WITH_VALUE = {"-c:a", "-b:a", "-ar", "-ac", "-af"}
_AUDIO_FLAGS = {"-an"}


def load_ytdlp_profile(profile_path: Path) -> list[str]:
    """Загрузить yt-dlp профиль из .txt файла в список аргументов."""
    if not profile_path.exists():
        raise RuntimeError(f"Файл yt-dlp профиля не найден: {profile_path}")
    args: list[str] = []
    for raw_line in profile_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        args.extend(shlex.split(line))
    return args


def load_profile(profile_path: Path) -> list[str]:
    """Загрузить профиль ffmpeg из .txt файла в список аргументов."""
    if not profile_path.exists():
        raise RuntimeError(f"Файл ffmpeg-профиля не найден: {profile_path}")

    args: list[str] = []
    for raw_line in profile_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        args.extend(shlex.split(line))
    return args


def build_normalize_command(
    *,
    input_path: Path,
    output_path: Path,
    profile_args: list[str],
    ffmpeg_path: Path,
) -> list[str]:
    """Собрать команду нормализации видео."""
    return [
        str(ffmpeg_path),
        "-y",
        "-i",
        str(input_path),
        *profile_args,
        str(output_path),
    ]


def build_thumbnail_clip_command(
    *,
    thumbnail_path: Path,
    output_path: Path,
    duration_seconds: int,
    width: int,
    height: int,
    profile_args: list[str],
    ffmpeg_path: Path,
    audio_codec: str = "aac",
    audio_bitrate: str = "512k",
    audio_sample_rate: int = 48000,
    audio_channels: int = 2,
) -> list[str]:
    """Собрать команду создания превью-клипа из изображения."""
    video_profile_args = _strip_audio_args(profile_args)
    vf_arg = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
    )
    return [
        str(ffmpeg_path),
        "-y",
        "-loop",
        "1",
        "-i",
        str(thumbnail_path),
        "-f",
        "lavfi",
        "-i",
        (
            "anullsrc="
            f"channel_layout={_channel_layout_from_count(audio_channels)}:"
            f"sample_rate={audio_sample_rate}"
        ),
        "-t",
        str(duration_seconds),
        "-vf",
        vf_arg,
        *video_profile_args,
        "-c:a",
        audio_codec,
        "-b:a",
        audio_bitrate,
        "-ar",
        str(audio_sample_rate),
        "-ac",
        str(audio_channels),
        "-shortest",
        str(output_path),
    ]


def build_concat_command(
    *,
    manifest_path: Path,
    output_path: Path,
    ffmpeg_path: Path,
) -> list[str]:
    """Собрать команду финальной склейки."""
    return [
        str(ffmpeg_path),
        "-y",
        "-loglevel",
        "warning",
        "-nostats",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(manifest_path),
        "-c",
        "copy",
        "-fflags",
        "+genpts",
        "-avoid_negative_ts",
        "make_zero",
        str(output_path),
    ]


def _strip_audio_args(profile_args: list[str]) -> list[str]:
    """Удалить из профиля аудио-аргументы для режима thumbnail clip."""
    filtered: list[str] = []
    skip_next = False

    for token in profile_args:
        if skip_next:
            skip_next = False
            continue
        if token in _AUDIO_OPTIONS_WITH_VALUE:
            skip_next = True
            continue
        if token in _AUDIO_FLAGS:
            continue
        filtered.append(token)

    return filtered


def _channel_layout_from_count(audio_channels: int) -> str:
    """Преобразовать количество каналов в channel_layout для anullsrc."""
    if audio_channels <= 1:
        return "mono"
    return "stereo"
