"""Построение concat manifest для финальной склейки."""
from __future__ import annotations

from pathlib import Path

from app.models.domain import NormalizedSegment


def build_manifest(segments: list[NormalizedSegment], manifest_path: Path) -> Path:
    """Создать concat manifest файл из сегментов."""
    grouped: dict[int, dict[str, NormalizedSegment]] = {}
    for segment in segments:
        bucket = grouped.setdefault(segment.order, {})
        if segment.segment_type in bucket:
            raise RuntimeError(
                f"Дублирующийся segment_type={segment.segment_type!r} для order={segment.order}."
            )
        bucket[segment.segment_type] = segment

    ordered_lines: list[str] = []
    for order in sorted(grouped):
        bucket = grouped[order]
        fade = bucket.get("fade_out")
        thumb = bucket.get("thumbnail_clip")
        video = bucket.get("video")
        if thumb is None or video is None:
            raise RuntimeError(f"Missing segments for order={order}.")
        if fade is not None:
            ordered_lines.append(_manifest_line(fade.file_path))
        ordered_lines.append(_manifest_line(thumb.file_path))
        ordered_lines.append(_manifest_line(video.file_path))

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text("\n".join(ordered_lines) + "\n", encoding="utf-8")
    return manifest_path


def _manifest_line(path: Path) -> str:
    normalized = path.resolve().as_posix().replace("'", "'\\''")
    return f"file '{normalized}'"
