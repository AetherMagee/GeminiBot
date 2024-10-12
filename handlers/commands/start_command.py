import asyncio

from aiogram.enums import ChatAction
from aiogram.types import Message, ReactionTypeEmoji

import handlers.commands.settings_command as settings
from main import bot
from utils import log_command


async def start_command(message: Message):
    await log_command(message)
    if message.from_user.id != message.chat.id:
        await message.react([ReactionTypeEmoji(emoji="👎")])
        return
    await message.answer("👋")
    if message.from_user.id not in settings.pending_sets.keys():
        await bot.send_chat_action(message.chat.id, ChatAction.TYPING)
        await asyncio.sleep(2)
        text = """<b>Привет!</b>
        
🤖 <b>Я - многофункциональный ИИ-бот.</b> Умею работать с текстом, картинками и даже больше!
❔ Чтобы <b>задать мне вопрос</b> или пообщаться, просто напиши сюда в чат.
👥 Можешь даже <b>добавить меня в свою группу</b>, чтобы я мог помогать всем! Чтобы обратиться ко мне, достаточно упомянуть меня.

⚙️ У меня есть множество <b>команд и параметров</b>. Их можно посмотреть в /help и /settings соответственно.
💬 Если хочешь быстро сменить тему - можешь <b>очистить мою память</b> командой /reset

📝 Учти, что я <b>сохраняю в свою память каждое сообщение</b>, что вижу. Старайся не отправлять сюда конфиденциальную информацию.
🤔 Я всё ещё учусь и могу допускать ошибки. Пожалуйста, не верь всему слепо.
"""
        await message.answer(text, disable_web_page_preview=True)
    else:
        await settings.handle_private_setting(message)
