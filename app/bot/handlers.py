"""Telegram handlers для Stitcher бота."""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Optional

from aiogram import Dispatcher, Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.auth import BotAuth
from app.config.settings import EnvConfig, StitcherConfig
from app.google.auth import GoogleServicesFactory
from app.google.sheets_client import GoogleSheetsClient
from app.input.sheet_reader import SlotLoader
from app.models.domain import StitchJob, WorkerProgress, WorkerResult
from app.runtime.logging_config import get_logger
from app.runtime.paths import PROJECT_ROOT
from app.worker.pipeline import StitchPipeline
from app.worker.progress import ProgressTracker

router = Router()

_processing_lock = threading.Lock()
_state_lock = threading.Lock()

_current_progress: WorkerProgress | None = None
_current_slot_key: str | None = None
_current_slot_label: str | None = None
_last_result: WorkerResult | None = None
_cancel_requested: bool = False

_runtime_config: StitcherConfig | None = None
_runtime_env: EnvConfig | None = None
_runtime_logger: logging.Logger | None = None


def set_runtime_context(config: StitcherConfig, env: EnvConfig, logger: logging.Logger) -> None:
    """Сохранить runtime-контекст для handlers."""
    global _runtime_config, _runtime_env, _runtime_logger
    _runtime_config = config
    _runtime_env = env
    _runtime_logger = logger


class TelegramProgressTracker(ProgressTracker):
    """Пишет прогресс в чат отдельными сообщениями."""

    def __init__(
        self,
        bot,
        chat_id: int,
        loop: asyncio.AbstractEventLoop,
        total_slots: int,
        current_slot_index: int,
        slot_label: str,
        status_message_id: int,
    ) -> None:
        self._bot = bot
        self._chat_id = chat_id
        self._loop = loop
        self._total_slots = total_slots
        self._current_slot_index = current_slot_index
        self._slot_label = slot_label
        self._status_message_id = status_message_id

    def on_progress(self, progress: WorkerProgress) -> None:
        global _current_progress
        with _state_lock:
            _current_progress = progress

        message_text = _format_progress_message(progress)

        _print_progress(progress)

        if not message_text:
            return

        asyncio.run_coroutine_threadsafe(
            self._bot.send_message(
                chat_id=self._chat_id,
                text=message_text,
            ),
            self._loop,
        )

    def is_cancel_requested(self) -> bool:
        with _state_lock:
            return _cancel_requested


@router.message(Command("start"))
async def cmd_start(message: types.Message) -> None:
    """Приветствие и краткая инструкция."""
    await message.answer("Привет! Я Stitcher Bot.", reply_markup=_launch_keyboard())


@router.callback_query(lambda c: c.data == "action:launch")
async def on_launch(
    callback: types.CallbackQuery,
    config: StitcherConfig | None = None,
    env: EnvConfig | None = None,
    logger: logging.Logger | None = None,
) -> None:
    """Запустить обработку всех будущих слотов."""
    global _cancel_requested, _current_progress, _current_slot_key, _current_slot_label, _last_result

    runtime = _resolve_runtime(config, env, logger)
    if runtime is None:
        await callback.answer("Внутренняя ошибка", show_alert=True)
        return
    cfg, env_cfg, log = runtime

    if not _is_allowed(env_cfg, callback.from_user.id if callback.from_user else 0):
        await callback.answer("Доступ запрещён", show_alert=True)
        return

    if not _processing_lock.acquire(blocking=False):
        await callback.answer("Уже идёт обработка.", show_alert=True)
        return

    await callback.answer()
    await callback.message.answer("⏳ Читаю таблицу...")

    try:
        jobs = _load_future_jobs(cfg, env_cfg)
    except RuntimeError as exc:
        _processing_lock.release()
        log.error("Ошибка загрузки слотов для бота: %s", exc)
        await callback.message.answer(f"Ошибка загрузки слотов: {exc}")
        return

    if not jobs:
        _processing_lock.release()
        await callback.message.answer("Нет будущих слотов")
        return

    with _state_lock:
        _cancel_requested = False
        _current_progress = None
        _current_slot_key = None
        _current_slot_label = None
        _last_result = None

    await callback.message.answer(f"🎬 Запуск: {len(jobs)} слотов")
    status_message = await callback.message.answer("⚙️ Выполняется...")
    try:
        await callback.bot.pin_chat_message(
            chat_id=callback.message.chat.id,
            message_id=status_message.message_id,
            disable_notification=True,
        )
    except Exception:
        pass

    loop = asyncio.get_running_loop()
    thread = threading.Thread(
        target=_run_all_slots_in_thread,
        kwargs={
            "config": cfg,
            "jobs": jobs,
            "bot": callback.bot,
            "chat_id": callback.message.chat.id,
            "status_message_id": status_message.message_id,
            "loop": loop,
            "logger": log,
        },
        daemon=True,
    )
    thread.start()


