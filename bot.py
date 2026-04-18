"""Stitcher Telegram Bot — точка входа."""
from __future__ import annotations

import asyncio
import sys

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.handlers import router, set_runtime_context
from app.config.config_loader import load_config
from app.config.settings import EnvConfig
from app.runtime.env_loader import load_env_config, load_env_file
from app.runtime.logging_config import get_console_logger, get_logger, setup_bot_logging


def main() -> None:
    """Запуск Telegram-бота Stitcher."""
    load_env_file()

    setup_bot_logging()
    logger = get_logger(__name__)

    try:
        config = load_config()
    except RuntimeError as exc:
        logger.error("Ошибка загрузки конфигурации: %s", exc)
        sys.exit(1)

    env = load_env_config()
    if not env.telegram_bot_token:
        logger.error("TELEGRAM_BOT_TOKEN не задан в secrets/.env")
        sys.exit(1)

    bot = Bot(token=env.telegram_bot_token)
    dp = Dispatcher()
    dp.include_router(router)

    set_runtime_context(config, env, logger)
    dp["config"] = config
    dp["env"] = env
    dp["logger"] = logger

    logger.info("Stitcher Bot запущен (mode=%s).", "polling")
    asyncio.run(_run_polling(dp=dp, bot=bot, chat_id=env.telegram_chat_id, env=env))


async def _run_polling(*, dp: Dispatcher, bot: Bot, chat_id: str, env: EnvConfig) -> None:
    logger = get_logger(__name__)
    console = get_console_logger()
    commands = [
        BotCommand(command="start", description="Начать работу"),
        BotCommand(command="stop", description="Остановить бота"),
    ]
    try:
        await bot.set_my_commands(commands)
        logger.info("Команды бота зарегистрированы: %d", len(commands))
    except Exception as exc:
        logger.warning("Не удалось зарегистрировать команды бота: %s", exc)

    try:
        bot_info = await bot.get_me()
        username = bot_info.username or ""
    except Exception as exc:
        logger.warning("Не удалось получить данные бота: %s", exc)
        username = ""

    admin_count = len(env.telegram_admin_user_ids)
    user_count = len(env.telegram_user_ids)
    console.info("✅ Бот готов к работе")
    if username:
        console.info("🤖 @%s", username)
    console.info("👤 Админы: %d | Пользователи: %d", admin_count, user_count)
    if chat_id.strip():
        console.info("💬 Чат: %s", chat_id)

    if chat_id.strip():
        try:
            await bot.send_message(
                chat_id=chat_id,
                text="🎬 Stitcher Bot запущен\n/stop — остановить бота",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="▶️ Запустить",
                                callback_data="action:launch",
                            )
                        ]
                    ]
                ),
            )
        except Exception:
            pass

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


async def _oneshot(dp: Dispatcher, bot: Bot) -> None:
    """Обработать pending updates и остановиться."""
    updates = await bot.get_updates(timeout=0)
    for update in updates:
        await dp.feed_update(bot, update)
    await bot.session.close()


if __name__ == "__main__":
    main()
