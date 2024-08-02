import asyncio
import os
import random
from typing import Union

import google.generativeai as genai
from aiogram.types import Message
from asyncpg import Record
from google.api_core.exceptions import InvalidArgument
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


def _get_api_key() -> str:
    global api_key_index
    api_key_index += 1
    return api_keys[api_key_index % len(api_keys)]


def get_available_models() -> list:
    logger.info("Getting available models...")
    genai.configure(api_key=_get_api_key())
    models = genai.list_models()
    model_list = []
    hidden = ["bison", "aqa", "embedding", "gecko"]
    for model in models:
        if not any(hidden_word in model.name for hidden_word in hidden):
            model_list.append(model.name.replace("models/", ""))

    return model_list


async def _call_gemini_api(request_id: int, prompt: list, max_attempts: int, token: str, model_name: str) -> Union[
    AsyncGenerateContentResponse, str, None]:
    safety = {
        "SEXUALLY_EXPLICIT": "block_none",
        "HARASSMENT": "block_none",
        "HATE_SPEECH": "block_none",
        "DANGEROUS": "block_none",
    }

    logger.debug(f"{request_id} | Using model {model_name}")

    attempts = 0
    while attempts < max_attempts:
        attempts += 1
        logger.debug(f"{request_id} | Generating, attempt {attempts}")

        model = genai.GenerativeModel(model_name)

        try:
            response = await model.generate_content_async(prompt, safety_settings=safety)
            return response
        except InvalidArgument:
            return "❌ <b>Такие файлы не поддерживаются Gemini API.</b>"
        except Exception as e:
            logger.error(f"{request_id} | Error \"{e}\" on key: {token}")
            if attempts == max_attempts - 1:
                return e

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
    token = _get_api_key()
    genai.configure(api_key=token)

    logger.debug(
        f"RID: {request_id} | UID: {message.from_user.id} | CID: {message.chat.id} | MID: {message.message_id}")

    chat_messages = await db.get_messages(message.chat.id)
    all_messages_list = [await _format_message_for_prompt(message) for message in chat_messages]
    all_messages = "\n".join(all_messages_list)

    typing_task = asyncio.create_task(simulate_typing(message.chat.id))

    photos = [await get_photo(message)]
    if not photos[0]:
        photos = []
    additional_media = await get_other_media(message, token)

    if not message.text.startswith("/raw"):
        prompt = default_prompt
        prompt = prompt.format(
            chat_type="direct message (DM)" if message.from_user.id == message.chat.id else "group",
            chat_title=f" called {message.chat.title}" if message.from_user.id != message.chat.id else f" with {message.from_user.first_name}",
            all_messages=all_messages,
            target_message=all_messages_list[-1],
            media_warning="\n- Your target message or a message related to it happen to contain some media files. "
                          "They have been attached for your analysis. When working with these files, follow these "
                          "rules: 1) If you are sure that it wasn't described before in the chat history, "
                          "describe PERFECTLY and AS THOROUGHLY AS POSSIBLE whatever is contained in the mediafile. "
                          "You won't be able to see it again, and the User might ask additional questions, "
                          "so these notes will also function as your future guidelines. When describing, start with "
                          "\"This <media_type> contains\" in the User's language. For example, when working with an "
                          "image and talking in a Russian-speaking chat, start with \"Это изображение содержит\". 2) "
                          "Perform what the user asks you to do. So, if it's an image and the User wants the text on "
                          "it - say it. If it's an audio resembling a voice message - transcript it as accurately as "
                          "possible, then handle it as a normal message directed at you. So, if it has any "
                          "instructions for you - execute them. Otherwise, ask the User what they want exactly." if
            photos or additional_media else None
        )
    else:
        prompt = message.text.replace("/raw ", "", 1)

    prompt = [prompt] + photos + additional_media
    model_name = await db.get_chat_parameter(message.chat.id, "model")

    api_task = asyncio.create_task(_call_gemini_api(
        request_id,
        prompt,
        3,
        token,
        model_name
    ))

    response = await api_task
    typing_task.cancel()
    # I have no idea how and why but ok.
    try:
        await typing_task
    except asyncio.CancelledError:
        pass

    logger.info(f"{request_id} | Complete")

    show_error_message = await db.get_chat_parameter(message.chat.id, "show_error_messages")

    try:
        if isinstance(response, AsyncGenerateContentResponse):
            output = response.text.replace("  ", " ")
        elif isinstance(response, str):
            output = response
        elif isinstance(response, Exception):
            error_message = (": " + str(response)) if show_error_message else ""
            output = f"❌ *Произошел сбой Gemini API{error_message}*"
        else:
            logger.error(f"{request_id} | What? {type(response)}")
            await db.save_system_message(message.chat.id, "Your response was supposed to be here, but you failed "
                                                          "to reply for some reason. Be better next time.")
            output = "❌ *Произошел сбой Gemini API.*"
        if not output.startswith("❌"):
            await db.save_our_message(message, output)
        return output
    except Exception as e:
        logger.error(f"{request_id} | Failed to generate message. Exception: {e}")
        try:
            if response.prompt_feedback.block_reason:
                logger.debug(f"{request_id} | Block reason: {response.prompt_feedback}")
                await db.save_system_message(message.chat.id, "Your response was supposed to be here, but you failed "
                                                              "to reply for some reason. Be better next time.")
                return "❌ *Запрос был заблокирован цензурой Gemini API.*"
            else:
                await db.save_system_message(message.chat.id,
                                             "Your response was supposed to be here, but you failed to reply for some "
                                             "reason. Be better next time.")
                error_message = (": " + str(e)) if show_error_message else ""
                return f"❌ *Произошел сбой Gemini API{error_message}.*"
        except Exception:
            await db.save_system_message(message.chat.id,
                                         "Your response was supposed to be here, but you failed to reply for some "
                                         "reason. Be better next time.")
            return "❌ *Произошел сбой Gemini API.*"


async def count_tokens_for_chat(messages_list: list, model_name: str) -> int:
    key = _get_api_key()
    genai.configure(api_key=key)
    model = genai.GenerativeModel(model_name)

    all_messages_list = [await _format_message_for_prompt(message) for message in messages_list]
    all_messages = "\n".join(all_messages_list)

    try:
        token_count = (await model.count_tokens_async(all_messages)).total_tokens
    except Exception as e:
        logger.error(f"Failed to count tokens. Exception: {e}")
        token_count = 0

    return token_count
