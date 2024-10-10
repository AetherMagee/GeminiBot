import asyncio
import os
import random
import traceback

import aiohttp
import requests
from aiogram.types import Message
from loguru import logger

import db
from api.prompt import get_system_prompt
from utils import get_message_text, simulate_typing
from .prompts import _prepare_prompt, get_system_messages

bot_id = int(os.getenv("TELEGRAM_TOKEN").split(":")[0])

keys_path = os.getenv("DATA_PATH") + "gemini_api_keys.txt"

if not os.path.exists(keys_path):
    logger.exception(
        f"Couldn't find the key list file in the configured data folder. Please mare sure that {keys_path} exists.")
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
}


def _get_api_key() -> str:
    global api_key_index
    api_key_index += 1
    if api_key_index % 50 == 0:
        logger.debug(f"Error counts: {api_keys_error_counts}")
    return api_keys[api_key_index % len(api_keys)]


async def _call_gemini_api(request_id: int, prompt: list, system_prompt: dict, model_name: str, token_to_use: str,
                           temperature: float, top_p: float, top_k: int, max_output_tokens: int, code_execution: bool,
                           safety_threshold: str):
    headers = {
        "Content-Type": "application/json"
    }

    safety_settings = []
    for safety_setting in ["HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_HARASSMENT",
                           "HARM_CATEGORY_DANGEROUS_CONTENT", "HARM_CATEGORY_CIVIC_INTEGRITY"]:
        safety_settings.append({
            "category": safety_setting,
            "threshold": "BLOCK_" + safety_threshold.upper()
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
                if response.status != 200:
                    logger.error(f"{request_id} | Got an error: {await response.json()}")
                    if attempt != MAX_API_ATTEMPTS:
                        continue
                decoded_response = await response.json()
                return decoded_response


async def _handle_api_response(
        request_id: int,
        response: dict,
        message: Message,
        store: bool,
        show_error_message: bool
) -> str:
    censordict = {
        "HARM_CATEGORY_SEXUALLY_EXPLICIT": "Сексуальный контент",
        "HARM_CATEGORY_HARASSMENT": "Оскорбления",
        "HARM_CATEGORY_HATE_SPEECH": "Разжигание ненависти",
        "HARM_CATEGORY_DANGEROUS_CONTENT": "Опасный контент",
        "LOW": "Низкая",
        "MEDIUM": "Средняя",
        "HIGH": "Высокая"
    }
    errordict = {
        "RESOURCE_EXHAUSTED": "Ежедневный ресурс API закончился. Пожалуйста, попробуйте через несколько часов.",
        "INTERNAL": "Произошел сбой на стороне Google. Пожалуйста, попробуйте через пару минут"
    }

    try:
        if isinstance(response, Exception):
            logger.debug(f"{request_id} | Received an exception: {response}")
            output = "❌ *Произошёл сбой Gemini API.*"
            if show_error_message:
                output += f"\n\n{response}"

            return output

        if "error" in response.keys():
            logger.debug(f"{request_id} | Received an error. Raw response: {response}")

            readable_error = None
            output = "❌ *Произошёл сбой Gemini API.*"
            if "status" in response["error"].keys():
                if response["error"]["status"] in errordict.keys() and show_error_message:
                    output += f"\n\n{errordict[response["error"]["status"]]}"

            if readable_error and show_error_message:
                output += f"\n\n{readable_error}"

            return output

        if "candidates" in response.keys() and response["candidates"][0]["finishReason"] in ["SAFETY", "OTHER"]:
            output = "❌ *Запрос был заблокирован цензурой Gemini API.*"
            output += "\n\n*Уверенность цензуры по категориям:*"
            for category in [detection for detection in response['candidates'][0]['safetyRatings'] if
                             detection['probability'] != "NEGLIGIBLE"]:
                output += f"\n{censordict[category['category']]} - {censordict[category['probability']]} уверенность"

            return output

        if "promptFeedback" in response.keys() and "blockReason" in response["promptFeedback"].keys():
            if response["promptFeedback"]["blockReason"] == "OTHER":
                output = "❌ *Запрос был заблокирован цензурой Gemini API по неизвестным причинам.*"
                output += "\nЕсли ошибка повторяется, попробуйте очистить память - /reset"
                return output

        return response["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        logger.debug(response)
        traceback.print_exc()
        output = "❌ *Непредвиденный сбой обработки ответа Gemini API.*"
        if show_error_message:
            output += f"\n\n{str(e)}"

        return output


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

    additional_sys_messages = await get_system_messages(chat_messages)
    if additional_sys_messages:
        sys_prompt_template += "\n\n<behaviour_rules>\n"
        sys_prompt_template += "\n".join(["- " + text for text in additional_sys_messages])
        sys_prompt_template += "\n</behaviour_rules>"

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
        bool(await db.get_chat_parameter(message.chat.id, "g_code_execution")),
        str(await db.get_chat_parameter(message.chat.id, "g_safety_threshold"))
    ))

    try:
        response = await api_task
    except Exception as api_error:
        traceback.print_exc()
        response = api_error
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
