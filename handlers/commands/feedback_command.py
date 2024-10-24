import asyncio
import os
import traceback

from aiogram.types import Message, ReactionTypeEmoji

from main import bot
from utils import get_message_text

FEEDBACK_TARGET_ID = os.getenv('FEEDBACK_TARGET_ID')
lock: dict = {}


async def feedback_command(message: Message):
    if not FEEDBACK_TARGET_ID:
        return

    lock.setdefault(message.chat.id, False)
    if lock[message.chat.id]:
        await message.reply("❌ <b>Подождите немного перед повторным запуском этой команды.</b>")
        return

    lock[message.chat.id] = True

    try:
        text = await get_message_text(message)
        if len(text.split()) < 2:
            await message.reply("❌ <b>Использование команды: </b> <i>/feedback [текст]</i>")
            return

        text = text.replace("/feedback ", "", 1)
        text_to_send = "👋 <b>Новый вызов /feedback</b>"
        text_to_send += f"\n{message.chat.id} | {message.from_user.id} | {message.from_user.first_name.replace('|', '')} | {message.message_id}\n"
        text_to_send += f"{text}"

        await bot.send_message(FEEDBACK_TARGET_ID, text_to_send)
        await message.react([ReactionTypeEmoji(emoji="👌")])
    except Exception as e:
        await message.reply("❌ <b>Сбой отправки.</b>")
        traceback.print_exc()
        return
    finally:
        await asyncio.sleep(60)
        lock[message.chat.id] = False
