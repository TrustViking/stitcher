"""Тесты для deno_updater."""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from app.runtime.deno_updater import DenoUpdateStatus, maybe_update_deno

_LOGGER = logging.getLogger("test")


def test_deno_updater_not_configured() -> None:
    """Если deno_path=None — возвращает статус без попытки обновления."""
    status = maybe_update_deno(
        deno_path=None,
        state_dir=Path("state"),
        enabled=False,
        interval_days=7,
        logger=_LOGGER,
    )
    assert isinstance(status, DenoUpdateStatus)
    assert status.current_version is None
    assert not status.attempted
    assert status.message == "не настроен"


def test_deno_nonexistent_path_disabled(tmp_path: Path) -> None:
    """Если deno_path не существует и enabled=False — возвращает current_version=None."""
    fake_path = tmp_path / "deno.exe"
    status = maybe_update_deno(
        deno_path=fake_path,
        state_dir=tmp_path,
        enabled=False,
        interval_days=7,
        logger=_LOGGER,
    )
    assert isinstance(status, DenoUpdateStatus)
    assert status.current_version is None
    assert status.attempted is False


def test_deno_interval_not_elapsed(tmp_path: Path) -> None:
    """Если интервал не истёк — пропускаем обновление."""
    fake_path = tmp_path / "deno.exe"
    state_file = tmp_path / "deno_last_check.json"
    state_file.write_text(
        json.dumps({"last_check_ts": int(time.time())}), encoding="utf-8"
    )

    status = maybe_update_deno(
        deno_path=fake_path,
        state_dir=tmp_path,
        enabled=True,
        interval_days=7,
        logger=_LOGGER,
    )
    assert status.attempted is False
    assert status.last_check_days_ago == 0
