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
        logger.debug("Loading a .env file. Are we not running in Docker?")
    load_dotenv()

bot = Bot(os.getenv("TELEGRAM_TOKEN"), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

adminMessageFilter = F.from_user.id == int(os.getenv("ADMIN_ID"))


async def main() -> None:
    logger.info("Initializing the database...")
    import db
    await db.initialize_connection_pool()

    async with db.shared.pool.acquire() as connection:
        await db.create_chat_config_table(connection)

    logger.info("DB init complete")

    logger.info("Initializing handlers...")
    await bot.delete_webhook(drop_pending_updates=True)

    from handlers import (handle_normal_message, reset_command, settings_command, set_command,
                          start_command, status_command, directsend_command, sql_command)

    dp.message.register(reset_command, Command("reset"))
    dp.message.register(reset_command, Command("clear"))
    dp.message.register(start_command, CommandStart())
    dp.message.register(status_command, Command("status"))
    dp.message.register(settings_command, Command("settings"))
    dp.message.register(set_command, Command("set"))

    dp.message.register(directsend_command, Command("directsend"), adminMessageFilter)
    dp.message.register(sql_command, Command("sql"), adminMessageFilter)

    @dp.message()
    async def on_any_message(message: Message) -> None:
        await handle_normal_message(message)

    logger.info("Starting to receive messages...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
