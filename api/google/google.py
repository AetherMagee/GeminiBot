import asyncio
import os
import random
import traceback
from typing import Dict, List

import aiohttp
import requests
from aiogram.types import Message
from asyncpg import Record
from loguru import logger

import db
from api.prompt import get_system_prompt
from utils import get_message_text, simulate_typing
from .media import get_other_media, get_photo

bot_id = int(os.getenv("TELEGRAM_TOKEN").split(":")[0])

keys_path = os.getenv("DATA_PATH") + "gemini_api_keys.txt"

if not os.path.exists(keys_path):
    logger.exception(f"Couldn't find the key list file in the configured data folder. Please mare sure that {keys_path} exists.")
    exit(1)

api_keys = []
with open(keys_path, "r") as f:
    characters_to_remove = [" ", "\n"]
    for line in f.readlines():
        if line.startswith("AIza"):
            for character in characters_to_remove:
                line = line.replace(character, "")
            api_keys.append(line.strip())
random.shuffle(api_keys)
logger.info(f"Loaded {len(api_keys)} API keys")

api_key_index = 0
api_keys_error_counts = {}

MAX_API_ATTEMPTS = 3
ERROR_MESSAGES = {
    "unsupported_file_type": "❌ *Данный тип файлов не поддерживается Gemini API.*",
    "censored": "❌ *Запрос был заблокирован цензурой Gemini API.*",
    "unknown": "❌ *Произошёл сбой Gemini API{0}*",
    "system_failure": "Your response was supposed to be here, but you failed to reply for some reason. Be better next "
                      "time."
}


def _get_api_key() -> str:
    global api_key_index
    api_key_index += 1
    if api_key_index % 50 == 0:
        logger.debug(f"Error counts: {api_keys_error_counts}")
    return api_keys[api_key_index % len(api_keys)]


async def _call_gemini_api(request_id: int, prompt: list, system_prompt: dict, model_name: str, token_to_use: str,
                           temperature: float, top_p: float, top_k: int, max_output_tokens: int, code_execution: bool):
    headers = {
        "Content-Type": "application/json"
    }

    safety_settings = []
    for safety_setting in ["HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_HARASSMENT",
                           "HARM_CATEGORY_DANGEROUS_CONTENT", "HARM_CATEGORY_CIVIC_INTEGRITY"]:
        safety_settings.append({
            "category": safety_setting,
            "threshold": "BLOCK_NONE"
        })

    data = {
        "system_instruction": system_prompt,
        "contents": prompt,
        "safetySettings": safety_settings,
        "generationConfig": {
            "temperature": temperature,
            "topP": top_p,
            "topK": top_k,
            "maxOutputTokens": max_output_tokens,
        }
    }
    if code_execution:
        data["tools"] = [{'code_execution': {}}]

    other_media_present = False
    for part in prompt[-1]["parts"]:
        if "file_data" in part.keys():
            other_media_present = True
            logger.info(f"{request_id} | Found other media in prompt, will not rotate keys.")
            break

    async with aiohttp.ClientSession() as session:
        for attempt in range(1, MAX_API_ATTEMPTS + 1):
            if other_media_present:
                key = token_to_use
            else:
                key = _get_api_key()
            logger.info(f"{request_id} | Generating, attempt {attempt}/{MAX_API_ATTEMPTS}")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"
            async with session.post(url, headers=headers, json=data) as response:
                decoded_response = await response.json()
                logger.debug(decoded_response)
                return decoded_response


async def format_message_for_prompt(message: Record, add_reply_to: bool = True) -> str:
    result = ""

    if message["sender_id"] == bot_id:
        result += "You: "
    else:
        if message["sender_username"] == message["sender_name"]:
            name = message["sender_name"]
        else:
            name = f"{message['sender_name']} ({message['sender_username']})"
        result += f"{name}: "

    if message["reply_to_message_id"] and add_reply_to:
        result += f"[REPLY TO: {message['reply_to_message_trimmed_text']}] "

    if message["text"]:
        result += message["text"]
    else:
        result += "*No text*"
    return result


async def _prepare_prompt(trigger_message: Message, chat_messages: List[Record], token: str) -> List[Dict]:
    result = []

    user_message_buffer = []
    for index, message in enumerate(chat_messages):
        if message["sender_id"] not in [0, 727]:
            user_message_buffer.append(await format_message_for_prompt(message))
            if index == len(chat_messages) - 1:
                result.append({
                    "role": "user",
                    "parts": [{
                        "text": "\n".join(user_message_buffer)
                    }],
                })
                break
        else:
            if user_message_buffer:
                result.append({
                    "role": "user",
                    "parts": [{
                        "text": "\n".join(user_message_buffer)
                    }],
                })
                user_message_buffer.clear()
            # if message["sender_id"] == 727:
            #     result.append({
            #         "role": "system",
            #         "parts": [{
            #             "text": (await format_message_for_prompt(message, False)).replace("SYSTEM: ", "", 1)
            #         }]
            #     })
            if message["sender_id"] == 0:
                result.append({
                    "role": "model",
                    "parts": [{
                        "text": (await format_message_for_prompt(message, False)).replace("You: ", "", 1)
                    }]
                })
            else:
                logger.error("How did we get here?")
                logger.debug(index)
                logger.debug(message)

    image = await get_photo(
        trigger_message,
        chat_messages,
        "base64"
    )
    other_file = await get_other_media(trigger_message, token, chat_messages)

    if image:
        index = -1
        last_message = result[index]

        parts = last_message["parts"]
        parts.append({
            "inline_data": {
                "mime_type": "image/jpeg",
                "data": image
            }
        })

        result[-1] = {
            "role": last_message["role"],
            "parts": parts
        }

    elif other_file:
        index = -1
        last_message = result[index]
        parts = last_message["parts"]

        parts.append({
            "file_data": {
                "mime_type": other_file["mime_type"],
                "file_uri": other_file["uri"]
            }
        })

        result[-1] = {
            "role": last_message["role"],
            "parts": parts
        }

    return result