@router.message(Command("stop"))
async def cmd_stop(message: types.Message, dispatcher: Dispatcher) -> None:
    runtime = _resolve_runtime(None, None, None)
    if runtime is None:
        await message.answer("Внутренняя ошибка.")
        return
    _, env_cfg, _ = runtime
    if not _is_allowed(env_cfg, message.from_user.id if message.from_user else 0):
        await message.answer("Доступ запрещён.")
        return
    await message.answer("⏹ Останавливаю бота...")
    try:
        await dispatcher.stop_polling()
    except RuntimeError:
        pass


def _resolve_runtime(
    config: StitcherConfig | None,
    env: EnvConfig | None,
    logger: logging.Logger | None,
) -> tuple[StitcherConfig, EnvConfig, logging.Logger] | None:
    resolved_config = config or _runtime_config
    resolved_env = env or _runtime_env
    resolved_logger = logger or _runtime_logger or get_logger(__name__)
    if resolved_config is None or resolved_env is None:
        return None
    return resolved_config, resolved_env, resolved_logger


def _is_allowed(env: EnvConfig, user_id: int) -> bool:
    return BotAuth(env.telegram_user_ids, env.telegram_admin_user_ids).is_allowed(user_id)


def _load_future_jobs(config: StitcherConfig, env: EnvConfig) -> list[StitchJob]:
    factory = GoogleServicesFactory(
        credentials_path=PROJECT_ROOT / "secrets" / "credentials.json",
        token_path=PROJECT_ROOT / "secrets" / "token.json",
    )
    sheets_service = factory.create_sheets_service()
    client = GoogleSheetsClient(sheets_service)
    loader = SlotLoader(client, config=config, sheets_id=env.google_sheets_id)
    return loader.load_future_slots().jobs


def _launch_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="▶️ Запустить", callback_data="action:launch")]
        ]
    )


def _restart_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="▶️ Запустить снова", callback_data="action:launch")]
        ]
    )


def _run_all_slots_in_thread(
    *,
    config: StitcherConfig,
    jobs: list[StitchJob],
    bot,
    chat_id: int,
    status_message_id: int,
    loop: asyncio.AbstractEventLoop,
    logger: logging.Logger,
) -> None:
    """Запустить все слоты подряд в отдельном потоке."""
    global _current_slot_key, _current_slot_label, _current_progress, _last_result, _cancel_requested

    start_total = time.monotonic()
    success_count = 0
    total_slots = len(jobs)

    try:
        for index, job in enumerate(jobs, 1):
            with _state_lock:
                if _cancel_requested:
                    break

            slot_label = _format_slot(job)
            print("\n" + "─" * 59, flush=True)
            print(f"▶ Слот {index}/{total_slots}: {slot_label} ({len(job.videos)} видео)", flush=True)
            print("─" * 59, flush=True)
            _threadsafe_send(
                bot=bot,
                loop=loop,
                chat_id=chat_id,
                text=(
                    "─────────────────────────\n"
                    f"▶ Слот {index}/{total_slots}: {slot_label} ({len(job.videos)} видео)\n"
                    "─────────────────────────"
                ),
                logger=logger,
            )
            _threadsafe_edit_status(
                bot=bot,
                loop=loop,
                chat_id=chat_id,
                message_id=status_message_id,
                text=f"⚙️ Выполняется... Слот {index}/{total_slots}",
                reply_markup=None,
                logger=logger,
            )

            with _state_lock:
                _current_slot_key = str(job.slot_key)
                _current_slot_label = slot_label

            tracker = TelegramProgressTracker(
                bot=bot,
                chat_id=chat_id,
                loop=loop,
                total_slots=total_slots,
                current_slot_index=index,
                slot_label=slot_label,
                status_message_id=status_message_id,
            )
            pipeline = StitchPipeline(config, progress=tracker)
            result = pipeline.run(job)

            with _state_lock:
                _last_result = result

            if result.success:
                success_count += 1
                output_name = result.output_path.name if result.output_path else "unknown.mp4"
                output_label = str(result.output_path) if result.output_path else "unknown.mp4"
                print(f"  ✅ Слот готов: {output_label}", flush=True)
                print(
                    f"     Время: {_format_duration(result.duration_seconds)} | "
                    f"Размер: {_format_size(result.output_size_bytes)}",
                    flush=True,
                )
                print("─" * 59, flush=True)
                print(flush=True)
                _threadsafe_send(
                    bot=bot,
                    loop=loop,
                    chat_id=chat_id,
                    text=(
                        f"✅ Слот готов: {output_name}\n"
                        f"   ⏱ {_format_duration(result.duration_seconds)} · {_format_size(result.output_size_bytes)}"
                    ),
                    logger=logger,
                )
            else:
                error_text = result.error_message or "Неизвестная ошибка"
                print(f"  ❌ Слот завершился с ошибкой: {error_text}", flush=True)
                print("─" * 59, flush=True)
                print(flush=True)
                _threadsafe_send(
                    bot=bot,
                    loop=loop,
                    chat_id=chat_id,
                    text=(
                        f"❌ Ошибка слота {slot_label}\n"
                        f"{error_text}"
                    ),
                    logger=logger,
                )

            if tracker.is_cancel_requested():
                break

        elapsed = time.monotonic() - start_total
        with _state_lock:
            cancelled = _cancel_requested

        if cancelled and success_count < total_slots:
            print(f"\n⛔ Остановлено: {success_count} из {total_slots}", flush=True)
            print(f"⏱ Общее время: {_format_duration(elapsed)}", flush=True)
            summary_text = (
                f"⛔ Остановлено: {success_count} из {total_slots}\n"
                f"⏱ Общее время: {_format_duration(elapsed)}"
            )
        else:
            print(f"\n✅ Готово: {success_count} из {total_slots}", flush=True)
            print(f"⏱ Общее время: {_format_duration(elapsed)}", flush=True)
            summary_text = (
                f"✅ Готово: {success_count} из {total_slots}\n"
                f"⏱ Общее время: {_format_duration(elapsed)}"
            )

        _threadsafe_send(
            bot=bot,
            loop=loop,
            chat_id=chat_id,
            text=summary_text,
            logger=logger,
        )
        _threadsafe_edit_status(
            bot=bot,
            loop=loop,
            chat_id=chat_id,
            message_id=status_message_id,
            text="💤 Готово. Ожидание.",
            reply_markup=_restart_keyboard(),
            logger=logger,
        )
    except Exception as exc:
        logger.exception("Ошибка _run_all_slots_in_thread: %s", exc)
        _threadsafe_send(
            bot=bot,
            loop=loop,
            chat_id=chat_id,
            text=f"❌ Ошибка фонового запуска: {exc}",
            logger=logger,
        )
        _threadsafe_edit_status(
            bot=bot,
            loop=loop,
            chat_id=chat_id,
            message_id=status_message_id,
            text="💤 Готово. Ожидание.",
            reply_markup=_restart_keyboard(),
            logger=logger,
        )
    finally:
        with _state_lock:
            _current_slot_key = None
            _current_slot_label = None
            _current_progress = None
            _cancel_requested = False
        if _processing_lock.locked():
            _processing_lock.release()


