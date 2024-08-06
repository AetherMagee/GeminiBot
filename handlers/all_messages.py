import os

from aiogram.enums import ParseMode
from aiogram.types import Message
from loguru import logger

import api
import db
from api.google import ERROR_MESSAGES
from utils import get_message_text, no_markdown
from .commands.shared import is_allowed_to_alter_memory

bot_id = int(os.getenv("TELEGRAM_TOKEN").split(":")[0])
bot_username = os.getenv("BOT_USERNAME")


async def handle_normal_message(message: Message) -> None:
    # TODO: Blacklisting

    requirement_pass = False
    for requirement in [message.text, message.caption, message.video, message.document, message.sticker,
                        message.photo, message.voice, message.audio, message.video_note]:
        if requirement:
            requirement_pass = True
            break
    if not requirement_pass:
        return

    text = await get_message_text(message)

    if text.startswith("/"):
        return

    await db.save_aiogram_message(message)

    if (message.reply_to_message and message.reply_to_message.from_user.id == bot_id) \
            or f"@{bot_username}" in text \
            or message.chat.id == message.from_user.id:

        forced = await get_message_text(message, "after_forced")
        if forced:
            if await is_allowed_to_alter_memory(message):
                our_message = await message.reply(forced)
                await db.save_our_message(message, forced, our_message.message_id)
                return
            else:
                return

        if await db.get_chat_parameter(message.chat.id, "endpoint") == "openai" and text == "":
            return

        output = await api.generate_response(message)
        try:
            our_message = await message.reply(output, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Failed to send response: {e}")
            try:
                output = await no_markdown(output)
                our_message = await message.reply(output)
                await db.save_system_message(
                    message.chat.id,
                    "Your previous message was not accepted by the endpoint due to bad formatting. The user sees your "
                    "message WITHOUT your formatting. Do better next time. Keep the formatting rules in mind.")
            except Exception:
                our_message = await message.reply(f"❌ <b>Telegram не принимает ответ "
                                                  f"бота.</b> <i>({len(output)} символов)</i>")
        finally:
            if output.startswith("❌"):
                output = ERROR_MESSAGES["system_failure"]
            await db.save_our_message(message, output, our_message.message_id)
