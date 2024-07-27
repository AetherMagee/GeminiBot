import asyncio
import os
import random
from typing import Union

import google.generativeai as genai
from aiogram.types import Message
from asyncpg import Record
from google.generativeai.types import AsyncGenerateContentResponse
from loguru import logger

import db
from utils import simulate_typing
from .media import get_other_media, get_photo

bot_id = int(os.getenv("TELEGRAM_TOKEN").split(":")[0])
api_keys = os.getenv("GEMINI_API_KEYS").split(", ")
api_key_index = 0
with open(os.getenv("DEFAULT_SYSTEM_PROMPT_FILE_PATH"), "r") as f:
    default_prompt = f.read()


async def _get_api_key() -> str:
    global api_key_index
    api_key_index += 1
    return api_keys[api_key_index % len(api_keys)]


async def _call_gemini_api(request_id: int, prompt: list, max_attempts: int, token: str) -> Union[
    AsyncGenerateContentResponse, None]:
    safety = {
        "SEXUALLY_EXPLICIT": "block_none",
        "HARASSMENT": "block_none",
        "HATE_SPEECH": "block_none",
        "DANGEROUS": "block_none",
    }

    attempts = 0
    while attempts < max_attempts:
        attempts += 1
        logger.debug(f"{request_id} | Generating, attempt {attempts}")

        model = genai.GenerativeModel("gemini-1.5-pro-latest")

        try:
            response = await model.generate_content_async(prompt, safety_settings=safety)
            return response
        except Exception as e:
            logger.error(f"{request_id} | Error \"{e}\" on key: {token}")

    return None


async def _format_message_for_prompt(message: Record) -> str:
    result = ""

    if message["sender_id"] == bot_id:
        result += "You: "
    else:
        if message["sender_username"] == message["sender_name"]:
            name = message["sender_name"]
        else:
            name = f"{message['sender_name']} ({message['sender_username']})"
        result += f"{name}: "

    if message["reply_to_message_id"]:
        result += f"[REPLY TO: {message['reply_to_message_trimmed_text']}] "

    if message["text"]:
        result += message["text"]
    else:
        result += "*No text*"
    return result


async def generate_response(message: Message) -> str:
    request_id = random.randint(100000, 999999)
    token = await _get_api_key()
    genai.configure(api_key=token)

    logger.debug(
        f"RID: {request_id} | UID: {message.from_user.id} | CID: {message.chat.id} | MID: {message.message_id}")

    prompt_mode = await db.get_chat_parameter(message.chat.id, "system_prompt_mode")
    if prompt_mode == 0:
        prompt = default_prompt
    else:
        prompt = await db.get_chat_parameter(message.chat.id, "custom_system_prompt")

    chat_messages = await db.get_messages(message.chat.id)
    all_messages_list = [await _format_message_for_prompt(message) for message in chat_messages]
    all_messages = "\n".join(all_messages_list)

    photos = [await get_photo(message)]
    if not photos[0]:
        photos = []
    additional_media = await get_other_media(message, token)

    prompt = prompt.format(
        chat_type="direct message (DM)" if message.from_user.id == message.chat.id else "group",
        chat_title=f" called {message.chat.title}" if message.from_user.id != message.chat.id else f" with {message.from_user.first_name}",
        all_messages=all_messages,
        target_message=all_messages_list[-1],
        media_warning="Your target message contains one or several media files. They have been attached with this "
                      "request. Make sure to handle it properly: If it's a video or an image start your response with "
                      "\"This image contains\" or \"This video contains\" and then describe it in as much detail as "
                      "you possibly can, for your own sake - you won't be able to see it again, "
                      "and the User may have additional questions related to the media. If the user speaks to you in "
                      "a language other than English, for example, Russian, adapt. Start your response with \"Это "
                      "изображение содержит\" instead. If it's audio and sounds like a voice message - do what the "
                      "user asks you to do from it." if photos or additional_media else None
    )

    prompt = [prompt] + photos + additional_media

    api_task = asyncio.create_task(_call_gemini_api(
        request_id,
        prompt,
        await db.get_chat_parameter(message.chat.id, "max_attempts"),
        token
    ))
    typing_task = asyncio.create_task(simulate_typing(message.chat.id))

    response = await api_task
    typing_task.cancel()
    # I have no idea how and why but ok.
    try:
        await typing_task
    except asyncio.CancelledError:
        pass

    logger.info(f"{request_id} | Complete")

    try:
        output = response.text
        await db.save_our_message(message, output)
        return output
    except Exception as e:
        logger.error(f"{request_id} | Failed to generate message. Exception: {e}")
        try:
            if response.prompt_feedback.block_reason:
                logger.debug(f"{request_id} | Block reason: {response.prompt_feedback}")
                return "❌ *Запрос был заблокирован цензурой Gemini API.*"
            else:
                return "❌ *Произошел сбой Gemini API.*"
        except Exception:
            return "❌ *Произошел сбой Gemini API.*"


async def count_tokens_for_chat(chat_id: int) -> int:
    key = await _get_api_key()
    genai.configure(api_key=key)
    model = genai.GenerativeModel("gemini-1.5-pro-latest")

    chat_messages = await db.get_messages(chat_id)
    all_messages_list = [await _format_message_for_prompt(message) for message in chat_messages]
    all_messages = "\n".join(all_messages_list)

    try:
        token_count = (await model.count_tokens_async(all_messages)).total_tokens
    except Exception as e:
        logger.error(f"{chat_id} | Failed to count tokens. Exception: {e}")
        token_count = 0

    return token_count
