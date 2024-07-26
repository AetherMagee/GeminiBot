import os

from aiogram.types import Message
from loguru import logger

import api.google
import db
import utils

bot_id = int(os.getenv("TELEGRAM_TOKEN").split(":")[0])
bot_username = os.getenv("BOT_USERNAME")  # This is not the best but I have no idea how do dynamically load it without spamming bot.get_me() requests


async def handle_normal_message(message: Message) -> None:
    if not message.text and not message.caption and not message.photo and not message.audio and not message.video:
        return

    await db.save_aiogram_message(message)

    if (message.reply_to_message and message.reply_to_message.from_user.id == bot_id) \
            or (message.text and f"@{bot_username}" in message.text)\
            or message.chat.id == message.from_user.id:
        output = await api.google.generate_response(message)
        try:
            await message.reply(output)
        except Exception as e:
            logger.error(f"Failed to send response: {e}")
            text = await utils.no_markdown(output)
            await message.reply(text)
            await db.save_system_message(
                message.chat.id,
                "Your previous message was not accepted by the endpoint due to bad formatting. The user sees your "
                "message WITHOUT your formatting. Do better next time. Keep the formatting rules in mind.")

