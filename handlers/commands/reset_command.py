from aiogram.types import Message, ReactionTypeEmoji

import db
from utils import log_command
from .shared import is_allowed_to_alter_memory


async def reset_command(message: Message):
    await log_command(message)
    if not await is_allowed_to_alter_memory(message):
        await message.reply("❌ <b>У вас нет доступа к этой команде.</b>")
        return

    await db.mark_all_messages_as_deleted(message.chat.id)
    await message.react([ReactionTypeEmoji(emoji="👌")])
