import asyncio
import os

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from dotenv import load_dotenv
from loguru import logger

if __name__ == "__main__":
    if os.path.exists(".env"):
        load_dotenv()

    logger.add(os.getenv("LOGS_PATH") + "{time}.log", rotation="1 day", backtrace=True, diagnose=True)

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
        await db.drop_orphan_columns(connection)

    logger.info("DB init complete")

    logger.info("Initializing handlers...")
    await bot.delete_webhook(drop_pending_updates=True)

    from utils import BlacklistFilter
    from handlers import (handle_new_message, reset_command, settings_comand, set_command, raw_command,
                          start_command, status_command, directsend_command, sql_command, restart_command,
                          forget_command, replace_command, help_command, system_command, stats_command,
                          handle_message_edit, blacklist_command, unblacklist_command, preset_command, hide_command)

    dp.message.register(directsend_command, Command("directsend"), adminMessageFilter)
    dp.message.register(sql_command, Command("sql"), adminMessageFilter)
    dp.message.register(restart_command, Command("restart"), adminMessageFilter)
    dp.message.register(blacklist_command, Command("blacklist"), adminMessageFilter)
    dp.message.register(unblacklist_command, Command("unblacklist"), adminMessageFilter)

    @dp.message(BlacklistFilter())
    @dp.edited_message(BlacklistFilter())
    async def blacklist_handler(message: Message):
        # Mark blacklisted messages as handled and do nothing lol
        pass

    dp.message.register(reset_command, Command("reset"))
    dp.message.register(reset_command, Command("clear"))
    dp.message.register(start_command, CommandStart())
    dp.message.register(status_command, Command("status"))
    dp.message.register(settings_comand, Command("settings"))
    dp.message.register(set_command, Command("set"))
    dp.message.register(raw_command, Command("raw"))
    dp.message.register(forget_command, Command("forget"))
    dp.message.register(replace_command, Command("replace"))
    dp.message.register(help_command, Command("help"))
    dp.message.register(system_command, Command("system"))
    dp.message.register(stats_command, Command("stats"))
    dp.message.register(preset_command, Command("preset"))
    dp.message.register(hide_command, Command("hide"))

    @dp.message()
    async def on_any_message(message: Message) -> None:
        await handle_new_message(message)

    @dp.edited_message()
    async def on_edited_message(message: Message) -> None:
        await handle_message_edit(message)

    logger.info("Starting to receive messages...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        import uvloop
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        logger.success("Running with uvloop!")
    except ImportError:
        if os.name != "nt":
            if os.path.exists(".env"):
                logger.info("Unable to use uvloop. Please run `pip install uvloop`.")
            else:
                logger.error("Unable to use uvloop. It appears that we're in a container, so this is a bug!")
    asyncio.run(main())
