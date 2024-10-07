from aiogram.types import Message, ReactionTypeEmoji

import db
from handlers.commands.shared import is_allowed_to_alter_memory
from utils import get_message_text, log_command


async def system_command(message: Message) -> None:
    await log_command(message)
    if not await is_allowed_to_alter_memory(message):
        await message.reply("❌ <b>У вас нет доступа к этой команде.</b>")
        return

    if await db.get_chat_parameter(message.chat.id, "endpoint") != "openai":
        await message.reply("❌ <b>Эта команда пока что доступна только на эндпоинтах OpenAI.</b>")
        return

    text = await get_message_text(message)
    try:
        text = text.split(" ", maxsplit=1)[1]
    except IndexError:
        await message.reply("❌ <b>Использование команды:</b> <i>/system [текст]</i>")
        return

    await db.save_system_message(message.chat.id, text)
    await message.react([ReactionTypeEmoji(emoji="👌")])
