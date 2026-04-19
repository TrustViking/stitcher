"""Загрузчик config.toml → StitcherConfig."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

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
from app.runtime.paths import PROJECT_ROOT

# Python 3.11+ поставляется с tomllib; для более ранних версий — tomli
if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib  # type: ignore[no-redef]
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ImportError as exc:
            raise RuntimeError(
                "Для Python < 3.11 требуется пакет tomli: pip install tomli"
            ) from exc


def load_config(config_path: Path | None = None) -> StitcherConfig:
    """Загрузить config.toml и вернуть StitcherConfig.

    Если config_path не передан — ищем config.toml в PROJECT_ROOT.
    Относительные пути в секциях резолвятся относительно PROJECT_ROOT.
    """
    if config_path is None:
        config_path = PROJECT_ROOT / "config.toml"

    if not config_path.exists():
        raise RuntimeError(
            f"Файл конфигурации не найден: {config_path}. "
            "Создайте config.toml по образцу из документации."
        )

    try:
        with open(config_path, "rb") as fh:
            raw: Dict[str, Any] = tomllib.load(fh)
    except Exception as exc:
        raise RuntimeError(f"Не удалось прочитать config.toml ({config_path}): {exc}") from exc

    _require_section(raw, "paths")
    _require_section(raw, "tools")
    _require_section(raw, "encoding")

    root = PROJECT_ROOT

    paths_raw = raw["paths"]
    paths = PathsConfig(
        temp_dir=_resolve_path(paths_raw.get("temp_dir", "./temp"), root),
        output_dir=_resolve_path(paths_raw.get("output_dir", "./output"), root),
        logs_dir=_resolve_path(paths_raw.get("logs_dir", "./logs"), root),
        state_dir=_resolve_path(paths_raw.get("state_dir", "./state"), root),
    )

    tools_raw = raw["tools"]
    ytdlp_raw = _require_field(tools_raw, "ytdlp_path", "tools")
    ffmpeg_raw = _require_field(tools_raw, "ffmpeg_path", "tools")
    tools = ToolsConfig(
        ytdlp_path=_resolve_path(ytdlp_raw, root),
        ffmpeg_path=_resolve_path(ffmpeg_raw, root),
    )

    ytdlp_raw = raw.get("ytdlp", {})
    ytdlp = YtDlpConfig(
        auto_update=bool(ytdlp_raw.get("auto_update", True)),
        update_check_interval_days=int(ytdlp_raw.get("update_check_interval_days", 7)),
    )

    enc_raw = raw["encoding"]
    encoding = EncodingConfig(
        gpu_profile=_resolve_path(
            enc_raw.get("gpu_profile", "./profiles/gpu_nvenc.txt"), root
        ),
        cpu_profile=_resolve_path(
            enc_raw.get("cpu_profile", "./profiles/cpu_libx264.txt"), root
        ),
        ytdlp_video_profile=_resolve_path(
            enc_raw.get("ytdlp_video_profile", "./profiles/ytdlp_video.txt"), root
        ),
        ytdlp_thumbnail_profile=_resolve_path(
            enc_raw.get("ytdlp_thumbnail_profile", "./profiles/ytdlp_thumbnail.txt"), root
        ),
        fallback_to_cpu=bool(enc_raw.get("fallback_to_cpu", True)),
    )

    video_raw = raw.get("video", {})
    video = VideoConfig(
        width=int(video_raw.get("width", 1920)),
        height=int(video_raw.get("height", 1080)),
        fps=int(video_raw.get("fps", 25)),
    )

    audio_raw = raw.get("audio", {})
    audio = AudioConfig(
        codec=str(audio_raw.get("codec", "aac")),
        sample_rate=int(audio_raw.get("sample_rate", 48000)),
        bitrate=str(audio_raw.get("bitrate", "512k")),
        channels=str(audio_raw.get("channels", "stereo")),
    )

    thumb_raw = raw.get("thumbnail", {})
    thumbnail = ThumbnailConfig(
        duration_seconds=int(thumb_raw.get("duration_seconds", 3)),
        source=str(thumb_raw.get("source", "youtube")),
        fade_duration_seconds=int(thumb_raw.get("fade_duration_seconds", 1)),
    )

    output_raw = raw.get("output", {})
    output = OutputConfig(
        filename_template=str(
            output_raw.get("filename_template", "{date}_{time}_{lang}.mp4")
        ),
    )

    ret_raw = raw.get("retention", {})
    retention = RetentionConfig(
        cleanup_on_start=bool(ret_raw.get("cleanup_on_start", True)),
        temp_max_age_days=int(ret_raw.get("temp_max_age_days", 3)),
        logs_max_age_days=int(ret_raw.get("logs_max_age_days", 7)),
    )

    google_raw = raw.get("google", {})
    google = GoogleConfig(
        sheets_id=(google_raw.get("sheets_id") or "").strip(),
    )

    return StitcherConfig(
        paths=paths,
        tools=tools,
        ytdlp=ytdlp,
        encoding=encoding,
        video=video,
        audio=audio,
        thumbnail=thumbnail,
        output=output,
        retention=retention,
        google=google,
    )


def _require_section(raw: Dict[str, Any], section: str) -> None:
    """Выбросить RuntimeError если секция отсутствует в конфиге."""
    if section not in raw:
        raise RuntimeError(
            f"Обязательная секция [{section}] отсутствует в config.toml."
        )


def _require_field(section_raw: Dict[str, Any], field_name: str, section_name: str) -> str:
    value = section_raw.get(field_name)
    if value is None or not str(value).strip():
        raise RuntimeError(
            f"Обязательное поле {section_name}.{field_name} отсутствует в config.toml"
        )
    return str(value)


def _resolve_path(value: str, root: Path) -> Path:
    """Резолвить путь относительно root если он не абсолютный."""
    p = Path(str(value))
    if p.is_absolute():
        return p
    return (root / p).resolve()
