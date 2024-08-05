from aiogram.types import Message

import db
from utils import log_command
from .shared import is_allowed_to_alter_memory


async def reset_command(message: Message):
    await log_command(message)
    if not await is_allowed_to_alter_memory(message):
        return

    await db.mark_all_messages_as_deleted(message.chat.id)
    await message.reply(f"✅ <b>Память очищена.</b>")
