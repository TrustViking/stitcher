"""Автообновление Deno раз в N дней."""
from __future__ import annotations

import json
import logging
import subprocess
import time
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


STATE_FILENAME = "deno_last_check.json"
DENO_RELEASES_API = "https://api.github.com/repos/denoland/deno/releases/latest"
DENO_DOWNLOAD_TEMPLATE = (
    "https://github.com/denoland/deno/releases/download/{version}"
    "/deno-x86_64-pc-windows-msvc.zip"
)
UPDATE_TIMEOUT_SECONDS = 60


@dataclass(frozen=True)
class DenoUpdateStatus:
    current_version: Optional[str]
    last_check_days_ago: Optional[int]
    attempted: bool
    succeeded: bool
    message: str


def maybe_update_deno(
    *,
    deno_path: Optional[Path],
    state_dir: Path,
    enabled: bool,
    interval_days: int,
    logger: logging.Logger,
) -> DenoUpdateStatus:
    """Если прошло >= interval_days с последней проверки — скачать и обновить Deno.

    Правила:
    - Если deno_path is None — возвращаем статус «не настроен».
    - Если enabled=False — только читаем текущую версию, обновление не запускаем.
    - Если интервал не истёк — только читаем версию и дни с прошлой проверки.
    - Ошибки обновления никогда не блокируют работу, только логируются.
    """
    if deno_path is None:
        return DenoUpdateStatus(
            current_version=None,
            last_check_days_ago=None,
            attempted=False,
            succeeded=False,
            message="не настроен",
        )

    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / STATE_FILENAME

    current_version = _read_current_version(deno_path, logger)
    last_check_ts = _read_last_check(state_file)
    days_ago = _days_since(last_check_ts) if last_check_ts is not None else None

    if not enabled:
        return DenoUpdateStatus(
            current_version=current_version,
            last_check_days_ago=days_ago,
            attempted=False,
            succeeded=False,
            message="auto-update disabled",
        )

    if last_check_ts is not None and days_ago is not None and days_ago < interval_days:
        # Если deno.exe физически отсутствует — игнорируем интервал и скачиваем
        if not deno_path.exists():
            logger.info(
                "deno auto-update: файл не найден, скачивание несмотря на интервал"
            )
        else:
            return DenoUpdateStatus(
                current_version=current_version,
                last_check_days_ago=days_ago,
                attempted=False,
                succeeded=False,
                message=f"check skipped: {days_ago} days since last check (interval {interval_days})",
            )

    logger.info("deno auto-update: получение последней версии с GitHub")
    succeeded = False
    message = ""
    try:
        req = urllib.request.Request(
            DENO_RELEASES_API,
            headers={"User-Agent": "stitcher"},
        )
        with urllib.request.urlopen(req, timeout=UPDATE_TIMEOUT_SECONDS) as resp:
            release_info = json.loads(resp.read().decode("utf-8"))
        latest_version = release_info.get("tag_name", "").strip()
        if not latest_version:
            raise RuntimeError("GitHub API вернул пустой tag_name")

        download_url = DENO_DOWNLOAD_TEMPLATE.format(version=latest_version)
        deno_path.parent.mkdir(parents=True, exist_ok=True)
        zip_path = deno_path.parent / "deno_update.zip"
        logger.info("deno auto-update: скачивание %s", download_url)
        urllib.request.urlretrieve(download_url, zip_path)  # noqa: S310

        with zipfile.ZipFile(zip_path) as zf:
            zf.extract("deno.exe", deno_path.parent)

        zip_path.unlink(missing_ok=True)
        succeeded = True
        message = latest_version
        logger.info("deno auto-update: успешно обновлён до %s", latest_version)
    except Exception as exc:
        message = f"error: {exc}"
        logger.warning("deno auto-update не удалось: %s", exc)

    if succeeded:
        _write_last_check(state_file, int(time.time()))
    new_version = _read_current_version(deno_path, logger)

    return DenoUpdateStatus(
        current_version=new_version,
        last_check_days_ago=0,
        attempted=True,
        succeeded=succeeded,
        message=message,
    )


def _read_current_version(deno_path: Path, logger: logging.Logger) -> Optional[str]:
    if not deno_path.exists():
        return None
    try:
        result = subprocess.run(
            [str(deno_path), "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode == 0:
            first_line = (result.stdout or "").strip().splitlines()[0] if (result.stdout or "").strip() else ""
            return first_line or None
    except Exception as exc:
        logger.debug("deno --version failed: %s", exc)
    return None


def _read_last_check(state_file: Path) -> Optional[int]:
    if not state_file.exists():
        return None
    try:
        payload = json.loads(state_file.read_text("utf-8"))
        ts = payload.get("last_check_ts")
        return int(ts) if ts is not None else None
    except Exception:
        return None


def _write_last_check(state_file: Path, ts: int) -> None:
    try:
        state_file.write_text(
            json.dumps({"last_check_ts": ts}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def _days_since(ts: int) -> int:
    now = int(time.time())
    return max(0, (now - ts) // 86400)
