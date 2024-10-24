import os

from aiogram import html
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message, ReactionTypeEmoji
from loguru import logger
from more_itertools import sliced

import api
import api.openai
import db
import handlers.commands.settings_command as settings
from main import ADMIN_IDS, bot
from utils import get_message_text
from .commands.shared import is_allowed_to_alter_memory

bot_id = int(os.getenv("TELEGRAM_TOKEN").split(":")[0])
bot_username = os.getenv("BOT_USERNAME")
FEEDBACK_TARGET_ID = int(os.getenv("FEEDBACK_TARGET_ID"))


async def meets_endpoint_requirements(message: Message, endpoint: str) -> bool:
    endpoint_requirements = {
        "google": [message.text, message.caption, message.video, message.document, message.sticker,
                   message.photo, message.voice, message.audio, message.video_note],
        "openai": [message.text, message.caption, message.photo]
    }

    if endpoint in endpoint_requirements.keys():
        return any(endpoint_requirements[endpoint])
    else:
        logger.error(f"Unknown endpoint {endpoint}")
        return False


async def should_generate_response(message: Message) -> bool:
    if message.reply_to_message and message.reply_to_message.from_user.id == bot_id:  # If replying to us
        return True

    if f"@{bot_username}" in await get_message_text(message):  # If mentioned
        return True

    if message.chat.id == message.from_user.id:  # If in DMs
        return True

    return False


async def check_token_limit(message: Message) -> bool:
    token_limit = await db.get_chat_parameter(message.chat.id, "token_limit")
    if token_limit:
        current_tokens = await api.openai.count_tokens(message.chat.id)
        if current_tokens > token_limit:
            token_action = await db.get_chat_parameter(message.chat.id, "token_limit_action")
            if token_action == "warn":
                await message.reply(f"⚠️ <b>Токенов больше, чем лимит</b> <i>({current_tokens} > {token_limit})</i>")
            elif token_action == "block":
                await message.reply(f"❌ <b>Запрос заблокирован: Токенов больше, чем лимит</b> "
                                    f"<i>({current_tokens} > {token_limit})</i>")
                return True
    return False


async def handle_forced_response(message: Message) -> bool:
    forced_response = await get_message_text(message, "after_forced")
    if forced_response:
        if await is_allowed_to_alter_memory(message):
            our_message = await message.reply(forced_response)
            await db.save_our_message(message, forced_response, our_message.message_id)
        else:
            await message.reply("❌ <b>У вас нет доступа к этой команде.</b>")
        return True
    return False


async def handle_response(message: Message, output: str) -> None:
    try:
        our_message = await message.reply(output, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Failed to send response: {e}")
        try:
            our_message = await message.reply(html.quote(output))
        except TelegramBadRequest:
            if len(output) > 2000:
                chunks = list(sliced(output, 1900))
                logger.warning(
                    f"Failed to send {len(output)} symbols at once, sending it in {len(chunks)} chunks instead...")
                for index, chunk in enumerate(chunks):
                    try:
                        logger.debug(f"Sending chunk {index} to {message.chat.id}")
                        our_message = await message.reply(chunk, parse_mode=ParseMode.MARKDOWN)
                    except TelegramBadRequest:
                        try:
                            our_message = await message.reply(html.quote(chunk))
                        except TelegramBadRequest:
                            logger.error(f"Failed to send chunk {index} to {message.chat.id}")
                            logger.debug(chunk)
            else:
                our_message = await message.reply(f"❌ <b>Telegram почему-то не принимает ответ бота.</b>")
    finally:
        if output.startswith("❌"):
            output = ""
        await db.save_our_message(message, output, our_message.message_id)


async def try_handle_feedback_response(message: Message) -> bool:
    if not FEEDBACK_TARGET_ID:
        return False

    if message.chat.id != FEEDBACK_TARGET_ID:
        return False

    if message.from_user.id not in ADMIN_IDS:
        return False

    if not message.reply_to_message:
        return False

    if message.reply_to_message.from_user.id != bot_id:
        return False

    try:
        target_chatid, target_userid, target_name, target_message_id = message.reply_to_message.text.split("\n")[
            1].split(" | ")
    except Exception as e:
        logger.error(f"Failed to handle feedback response: {e}")
        return True

    text_to_send = f"👋 <b>{target_name}</b>, вот ответ администратора бота на ваш запрос:\n\n"
    text_to_send += message.text

    try:
        await bot.send_message(target_chatid, text_to_send, reply_to_message_id=target_message_id)
    except TelegramBadRequest:
        await bot.send_message(target_chatid, text_to_send)

    await message.react([ReactionTypeEmoji(emoji="👌")])

    return True


async def handle_new_message(message: Message) -> None:
    if message.from_user.id in settings.pending_sets and message.from_user.id == message.chat.id:
        await settings.handle_private_setting(message)
        return

    if await try_handle_feedback_response(message):
        return

    endpoint = await db.get_chat_parameter(message.chat.id, "endpoint")

    if not await meets_endpoint_requirements(message, endpoint):
        return

    await db.save_aiogram_message(message)

    if not await should_generate_response(message):
        return

    if await check_token_limit(message):
        return

    if await handle_forced_response(message):
        return

    output = await api.generate_response(message, endpoint)

    await handle_response(message, output)


async def handle_message_edit(message: Message) -> None:
    await db.replace_message(message.chat.id, message.message_id, message.text)
