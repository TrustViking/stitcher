"""GPU → CPU fallback для ffmpeg-кодирования."""
from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class EncodeResult:
    process: subprocess.CompletedProcess[str]
    used_gpu: bool


def run_with_fallback(
    *,
    gpu_command: list[str],
    cpu_command: list[str],
    fallback_enabled: bool,
    logger: logging.Logger,
) -> EncodeResult:
    """Выполнить ffmpeg-команду с GPU/CPU fallback."""
    logger.debug("Starting GPU encode attempt.")
    gpu_result = _run_command(gpu_command, logger=logger, label="GPU")
    if gpu_result.returncode == 0:
        logger.debug("GPU encode attempt succeeded.")
        return EncodeResult(process=gpu_result, used_gpu=True)

    if not fallback_enabled:
        raise RuntimeError(
            "GPU encoding failed and fallback disabled: "
            f"{(gpu_result.stderr or '').strip()}"
        )

    logger.warning(
        "GPU encoding failed, falling back to CPU: %s",
        (gpu_result.stderr or "").strip(),
    )
    logger.debug("Starting CPU fallback encode attempt.")

    cpu_result = _run_command(cpu_command, logger=logger, label="CPU")
    if cpu_result.returncode == 0:
        logger.debug("CPU fallback encode attempt succeeded.")
        return EncodeResult(process=cpu_result, used_gpu=False)

    raise RuntimeError(
        "CPU fallback failed: "
        f"{(cpu_result.stderr or '').strip()}"
    )


def _run_command(
    command: list[str],
    *,
    logger: logging.Logger,
    label: str,
) -> subprocess.CompletedProcess[str]:
    logger.debug("ffmpeg %s command: %s", label, " ".join(command))
    started = time.monotonic()
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    elapsed = time.monotonic() - started
    if result.stdout:
        logger.debug("ffmpeg %s stdout: %s", label, result.stdout.strip())
    if result.stderr:
        logger.debug("ffmpeg %s stderr: %s", label, result.stderr.strip())
    logger.debug("ffmpeg %s finished: returncode=%d elapsed=%.2fs", label, result.returncode, elapsed)
    return result
