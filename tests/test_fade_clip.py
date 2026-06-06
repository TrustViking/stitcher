"""Тесты генератора fade_out-клипа."""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from app.transcode.fade_clip import FadeClipBuilder


def test_build_fade_clip_returns_fade_segment(tmp_path: Path, monkeypatch) -> None:
    builder = FadeClipBuilder(
        ffmpeg_path=tmp_path / "ffmpeg.exe",
        duration_seconds=1,
        width=1920,
        height=1080,
        audio_codec="aac",
        audio_bitrate="512k",
        audio_sample_rate=48000,
        audio_channels=2,
        logger=logging.getLogger("test_fade_clip"),
    )
    slot_temp_dir = tmp_path / "slot"

    def fake_run(command, **kwargs):  # noqa: ANN001
        assert kwargs["stdout"] is subprocess.DEVNULL
        assert kwargs["stderr"] is subprocess.PIPE
        assert kwargs["check"] is False
        assert command[-1].endswith("1_fade.mp4")
        output_path = Path(command[-1])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("ok", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr("app.transcode.fade_clip.subprocess.run", fake_run)

    segment = builder.build_clip(order=1, slot_temp_dir=slot_temp_dir)

    assert segment.segment_type == "fade_out"
    assert segment.file_path.exists()
    assert segment.file_path.name == "1_fade.mp4"
    assert segment.used_gpu is False


def test_build_fade_clip_raises_on_ffmpeg_error(tmp_path: Path, monkeypatch) -> None:
    builder = FadeClipBuilder(
        ffmpeg_path=tmp_path / "ffmpeg.exe",
        duration_seconds=1,
        width=1920,
        height=1080,
        audio_codec="aac",
        audio_bitrate="512k",
        audio_sample_rate=48000,
        audio_channels=2,
        logger=logging.getLogger("test_fade_clip"),
    )

    def fake_run(command, **kwargs):  # noqa: ANN001
        assert kwargs["stdout"] is subprocess.DEVNULL
        assert kwargs["stderr"] is subprocess.PIPE
        assert kwargs["check"] is False
        return subprocess.CompletedProcess(command, 1, stdout=b"", stderr=b"boom")

    monkeypatch.setattr("app.transcode.fade_clip.subprocess.run", fake_run)

    try:
        builder.build_clip(order=1, slot_temp_dir=tmp_path / "slot")
    except RuntimeError as exc:
        assert "Fade clip failed" in str(exc)
    else:
        raise AssertionError("Ожидался RuntimeError при ошибке ffmpeg.")
