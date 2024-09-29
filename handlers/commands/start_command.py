import asyncio

from aiogram.enums import ChatAction
from aiogram.types import Message, ReactionTypeEmoji

from main import bot
from utils import log_command
import handlers.commands.settings_command as settings


async def start_command(message: Message):
    await log_command(message)
    if message.from_user.id != message.chat.id:
        await message.react([ReactionTypeEmoji(emoji="👎")])
        return
    await message.answer("👋")
    if message.from_user.id not in settings.pending_sets.keys():
        await bot.send_chat_action(message.chat.id, ChatAction.TYPING)
        await asyncio.sleep(2)
        await message.answer(f"<b>Привет!</b>\n🤖 Я - бот Gemini. Чтобы задать вопрос - просто напиши мне сообщение. <i>(в "
                             f"чате нужно либо ответить на моё сообщение, либо упомянуть меня через @)</i>\n🔔 Проверить "
                             f"статус бота можно <a href=\"https://t.me/aetherlounge/2\">тут</a> или через /status\n💬 "
                             f"Сбросить мою память - /reset или /clear\n❔ Остальные команды можно посмотреть в /help",
                             disable_web_page_preview=True)
    else:
        await settings.handle_private_setting(message)
