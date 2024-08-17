import asyncio
import os

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from dotenv import load_dotenv
from loguru import logger

if os.path.exists(".env"):
    if __name__ == "__main__":
        logger.error("A .env file is present. This indicates that the bot is not running in Docker.")
        logger.error("The bot currently has hardcoded paths that make running in Docker mandatory.")
        logger.error("Shutting down...")
        exit(1)
    load_dotenv()

bot = Bot(os.getenv("TELEGRAM_TOKEN"), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

ADMIN_IDS = [int(admin_id) for admin_id in os.getenv("ADMIN_IDS").split(", ")]
adminMessageFilter = F.from_user.id.in_(ADMIN_IDS)


async def main() -> None:
    logger.info("Initializing the database...")
    import db
    await db.initialize_connection_pool()

    async with db.shared.pool.acquire() as connection:
        await db.create_chat_config_table(connection)
        await db.create_blacklist_table(connection)

    logger.info("DB init complete")

    logger.info("Initializing handlers...")
    await bot.delete_webhook(drop_pending_updates=True)

    from utils import BlacklistFilter
    from handlers import (handle_new_message, reset_command, settings_command, set_command, raw_command,
                          start_command, status_command, directsend_command, sql_command, restart_command,
                          forget_command, replace_command, help_command, system_command, stats_command,
                          handle_message_edit, blacklist_command, unblacklist_command)

    dp.message.register(reset_command, Command("reset"), BlacklistFilter())
    dp.message.register(reset_command, Command("clear"), BlacklistFilter())
    dp.message.register(start_command, CommandStart(), BlacklistFilter())
    dp.message.register(status_command, Command("status"), BlacklistFilter())
    dp.message.register(settings_command, Command("settings"), BlacklistFilter())
    dp.message.register(set_command, Command("set"), BlacklistFilter())
    dp.message.register(raw_command, Command("raw"), BlacklistFilter())
    dp.message.register(forget_command, Command("forget"), BlacklistFilter())
    dp.message.register(replace_command, Command("replace"), BlacklistFilter())
    dp.message.register(help_command, Command("help"), BlacklistFilter())
    dp.message.register(system_command, Command("system"), BlacklistFilter())
    dp.message.register(stats_command, Command("stats"), BlacklistFilter())

    dp.message.register(directsend_command, Command("directsend"), adminMessageFilter)
    dp.message.register(sql_command, Command("sql"), adminMessageFilter)
    dp.message.register(restart_command, Command("restart"), adminMessageFilter)
    dp.message.register(blacklist_command, Command("blacklist"), adminMessageFilter)
    dp.message.register(unblacklist_command, Command("unblacklist"), adminMessageFilter)

    @dp.message(BlacklistFilter())
    async def on_any_message(message: Message) -> None:
        await handle_new_message(message)

    @dp.edited_message(BlacklistFilter())
    async def on_edited_message(message: Message) -> None:
        await handle_message_edit(message)

    logger.info("Starting to receive messages...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
