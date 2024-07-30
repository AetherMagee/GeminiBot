import os

from aiogram import html
from aiogram.types import Message
from loguru import logger

import api.google
import db

bot_id = int(os.getenv("TELEGRAM_TOKEN").split(":")[0])
bot_username = os.getenv("BOT_USERNAME")


async def handle_normal_message(message: Message) -> None:
    requirement_pass = False
    for requirement in [message.text, message.caption, message.video, message.document,
                        message.photo, message.voice, message.audio, message.video_note]:
        if requirement:
            requirement_pass = True
            break
    if not requirement_pass:
        return

    if message.text:
        text = message.text
    elif message.caption:
        text = message.caption
    else:
        text = ""

    if text.startswith("/"):
        return

    await db.save_aiogram_message(message)

    if (message.reply_to_message and message.reply_to_message.from_user.id == bot_id) \
            or f"@{bot_username}" in text \
            or message.chat.id == message.from_user.id:
        output = await api.google.generate_response(message)
        try:
            await message.reply(output)
        except Exception as e:
            logger.error(f"Failed to send response: {e}")
            output = html.quote(output)
            try:
                await message.reply(output)
                await db.save_system_message(
                    message.chat.id,
                    "Your previous message was not accepted by the endpoint due to bad formatting. The user sees your "
                    "message WITHOUT your formatting. Do better next time. Keep the formatting rules in mind.")
            except Exception as e:
                await message.reply("❌ <b>Gemini API выдало какой то пиздец с которым я даже не знаю как работать, "
                                    "поэтому вместо него держите это сообщение об ошибке. </b>")
