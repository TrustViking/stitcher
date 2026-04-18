"""Тесты формирования concat manifest."""
from __future__ import annotations

from pathlib import Path

from app.concat.manifest_builder import build_manifest
from app.models.domain import NormalizedSegment


def test_build_manifest_contains_thumb_and_video_pairs(tmp_path: Path) -> None:
    segments = [
        NormalizedSegment(file_path=tmp_path / "2_normalized.mp4", segment_type="video", order=2),
        NormalizedSegment(file_path=tmp_path / "1_thumb_clip.mp4", segment_type="thumbnail_clip", order=1),
        NormalizedSegment(file_path=tmp_path / "3_thumb_clip.mp4", segment_type="thumbnail_clip", order=3),
        NormalizedSegment(file_path=tmp_path / "2_thumb_clip.mp4", segment_type="thumbnail_clip", order=2),
        NormalizedSegment(file_path=tmp_path / "1_normalized.mp4", segment_type="video", order=1),
        NormalizedSegment(file_path=tmp_path / "3_normalized.mp4", segment_type="video", order=3),
    ]
    manifest_path = tmp_path / "concat_manifest.txt"

    build_manifest(segments, manifest_path)

    lines = manifest_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 6
    assert lines[0].endswith("1_thumb_clip.mp4'")
    assert lines[1].endswith("1_normalized.mp4'")
    assert lines[2].endswith("2_thumb_clip.mp4'")
    assert lines[3].endswith("2_normalized.mp4'")
    assert lines[4].endswith("3_thumb_clip.mp4'")
    assert lines[5].endswith("3_normalized.mp4'")


def test_build_manifest_enforces_pair_completeness(tmp_path: Path) -> None:
    segments = [
        NormalizedSegment(file_path=tmp_path / "1_thumb_clip.mp4", segment_type="thumbnail_clip", order=1),
    ]

    manifest_path = tmp_path / "concat_manifest.txt"
    try:
        build_manifest(segments, manifest_path)
    except RuntimeError as exc:
        assert "Missing segments" in str(exc)
    else:
        raise AssertionError("Ожидался RuntimeError для неполного набора сегментов.")


def test_build_manifest_orders_fade_before_thumb_and_video(tmp_path: Path) -> None:
    segments = [
        NormalizedSegment(file_path=tmp_path / "1_normalized.mp4", segment_type="video", order=1),
        NormalizedSegment(file_path=tmp_path / "1_thumb_clip.mp4", segment_type="thumbnail_clip", order=1),
        NormalizedSegment(file_path=tmp_path / "1_fade.mp4", segment_type="fade_out", order=1),
    ]
    manifest_path = tmp_path / "concat_manifest.txt"

    build_manifest(segments, manifest_path)

    lines = manifest_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    assert lines[0].endswith("1_fade.mp4'")
    assert lines[1].endswith("1_thumb_clip.mp4'")
    assert lines[2].endswith("1_normalized.mp4'")
