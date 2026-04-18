"""Интерфейсы и адаптеры прогресса обработки."""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.models.domain import WorkerProgress


class ProgressTracker(ABC):
    """Абстрактный интерфейс отслеживания прогресса."""

    @abstractmethod
    def on_progress(self, progress: WorkerProgress) -> None:
        """Обработать обновление прогресса."""


class CliProgressTracker(ProgressTracker):
    """Прогресс в stdout для CLI-режима."""

    def on_progress(self, progress: WorkerProgress) -> None:
        marker = f"[{progress.current_video}/{progress.total_videos}]"
        if progress.stage == "download":
            print(f"  ⬇️  {marker} {progress.message}")
            return
        if progress.stage == "download_done":
            print(f"  ⬇️  {marker} {progress.message}")
            return
        if progress.stage == "normalize":
            print(f"  ⚙️  {marker} {progress.message}")
            return
        if progress.stage == "normalize_done":
            print(f"  ⚙️  {marker} {progress.message}")
            return
        if progress.stage == "concat":
            print(f"  🧩 {progress.message}...")
            return
        if progress.stage == "error":
            print(f"  ❌ {progress.message}")
            return
        if progress.stage == "done":
            return
        print(f"  • {progress.message}")


class NullProgressTracker(ProgressTracker):
    """Заглушка — ничего не делает."""

    def on_progress(self, progress: WorkerProgress) -> None:
        del progress
