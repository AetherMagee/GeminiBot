import os

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message, ReactionTypeEmoji

from utils import log_command

bot_id = int(os.getenv("TELEGRAM_TOKEN").split(":")[0])


async def hide_command(message: Message):
    await log_command(message)

    if not message.reply_to_message:
        await message.react([ReactionTypeEmoji(emoji="🤔")])
        return

    if message.reply_to_message.from_user.id == bot_id:
        await message.reply_to_message.delete()

    try:
        await message.delete()
    except TelegramBadRequest:
        await message.react([ReactionTypeEmoji(emoji="👌")])
