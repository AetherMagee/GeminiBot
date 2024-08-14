import os

from aiogram import html
from aiogram.enums import ParseMode
from aiogram.types import Message
from loguru import logger

import api
import api.openai
import db
from api.google import ERROR_MESSAGES
from utils import get_message_text
from .commands.shared import is_allowed_to_alter_memory

bot_id = int(os.getenv("TELEGRAM_TOKEN").split(":")[0])
bot_username = os.getenv("BOT_USERNAME")


async def handle_new_message(message: Message) -> None:
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

        token_limit = await db.get_chat_parameter(message.chat.id, "token_limit")
        token_warning: Message = None
        if token_limit:
            current_token_count = await api.openai.count_tokens(message.chat.id)  # Using Tiktoken as it's faster
            if current_token_count > token_limit:
                token_limit_action = await db.get_chat_parameter(message.chat.id, "token_limit_action")
                if token_limit_action == "warn":
                    token_warning = await message.reply(f"⚠️ <b>Количество токенов превышает заданный лимит</b> "
                                                        f"<i>({current_token_count} > {token_limit})</i>")
                elif token_limit_action == "block":
                    await message.reply(f"❌ <b>Запрос заблокирован: Количество токенов превышает заданный лимит</b> "
                                        f"<i>({current_token_count} > {token_limit})</i>")
                    return

        output = await api.generate_response(message)
        try:
            our_message = await message.reply(output, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Failed to send response: {e}")
            try:
                our_message = await message.reply(html.quote(output))
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
            if token_warning:
                await token_warning.delete()


async def handle_message_edit(message: Message) -> None:
    logger.info(f"Updating message {message.message_id} in {message.chat.id}")
    await db.replace_message(message.chat.id, message.message_id, message.text)