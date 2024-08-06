import os

from aiogram.types import Message, ReactionTypeEmoji

import db
from utils import log_command
from .shared import is_allowed_to_alter_memory

bot_id = int(os.getenv("TELEGRAM_TOKEN").split(":")[0])


async def forget_command(message: Message) -> None:
    await log_command(message)

    if not await is_allowed_to_alter_memory(message):
        await message.reply("❌ <b>У вас нет доступа к этой команде.</b>")
        return
    if not message.reply_to_message:
        await message.reply("❌ <b>Используйте команду ответом на сообщение, которое нужно удалить из памяти бота..</b>")
        return

    successful = await db.attempt_delete_message(message.chat.id, message.reply_to_message.message_id)
    if successful:
        await message.react([ReactionTypeEmoji(emoji="👌")])
    else:
        await message.reply("❌ <b>Не удалось удалить сообщение из памяти.</b>")
