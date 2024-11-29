import asyncio
import os
import random
import traceback

import aiohttp
import requests
from aiogram.types import Message
from aiohttp import ContentTypeError
from aiohttp_socks import ProxyConnector
from loguru import logger

import db
from api.prompt import get_system_prompt
from main import bot
from utils import simulate_typing
from .keys import ApiKeyManager, OutOfBillingKeysException, OutOfKeysException
from .prompts import _prepare_prompt, get_system_messages

bot_id = int(os.getenv("TELEGRAM_TOKEN").split(":")[0])

keys_path = os.path.join(os.getenv("DATA_PATH"), "gemini_api_keys.txt")
key_manager = ApiKeyManager(keys_path)

MAX_API_ATTEMPTS = 3
admin_ids_str = os.getenv("ADMIN_IDS", "")
admin_ids = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip()]

ERROR_MESSAGES = {
    "unsupported_file_type": "❌ *Данный тип файлов не поддерживается Gemini API.*",
    "censored": "❌ *Запрос был заблокирован цензурой Gemini API.*",
    "unknown": "❌ *Произошёл сбой Gemini API{0}*",
}


async def _get_api_key(billing_only=False) -> str:
    try:
        key = await key_manager.get_api_key(billing_only=billing_only)
        return key
    except Exception as e:
        logger.error(f"No active {'billing ' if billing_only else ''}API keys available.")
        raise e


async def _call_gemini_api(request_id: int, prompt: list, system_prompt: dict, model_name: str, token_to_use: str,
                           temperature: float, top_p: float, top_k: int, max_output_tokens: int, code_execution: bool,
                           safety_threshold: str, grounding: bool, grounding_threshold: float):
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
        # noinspection PyTypedDict
        data["tools"] = [{'code_execution': {}}]

    if grounding:
        data["tools"] = [{
            "google_search_retrieval": {
                "dynamic_retrieval_config": {
                    "mode": "MODE_DYNAMIC",
                    "dynamic_threshold": grounding_threshold,
                }
            }
        }]

    other_media_present = any("file_data" in part for part in prompt[-1]["parts"])
    if other_media_present:
        logger.info(f"{request_id} | Found other media in prompt, will not rotate keys.")

    if os.getenv("GROUNDING_PROXY_URL") and grounding:
        connector = ProxyConnector.from_url(os.getenv("GROUNDING_PROXY_URL"))
    elif os.getenv("PROXY_URL"):
        connector = ProxyConnector.from_url(os.getenv("PROXY_URL"))
    else:
        connector = None

    async with aiohttp.ClientSession(connector=connector) as session:
        for attempt in range(1, MAX_API_ATTEMPTS + 1):
            if other_media_present:
                key = token_to_use
            else:
                try:
                    key = await key_manager.get_api_key(billing_only=grounding)
                except OutOfBillingKeysException:
                    logger.error(f"{request_id} | No billing API keys available.")
                    return {"error": {"status": "NO_BILLING", "message": "No billing API keys available."}}
                except OutOfKeysException:
                    logger.error(f"{request_id} | No active API keys available.")
                    return {"error": {"status": "RESOURCE_EXHAUSTED", "message": "No active API keys available."}}

            logger.info(f"{request_id} | Generating, attempt {attempt}/{MAX_API_ATTEMPTS} (key ...{key[-6:]})")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"
            async with session.post(url, headers=headers, json=data) as response:
                try:
                    decoded_response = await response.json()
                except ContentTypeError:
                    logger.error(f"{request_id} Response is not JSON, but {response.content_type}")
                    logger.debug(await response.text())
                if response.status != 200:
                    logger.error(f"{request_id} | Got an error: {decoded_response} | Key: ...{key[-6:]}")

                    error_status = decoded_response.get("error", {}).get("status", "")
                    if error_status == "RESOURCE_EXHAUSTED":
                        await key_manager.handle_key_error(
                            key, error_status, is_billing=grounding, admin_ids=admin_ids, bot=bot
                        )
                        if not other_media_present:
                            continue
                    else:
                        await key_manager.handle_key_error(key, error_status, is_billing=grounding)
                        if attempt != MAX_API_ATTEMPTS:
                            continue
                else:
                    return decoded_response

        return decoded_response