def _threadsafe_send(
    *,
    bot,
    loop: asyncio.AbstractEventLoop,
    chat_id: int,
    text: str,
    logger: logging.Logger,
) -> None:
    try:
        future = asyncio.run_coroutine_threadsafe(
            bot.send_message(chat_id=chat_id, text=text),
            loop,
        )
        future.result(timeout=30)
    except Exception as exc:
        logger.debug("send_message failed: %s", exc)


def _threadsafe_edit_status(
    *,
    bot,
    loop: asyncio.AbstractEventLoop,
    chat_id: int,
    message_id: int,
    text: str,
    reply_markup: InlineKeyboardMarkup | None,
    logger: logging.Logger,
) -> None:
    try:
        future = asyncio.run_coroutine_threadsafe(
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=reply_markup,
            ),
            loop,
        )
        future.result(timeout=30)
    except Exception as exc:
        logger.debug("edit_message_text failed: %s", exc)


def _print_progress(progress: WorkerProgress) -> None:
    marker = f"[{progress.current_video}/{progress.total_videos}]"
    if progress.stage == "download":
        print(f"  ⬇️  {marker} {progress.message}", flush=True)
        return
    if progress.stage == "download_done":
        print(f"  ⬇️  {marker} {progress.message}", flush=True)
        return
    if progress.stage == "normalize":
        print(f"  ⚙️  {marker} {progress.message}", flush=True)
        return
    if progress.stage == "normalize_done":
        print(f"  ⚙️  {marker} {progress.message}", flush=True)
        return
    if progress.stage == "concat":
        print(f"  🧩 {progress.message}...", flush=True)
        return
    if progress.stage == "error":
        print(f"  ❌ {progress.message}", flush=True)
        return
    if progress.stage == "done":
        return
    print(f"  • {progress.message}", flush=True)


def _format_progress_message(progress: WorkerProgress) -> str:
    marker = f"[{progress.current_video}/{progress.total_videos}]"
    if progress.stage in {"download", "download_done"}:
        return f"⬇️ {marker} {progress.message}"
    if progress.stage in {"normalize", "normalize_done"}:
        return f"⚙️ {marker} {progress.message}"
    if progress.stage == "concat":
        return f"🧩 {progress.message}..."
    return ""


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


