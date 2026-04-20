"""Stitcher CLI — точка входа."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

from app.runtime.paths import PROJECT_ROOT

if TYPE_CHECKING:
    import logging

    from app.config.settings import StitcherConfig
    from app.input.sheet_reader import SlotLoadReport
    from app.models.domain import StitchJob, WorkerResult


def _setup_stdio_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="stitcher",
        description="Stitcher — автоматизированный пайплайн склейки видео.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Пробный прогон без реальной обработки.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Включить DEBUG-логирование.",
    )

    args = parser.parse_args()

    _setup_stdio_utf8()
    print("🔵 Stitcher запускается...")

    from app.runtime.env_loader import load_env_file

    load_env_file()

    from app.config.config_loader import load_config

    try:
        config = load_config()
    except RuntimeError as exc:
        print(f"Ошибка загрузки конфигурации: {exc}", file=sys.stderr)
        sys.exit(1)

    from app.runtime.logging_config import get_logger, setup_logging

    setup_logging(debug=args.debug, logs_dir=config.paths.logs_dir)
    logger = get_logger(__name__)

    # --- startup path snapshot (goes to log file only, not console) ---
    logger.debug("=== Stitcher startup ===")
    logger.debug("PROJECT_ROOT : %s", PROJECT_ROOT)
    logger.debug("config.toml  : %s", PROJECT_ROOT / "config.toml")
    logger.debug("ffmpeg       : %s", config.tools.ffmpeg_path)
    logger.debug("yt-dlp       : %s", config.tools.ytdlp_path)
    logger.debug("gpu_profile  : %s", config.encoding.gpu_profile)
    logger.debug("cpu_profile  : %s", config.encoding.cpu_profile)
    logger.debug("ytdlp_video  : %s", config.encoding.ytdlp_video_profile)
    logger.debug("ytdlp_thumb  : %s", config.encoding.ytdlp_thumbnail_profile)
    logger.debug("temp_dir     : %s", config.paths.temp_dir)
    logger.debug("output_dir   : %s", config.paths.output_dir)
    logger.debug("logs_dir     : %s", config.paths.logs_dir)
    logger.debug("state_dir    : %s", config.paths.state_dir)
    logger.debug("secrets_dir  : %s", PROJECT_ROOT / "secrets")
    logger.debug("========================")
    # --- end startup path snapshot ---

    if config.retention.cleanup_on_start:
        from app.runtime.cleanup import run_startup_cleanup

        run_startup_cleanup(
            logger=logger,
            temp_dir=config.paths.temp_dir,
            logs_dir=config.paths.logs_dir,
            state_dir=config.paths.state_dir,
            temp_max_age_days=config.retention.temp_max_age_days,
            logs_max_age_days=config.retention.logs_max_age_days,
        )

    exit_code = _cmd_run(dry_run=args.dry_run, config=config, logger=logger)
    sys.exit(exit_code)


def _cmd_run(*, dry_run: bool, config: StitcherConfig, logger: logging.Logger) -> int:
    """Главный сценарий: обработать все будущие слоты из Google Sheet."""
    if not _preflight_checks(config, logger):
        return 1

    print("🔵 Проверяю окружение...")

    from app.runtime.ytdlp_updater import maybe_update_ytdlp

    update_status = maybe_update_ytdlp(
        ytdlp_path=config.tools.ytdlp_path,
        state_dir=config.paths.state_dir,
        enabled=config.ytdlp.auto_update,
        interval_days=config.ytdlp.update_check_interval_days,
        logger=logger,
    )
    ytdlp_info = _build_ytdlp_info(update_status)
    codec_label = _build_codec_label(config)

    print("🔵 Читаю таблицу и получаю данные видео...")

    report = _load_future_slots(config, logger)
    if report is None:
        return 1

    jobs = report.jobs
    if not jobs:
        print("Нет будущих слотов для обработки.")
        return 0

    _print_header(codec_label=codec_label, ytdlp_info=ytdlp_info)
    _print_sheet_summary(report)
    _print_jobs_overview(jobs)

    total_slots = len(jobs)
    successful = 0
    failures: list[tuple[str, str]] = []
    started = time.monotonic()

    from app.worker.pipeline import StitchPipeline
    from app.worker.progress import CliProgressTracker

    for index, job in enumerate(jobs, start=1):
        _print_slot_header(index=index, total=total_slots, job=job)

        if dry_run:
            print("  🧪 Dry run: пайплайн не запускался.")
            successful += 1
            _print_separator()
            continue

        pipeline = StitchPipeline(config, progress=CliProgressTracker())
        result = pipeline.run(job)
        if result.success:
            successful += 1
            _print_slot_success(result)
        else:
            error = result.error_message or "Неизвестная ошибка"
            failures.append((_format_slot(job), error))
            print(f"  ❌ Слот завершился с ошибкой: {error}")
        _print_separator()

    total_duration = time.monotonic() - started
    _print_summary(
        total=total_slots,
        successful=successful,
        failures=failures,
        total_duration=total_duration,
        output_dir=config.paths.output_dir,
    )
    return 1 if failures else 0


def _load_future_slots(
    config: StitcherConfig, logger: logging.Logger
) -> SlotLoadReport | None:
    from app.google.auth import GoogleServicesFactory
    from app.google.sheets_client import GoogleSheetsClient
    from app.ingest.youtube_metadata import YtDlpBinaryMetadataFetcher
    from app.input.row_enricher import RowEnricher
    from app.input.sheet_reader import SlotLoader

    credentials_path = PROJECT_ROOT / "secrets" / "credentials.json"
    token_path = PROJECT_ROOT / "secrets" / "token.json"

    try:
        factory = GoogleServicesFactory(
            credentials_path=credentials_path,
            token_path=token_path,
        )
        sheets_service = factory.create_sheets_service()

        fetcher = YtDlpBinaryMetadataFetcher(ytdlp_path=config.tools.ytdlp_path)
        enricher = RowEnricher(metadata_fetcher=fetcher)

        loader = SlotLoader(
            GoogleSheetsClient(sheets_service),
            enricher=enricher,
            config=config,
            sheets_id=config.google.sheets_id,
        )
        return loader.load_future_slots()
    except Exception as exc:
        logger.error("Ошибка загрузки слотов из Google Sheets: %s", exc)
        return None


def _preflight_checks(config: StitcherConfig, logger: logging.Logger) -> bool:
    """Проверить окружение и вывести все ошибки одним блоком."""
    errors = _collect_preflight_errors(config, logger)
    if not errors:
        return True

    print("\n❌ Preflight checks failed:\n")
    for message in errors:
        print(message)
    print("\nИсправьте ошибки выше и запустите снова.")
    return False


def _collect_preflight_errors(
    config: StitcherConfig, logger: logging.Logger
) -> list[str]:
    errors: list[str] = []

    if not config.google.sheets_id:
        errors.append(
            "❌ google.sheets_id не задан в config.toml.\n"
            "   Вставьте ID вашей Google-таблицы в секцию [google]."
        )

    credentials_path = PROJECT_ROOT / "secrets" / "credentials.json"
    if not credentials_path.exists():
        errors.append(
            "❌ OAuth credentials не найдены: secrets/credentials.json\n"
            "   Скачайте Desktop OAuth client из Google Cloud Console."
        )

    if not config.tools.ytdlp_path.exists():
        errors.append(
            f"❌ yt-dlp не найден по пути из config.toml: {config.tools.ytdlp_path}\n"
            "   Проверьте путь [tools].ytdlp_path или скачайте:\n"
            "   https://github.com/yt-dlp/yt-dlp/releases"
        )

    if not config.tools.ffmpeg_path.exists():
        errors.append(
            f"❌ ffmpeg не найден по пути из config.toml: {config.tools.ffmpeg_path}\n"
            "   Проверьте путь [tools].ffmpeg_path или скачайте:\n"
            "   https://www.gyan.dev/ffmpeg/builds/"
        )

    if not config.encoding.gpu_profile.exists():
        errors.append(f"❌ GPU профиль не найден: {config.encoding.gpu_profile}")
    if not config.encoding.cpu_profile.exists():
        errors.append(f"❌ CPU профиль не найден: {config.encoding.cpu_profile}")

    for target in (
        config.paths.temp_dir,
        config.paths.output_dir,
        config.paths.state_dir,
    ):
        try:
            target.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            errors.append(f"❌ Не удалось создать директорию {target}: {exc}")

    import shutil

    try:
        disk = shutil.disk_usage(config.paths.temp_dir)
        one_gb = 1024 * 1024 * 1024
        if disk.free < one_gb:
            logger.warning(
                "Низкое свободное место в temp_dir: %.2f MB",
                disk.free / (1024 * 1024),
            )
    except OSError as exc:
        logger.warning("Не удалось проверить свободное место: %s", exc)

    return errors


def _print_header(*, codec_label: str, ytdlp_info: str) -> None:
    line = "═" * 59
    print(line)
    print("  STITCHER - обработка слотов из Google Sheet")
    print("─" * 59)
    print(f"  yt-dlp  {ytdlp_info}")
    print(f"  кодек   {codec_label}")
    print(line)
    print()


def _build_ytdlp_info(update_status) -> str:
    version = update_status.current_version or "n/a"
    if update_status.current_version is None:
        return version
    if update_status.attempted and update_status.succeeded:
        return f"{version} (обновлено сейчас)"
    if update_status.attempted:
        return f"{version} (обновление не удалось)"
    if update_status.last_check_days_ago is not None:
        return f"{version} (проверено {update_status.last_check_days_ago} дн. назад)"
    return version


def _build_codec_label(config: StitcherConfig) -> str:
    codec = "h264_nvenc"
    bitrate = "10 Mbps"
    try:
        from app.ffmpeg.command_builder import load_profile

        profile_args = load_profile(config.encoding.gpu_profile)
        parsed_codec = _extract_ffmpeg_flag(profile_args, "-c:v")
        parsed_bitrate = _extract_ffmpeg_flag(profile_args, "-b:v")
        if parsed_codec:
            codec = parsed_codec
        if parsed_bitrate:
            bitrate = _human_bitrate(parsed_bitrate)
    except Exception:
        pass

    fallback = "fallback → CPU" if config.encoding.fallback_to_cpu else "fallback off"
    return f"GPU · {codec} · CBR {bitrate}  {fallback}"


def _extract_ffmpeg_flag(args: list[str], flag: str) -> str:
    for idx, item in enumerate(args[:-1]):
        if item == flag:
            return args[idx + 1]
    return ""


def _human_bitrate(raw_value: str) -> str:
    normalized = raw_value.strip().lower()
    if normalized.endswith("m"):
        number = normalized[:-1]
        if number.replace(".", "", 1).isdigit():
            return f"{number} Mbps"
    if normalized.endswith("k"):
        number = normalized[:-1]
        if number.replace(".", "", 1).isdigit():
            return f"{number} Kbps"
    return raw_value


def _print_jobs_overview(jobs: list[StitchJob]) -> None:
    print(f"📋 Определили слоты: {len(jobs)}")
    for index, job in enumerate(jobs, start=1):
        print(f"   {index}. {_format_slot(job)} - {len(job.videos)} видео")
    print()


def _print_sheet_summary(report: SlotLoadReport) -> None:
    lang_parts = ", ".join(
        f"{lang.upper()}={count}"
        for lang, count in sorted(report.rows_by_language.items())
    )
    print(f"  таблица:   {report.total_rows} строк")
    print(f"  дополнено: {report.enriched_rows}/{report.total_rows}")
    print(f"  языки:     {lang_parts}")
    print()


def _print_slot_header(*, index: int, total: int, job: StitchJob) -> None:
    line = "─" * 59
    print(line)
    print(f"▶ Слот {index}/{total}: {_format_slot(job)} ({len(job.videos)} видео)")
    print(line)


def _print_slot_success(result: WorkerResult) -> None:
    if result.output_path is None:
        print("  ✅ Слот готов")
        return

    print(f"  ✅ Слот готов: {result.output_path}")
    print(
        "     Время: "
        f"{_format_duration(result.duration_seconds)} | "
        f"Размер: {_format_size(result.output_size_bytes)}"
    )


def _print_separator() -> None:
    print("─" * 59)
    print()


def _print_summary(
    *,
    total: int,
    successful: int,
    failures: list[tuple[str, str]],
    total_duration: float,
    output_dir: Path,
) -> None:
    line = "═" * 59
    print(line)
    print("  ИТОГО")
    print(line)
    print(f"  ✅ Успешно: {successful} из {total}")
    print(f"  ❌ Ошибки:  {len(failures)}")
    for slot_label, error in failures:
        print(f"     - {slot_label} - {error}")
    print(f"  ⏱  Общее время: {_format_duration(total_duration)}")
    print(f"  📂 Файлы в: {output_dir}")
    print(line)


def _format_slot(job: StitchJob) -> str:
    key = job.slot_key
    date_human = key.date.replace("-", ".")
    time_human = key.time.replace("-", ":")
    return f"{date_human} {time_human} {key.language.upper()}"


def _format_duration(value: float) -> str:
    seconds = max(0, int(round(value)))
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours} ч {minutes} мин {sec} сек"
    if minutes:
        return f"{minutes} мин {sec} сек"
    return f"{sec} сек"


def _format_size(size_bytes: int) -> str:
    if size_bytes <= 0:
        return "0 B"

    size = float(size_bytes)
    units = ["B", "KB", "MB", "GB", "TB"]
    unit = units[0]
    for candidate in units:
        unit = candidate
        if size < 1024.0 or candidate == units[-1]:
            break
        size /= 1024.0

    if unit in {"B", "KB"}:
        return f"{int(size)} {unit}"
    return f"{size:.1f} {unit}"


if __name__ == "__main__":
    main()