async def _handle_api_response(
        request_id: int,
        response: dict,
        message: Message,
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
        "INTERNAL": "Произошел сбой на стороне Google. Пожалуйста, попробуйте через пару минут",
        "UNAVAILABLE": "Выбранная модель недоступна на стороне Gemini API. Возможно, сервера Google перегружены.",
        "NO_BILLING": "Ресурс веб-поиска закончился. Пожалуйста, попробуйте через несколько часов."
    }

    try:
        if isinstance(response, Exception):
            logger.debug(f"{request_id} | Received an exception: {response}")
            output = "❌ *Произошёл неизвестный сбой.*\n\nПожалуйста, попробуйте позже."

            return output

        if "error" in response.keys():
            logger.debug(f"{request_id} | Received an error. Raw response: {response}")

            output = "❌ *Произошёл сбой Gemini API.*"
            if "status" in response["error"].keys():
                if response["error"]["status"] in errordict.keys() and show_error_message:
                    output += f"\n\n{errordict[response['error']['status']]}"

            return output

        if "candidates" in response.keys():
            finish_reason = response.get("candidates")[0].get("finishReason")
            if finish_reason in ["SAFETY", "OTHER"]:
                output = "❌ *Запрос был заблокирован цензурой Gemini API.*"
                output += "\n\n*Уверенность цензуры по категориям:*"
                for category in [detection for detection in response['candidates'][0]['safetyRatings'] if
                                 detection['probability'] != "NEGLIGIBLE"]:
                    output += f"\n{censordict[category['category']]} - {censordict[category['probability']]} уверенность"

                return output

            if finish_reason == "PROHIBITED_CONTENT":
                output = "❌ *Запрос был заблокирован цензурой Gemini API по неизвестным причинам.*"
                output += "\nЕсли ошибка повторяется, попробуйте очистить память - /reset"
                return output

            if finish_reason == "RECITATION":
                output = "❌ *Запрос был заблокирован цензурой Gemini API в связи с тем, что модель начала повторять контент, защищённый авторским правом.*"

                sources = response.get("citationSources")
                if sources and isinstance(sources, list):
                    output += "\n\nПроцитированный контент:\n"
                    for source in sources:
                        output += f"- {source.get('uri')}"

                return output

        if "promptFeedback" in response.keys() and "blockReason" in response["promptFeedback"].keys():
            if response["promptFeedback"]["blockReason"] in ["OTHER", "PROHIBITED_CONTENT"]:
                output = "❌ *Запрос был заблокирован цензурой Gemini API по неизвестным причинам.*"
                output += "\nЕсли ошибка повторяется, попробуйте очистить память - /reset"
                return output

        usage = response.get("usageMetadata")

        if usage:
            try:
                total_tokens = usage['totalTokenCount']
                prompt_tokens = usage.get('promptTokenCount')
                completion_tokens = usage.get('candidatesTokenCount')

                logger.debug(
                    f"{request_id} | Tokens: {total_tokens} total ({prompt_tokens} prompt, {completion_tokens} completion)")

                await db.statistics.log_generation(
                    message.chat.id,
                    message.from_user.id,
                    "google",
                    prompt_tokens,
                    completion_tokens,
                    await db.get_chat_parameter(message.chat.id, "g_model")
                )
            except KeyError:
                logger.warning(f"{request_id} | Failed to process token usage metadata.")
                traceback.print_exc()
                logger.debug(response)

        output = response["candidates"][0]["content"]["parts"][0]["text"].replace("  ", " ")

        grounding_metadata = response["candidates"][0].get("groundingMetadata")
        if grounding_metadata:
            chunks = grounding_metadata.get("groundingChunks")
            queries = grounding_metadata.get("webSearchQueries")

            if chunks or queries:
                def error_prone_len(inp) -> int:
                    try:
                        return len(inp)
                    except TypeError:
                        return 0

                logger.debug(f"{request_id} | Response is grounded. {error_prone_len(chunks)} chunks and {error_prone_len(queries)} queries.")
                output += "\n⎯⎯⎯⎯⎯\n"

            if queries and await db.get_chat_parameter(message.chat.id, "g_web_show_queries"):
                output += "\n"
                output += "*Поисковые запросы:*\n"
                for query in queries:
                    output += f"- _{query}_\n"

            if chunks and await db.get_chat_parameter(message.chat.id, "g_web_show_sources"):
                output += "\n"
                output += "*Источники:*\n"
                for chunk in chunks:
                    output += f"- [{chunk['web']['title']}]({chunk['web']['uri']})\n"

        return output
    except Exception as e:
        logger.debug(response)
        traceback.print_exc()
        output = "❌ *Непредвиденный сбой обработки ответа Gemini API.*"
        if show_error_message:
            output += f"\n\n{str(e)}"

        return output


async def generate_response(message: Message) -> str:
    request_id = random.randint(100000, 999999)
    token = await _get_api_key()

    logger.info(
        f"R: {request_id} | U: {message.from_user.id} ({message.from_user.first_name}) | C: {message.chat.id} ({message.chat.title}) | M: {message.message_id}"
    )

    chat_messages = await db.get_messages(message.chat.id)
    typing_task = asyncio.create_task(simulate_typing(message.chat.id))

    prompt = await _prepare_prompt(message, chat_messages, token)
    if not prompt:
        return ERROR_MESSAGES["censored"]

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
        str(await db.get_chat_parameter(message.chat.id, "g_safety_threshold")),
        bool(await db.get_chat_parameter(message.chat.id, "g_web_search")),
        float(await db.get_chat_parameter(message.chat.id, "g_web_threshold"))
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
        return await _handle_api_response(request_id, response, message, show_error_message)
    except Exception as e:
        logger.error(f"{request_id} | Failed to generate message. Exception: {e}")
        error_message = (": " + str(e)) if show_error_message else ""
        return ERROR_MESSAGES['unknown'].format(error_message)


async def count_tokens_for_chat(trigger_message: Message) -> int:
    key = await _get_api_key()

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
        async with session.post(url, headers=headers, json=data, proxy=os.getenv("PROXY_URL")) as response:
            decoded_response = await response.json()

    if not decoded_response:
        return 0

    try:
        return decoded_response["totalTokens"]
    except Exception as e:
        logger.error(f"Failed to count tokens: {e}")
        return 0


def get_available_models():
    logger.info("GOOGLE | Getting available models...")
    model_list = []
    try:
        active_keys = key_manager.get_active_keys()
        if not active_keys:
            logger.error("No active API keys available to fetch models.")
            return model_list
        key = active_keys[0]
        
        proxy = os.getenv("PROXY_URL")

        if proxy:
            if proxy.startswith("socks"):
                proto = "https"
            else:
                proto = proxy.split("://")[0]
            proxies = {proto: proxy}
        else:
            proxies = {}
        response = requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={key}",
                                proxies=proxies)
        decoded_response = response.json()

        hidden = ["bison", "aqa", "embedding", "gecko"]
        for model in decoded_response.get("models", []):
            if not any(hidden_word in model["name"] for hidden_word in hidden):
                model_list.append(model["name"].replace("models/", ""))
    except Exception as e:
        logger.error(f"Failed to get available models. Exception: {e}")
        traceback.print_exc()

    return model_list
