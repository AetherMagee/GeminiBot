import asyncio
import os
import sys
from datetime import datetime

import aiogram
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from dotenv import load_dotenv
from loguru import logger

if __name__ == "__main__":
    if os.path.exists(".env"):
        load_dotenv()

    logger.add(
        os.getenv("LOGS_PATH") + "{time}.log",
        rotation="4 hours",
        backtrace=True,
        diagnose=True,
        enqueue=True,
        retention="7 days"
    )

proxy = os.getenv("PROXY_URL")
session = AiohttpSession(proxy=proxy)

bot = Bot(os.getenv("TELEGRAM_TOKEN"),
          default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True), session=session)
dp = Dispatcher()

ADMIN_IDS = [int(admin_id) for admin_id in os.getenv("ADMIN_IDS").split(", ")]
adminMessageFilter = F.from_user.id.in_(ADMIN_IDS)

start_time = datetime.now()


async def main() -> None:
    logger.info("Initializing the database...")
    import db
    await db.initialize_connection_pool()

    async with db.shared.pool.acquire() as conn:
        # Create tables
        await db.create_messages_table(conn)
        await db.create_chat_config_table(conn)
        await db.create_blacklist_table(conn)
        await db.create_statistics_table(conn)

        # Migrate if necessary
        await db.migrate_statistics_table(conn)
        await db.migrate_messages_tables(conn)

        await db.drop_orphan_columns(conn)

    logger.info("DB init complete")

    logger.info("Initializing handlers...")
    if os.path.exists(os.getenv("DATA_PATH") + "drop_pending_updates"):
        logger.warning("Dropping pending updates...")
        await bot.delete_webhook(drop_pending_updates=True)

    from utils import BlacklistFilter
    from handlers import (handle_new_message, reset_command, settings_comand, set_command, prune_command,
                          start_command, status_command, directsend_command, sql_command, restart_command,
                          forget_command, replace_command, help_command, system_command, feedback_command,
                          stats_command, handle_message_edit, blacklist_command,
                          unblacklist_command, preset_command, hide_command, dropcaches_command)

    dp.message.register(directsend_command, Command("directsend"), adminMessageFilter)
    dp.message.register(sql_command, Command("sql"), adminMessageFilter)
    dp.message.register(restart_command, Command("restart"), adminMessageFilter)
    dp.message.register(blacklist_command, Command("blacklist"), adminMessageFilter)
    dp.message.register(unblacklist_command, Command("unblacklist"), adminMessageFilter)
    dp.message.register(prune_command, Command("prune"), adminMessageFilter)
    dp.message.register(stats_command, Command("stats"), adminMessageFilter)
    dp.message.register(dropcaches_command, Command("dropcaches"), adminMessageFilter)

    dp.message.register(status_command, Command("status"))

    @dp.message(BlacklistFilter())
    @dp.edited_message(BlacklistFilter())
    async def blacklist_handler(message: Message):
        # Mark blacklisted messages as handled and do nothing lol
        pass

    dp.message.register(reset_command, Command("reset"))
    dp.message.register(reset_command, Command("clear"))
    dp.message.register(start_command, CommandStart())
    dp.message.register(settings_comand, Command("settings"))
    dp.message.register(set_command, Command("set"))
    dp.message.register(forget_command, Command("forget"))
    dp.message.register(replace_command, Command("replace"))
    dp.message.register(help_command, Command("help"))
    dp.message.register(system_command, Command("system"))
    dp.message.register(preset_command, Command("preset"))
    dp.message.register(hide_command, Command("hide"))
    dp.message.register(feedback_command, Command("feedback"))

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
        if sys.platform != 'win32':
            if os.path.exists(".env"):
                logger.info("Unable to use uvloop. Please run `pip install uvloop`.")
            else:
                logger.error("Unable to use uvloop. It appears that we're in a container, so this is a bug!")
        else:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    logger.debug(f"Running Python {sys.version_info.major}.{sys.version_info.minor}, aiogram {aiogram.__version__}")
    asyncio.run(main())
