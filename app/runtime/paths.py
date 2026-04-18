"""Резолвинг корневого пути проекта и рабочих директорий."""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.config.settings import StitcherConfig


def _resolve_project_root() -> Path:
    """Вернуть корневую директорию проекта.

    Dev mode: paths.py живёт в app/runtime/paths.py → parents[2] = корень.
    Frozen mode: sys.executable — это .exe в корне дистрибутива.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


PROJECT_ROOT: Path = _resolve_project_root()


@dataclass(frozen=True)
class StitcherPaths:
    """Рабочие пути проекта."""

    project_root: Path
    config_path: Path
    temp_dir: Path
    output_dir: Path
    logs_dir: Path
    ffmpeg_profiles_dir: Path
    secrets_dir: Path


def get_project_paths(config: "StitcherConfig | None" = None) -> StitcherPaths:
    """Вернуть пути проекта.

    Если config передан — пути берутся из него.
    Иначе — defaults относительно PROJECT_ROOT.
    """
    root = PROJECT_ROOT
    if config is not None:
        return StitcherPaths(
            project_root=root,
            config_path=root / "config.toml",
            temp_dir=config.paths.temp_dir,
            output_dir=config.paths.output_dir,
            logs_dir=config.paths.logs_dir,
            ffmpeg_profiles_dir=root / "ffmpeg_profiles",
            secrets_dir=root / "secrets",
        )
    return StitcherPaths(
        project_root=root,
        config_path=root / "config.toml",
        temp_dir=root / "temp",
        output_dir=root / "output",
        logs_dir=root / "logs",
        ffmpeg_profiles_dir=root / "ffmpeg_profiles",
        secrets_dir=root / "secrets",
    )
