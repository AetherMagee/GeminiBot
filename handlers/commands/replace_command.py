import os
import traceback

from aiogram.types import Message, ReactionTypeEmoji

import db
from handlers.commands.shared import is_allowed_to_alter_memory
from utils import log_command

bot_id = int(os.getenv("TELEGRAM_TOKEN").split(":")[0])


async def replace_command(message: Message) -> None:
    await log_command(message)

    if not await is_allowed_to_alter_memory(message):
        await message.reply("❌ <b>У вас нет доступа к этой команде.</b>")
        return

    if not message.reply_to_message:
        await message.reply("❌ <b>Использование команды: <i>/replace [текст]</i> ответом на сообщение, текст которого "
                            "нужно отредактировать.")
        return

    target = message.reply_to_message.message_id
    new_text = message.text.split(" ", maxsplit=1)[1]

    result = await db.replace_message(message.chat.id, target, new_text)

    if result:
        await message.react([ReactionTypeEmoji(emoji="👌")])
        if message.reply_to_message.from_user.id == bot_id:
            try:
                await message.reply_to_message.edit_text(new_text)
            except Exception:
                traceback.print_exc()
                return
    else:
        await message.reply("❌ <b>Не удалось изменить сообщение в памяти.</b>")