async def _handle_api_response(
        request_id: int,
        response: dict,
        message: Message,
        store: bool,
        show_error_message: bool
) -> str:
    try:
        return response["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        traceback.print_exc()
        output = "❌ *Непредвиденный сбой обработки ответа Gemini API.*"
        if show_error_message:
            output += f"\n\n{str(e)}"


async def generate_response(message: Message) -> str:
    request_id = random.randint(100000, 999999)
    token = _get_api_key()
    message_text = await get_message_text(message)

    logger.info(
        f"RID: {request_id} | UID: {message.from_user.id} | CID: {message.chat.id} | MID: {message.message_id}"
    )

    chat_messages = await db.get_messages(message.chat.id)
    typing_task = asyncio.create_task(simulate_typing(message.chat.id))

    if not message_text.startswith("/raw"):
        prompt = await _prepare_prompt(message, chat_messages, token)
        if not prompt:
            return ERROR_MESSAGES["censored"]

        store = True
    else:
        prompt = [message_text.replace("/raw ", "", 1)]
        store = "--dont-store" not in prompt[0]
        if not store:
            prompt[0] = prompt[0].replace("--dont-store", "", 1)

    model_name = await db.get_chat_parameter(message.chat.id, "g_model")

    chat_type = "direct message (DM)" if message.from_user.id == message.chat.id else "group"
    chat_title = f" called {message.chat.title}" if message.from_user.id != message.chat.id else f" with {message.from_user.first_name}"

    sys_prompt_template = await get_system_prompt()
    system_prompt = {
        "parts": {
            "text": sys_prompt_template.format(
                chat_title=chat_title,
                chat_type=chat_type,
            )
        }
    }

    api_task = asyncio.create_task(_call_gemini_api(
        request_id,
        prompt,
        system_prompt,
        model_name,
        token,
        float(await db.get_chat_parameter(message.chat.id, "g_temperature")),
        float(await db.get_chat_parameter(message.chat.id, "g_top_p")),
        int(await db.get_chat_parameter(message.chat.id, "g_top_k")),
        int(await db.get_chat_parameter(message.chat.id, "max_output_tokens")),
        bool(await db.get_chat_parameter(message.chat.id, "g_code_execution"))
    ))

    response = await api_task
    typing_task.cancel()
    try:
        await typing_task
    except asyncio.CancelledError:
        pass

    logger.info(f"{request_id} | Complete")

    show_error_message = await db.get_chat_parameter(message.chat.id, "show_error_messages")

    try:
        return await _handle_api_response(request_id, response, message, store, show_error_message)
    except Exception as e:
        logger.error(f"{request_id} | Failed to generate message. Exception: {e}")
        if store:
            await db.save_system_message(message.chat.id, ERROR_MESSAGES['system_failure'])
        error_message = (": " + str(e)) if show_error_message else ""
        return ERROR_MESSAGES['unknown'].format(error_message)


async def count_tokens_for_chat(trigger_message: Message) -> int:
    key = _get_api_key()

    prompt = await _prepare_prompt(trigger_message, await db.get_messages(trigger_message.chat.id), key)

    headers = {
        "Content-Type": "application/json"
    }
    data = {
        "contents": prompt
    }
    model = await db.get_chat_parameter(trigger_message.chat.id, "g_model")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:countTokens?key={key}"

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=data) as response:
            decoded_response = await response.json()

    if not decoded_response:
        return 0

    try:
        return decoded_response["totalTokens"]
    except Exception as e:
        logger.error(f"Failed to count tokens: {e}")
        return 0


def get_available_models() -> list:
    logger.info("GOOGLE | Getting available models...")
    model_list = []
    try:
        response = requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={_get_api_key()}")
        decoded_response = response.json()

        hidden = ["bison", "aqa", "embedding", "gecko"]
        for model in decoded_response["models"]:
            if not any(hidden_word in model["name"] for hidden_word in hidden):
                model_list.append(model["name"].replace("models/", ""))
    except Exception as e:
        logger.error(f"Failed to get available models. Exception: {e}")

    return model_list
