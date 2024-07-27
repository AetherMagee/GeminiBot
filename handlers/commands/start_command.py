import asyncio

from aiogram.enums import ChatAction
from aiogram.types import Message
from loguru import logger

from main import bot


async def start_command(message: Message):
    logger.info(f"Start command from {message.from_user.id}")
    await message.reply("👋")
    await bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    await asyncio.sleep(2)
    await message.reply(f"*Привет!*\n🤖 Я - бот Gemini. Чтобы задать вопрос - просто напиши мне сообщение. _(в "
                        f"чате нужно либо ответить на моё сообщение, либо упомянуть меня через @)_\n🔔 Проверить "
                        f"статус бота можно [тут](https://t.me/aetherlounge/2) или через /status\n💬 Сбросить мою "
                        f"память - /reset или /clear",
                        disable_web_page_preview=True)
