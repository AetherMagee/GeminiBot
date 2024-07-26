from aiogram.types import Message

import db


async def reset_command(message: Message):
    await db.mark_all_messages_as_deleted(message.chat.id)
    await message.reply("✅ *Память очищена.*")
