from aiogram.types import Message
from loguru import logger

import db
from main import bot
from utils import log_command


async def reset_command(message: Message):
    await log_command(message)
    if not message.from_user.id == message.chat.id:
        permission_mode = await db.get_chat_parameter(message.chat.id, "reset_permission")
        if permission_mode == "owner":
            allowed_statuses = ["creator"]
        elif permission_mode == "admins":
            allowed_statuses = ["administrator", "creator"]
        else:
            allowed_statuses = ["member", "administrator", "creator"]

        try:
            member = await bot.get_chat_member(message.chat.id, message.from_user.id)
            if member.status not in allowed_statuses:
                await message.reply(f"❌ <b>Доступ запрещён.</b>")
                return
        except Exception as e:
            logger.warning("No admin rights, assuming sufficient permissions.")
            pass

    await db.mark_all_messages_as_deleted(message.chat.id)
    await message.reply(f"✅ <b>Память очищена.</b>")
