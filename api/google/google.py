import os
import random
import time
import traceback
from typing import List

import aiohttp
from aiogram.types import Message
from aiohttp import ContentTypeError
from aiohttp_socks import ProxyConnector
from async_lru import alru_cache
from asyncpg import Record
from loguru import logger

import db
from api.prompt import get_system_prompt
from utils import simulate_typing
from .keys import ApiKeyManager, OutOfBillingKeysException, OutOfKeysException
from .prompts import _prepare_prompt, get_system_messages

bot_id = int(os.getenv("TELEGRAM_TOKEN").split(":")[0])

keys_path = os.path.join(os.getenv("DATA_PATH"), "gemini_api_keys.txt")
key_manager = ApiKeyManager(keys_path)

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


async def _call_gemini_api(request_id: int, trigger_message: Message, messages: List[Record], system_prompt: dict,
                           model_name: str, temperature: float, top_p: float, top_k: int, max_output_tokens: int,
                           code_execution: bool, safety_threshold: str, grounding: bool, grounding_threshold: float):
    if os.getenv("GROUNDING_PROXY_URL") and grounding:
        connector = ProxyConnector.from_url(os.getenv("GROUNDING_PROXY_URL"))
    elif os.getenv("PROXY_URL"):
        connector = ProxyConnector.from_url(os.getenv("PROXY_URL"))
    else:
        connector = None

    async with aiohttp.ClientSession(connector=connector) as session:

        MAX_API_ATTEMPTS = int(os.getenv("MAX_KEY_ROTATION_ATTEMPTS"))

        censor_evade_attempts = 0
        bad_key_attempts = 0
        generating = True
        while generating:
            try:
                key = await key_manager.get_api_key(billing_only=grounding)
            except OutOfBillingKeysException:
                logger.error(f"{request_id} | No billing API keys available.")
                return {"error": {"status": "NO_BILLING", "message": "No billing API keys available."}}
            except OutOfKeysException:
                logger.error(f"{request_id} | No active API keys available.")
                return {"error": {"status": "RESOURCE_EXHAUSTED", "message": "No active API keys available."}}

            prompt = await _prepare_prompt(trigger_message, messages, key)

            safety_settings = []
            for safety_setting in ["HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_HATE_SPEECH",
                                   "HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_DANGEROUS_CONTENT",
                                   "HARM_CATEGORY_CIVIC_INTEGRITY"]:
                safety_settings.append({
                    "category": safety_setting,
                    "threshold": "BLOCK_" + safety_threshold.upper()
                })

            data = {
                "contents": prompt,
                "safetySettings": safety_settings,
                "generationConfig": {
                    "temperature": temperature,
                    "topP": top_p,
                    "topK": top_k,
                    "maxOutputTokens": max_output_tokens,
                }
            }
            if system_prompt:
                data["system_instruction"] = system_prompt

            if code_execution:
                # noinspection PyTypedDict
                data["tools"] = [{'code_execution': {}}]

            if grounding:
                if "2.0" in model_name:
                    # noinspection PyTypedDict
                    data["tools"] = [{
                        "googleSearch": {}
                    }]
                else:
                    data["tools"] = [{
                        "googleSearchRetrieval": {
                            "dynamic_retrieval_config": {
                                "mode": "MODE_DYNAMIC",
                                "dynamic_threshold": grounding_threshold,
                            }
                        }
                    }]

            headers = {
                "Content-Type": "application/json",
                "x-goog-api-key": key
            }

            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
            logger.info(f"{request_id} | Generating: key ...{key[-6:]}, model {model_name}")
            async with session.post(url, headers=headers, json=data) as response:
                try:
                    decoded_response = await response.json()
                except ContentTypeError:
                    logger.error(f"{request_id} Response is not JSON, but {response.content_type}")
                    logger.debug(await response.text())
                    return {'error': {'status': 'INTERNAL', 'message': 'Response is not JSON.'}}

                if response.status != 200:
                    error = decoded_response.get('error', {})
                    status_code = error.get('status', '')
                    if status_code:
                        logger.error(f"{request_id} | Got an error: {status_code} | Key: ...{key[-6:]}")
                        if status_code == "RESOURCE_EXHAUSTED":
                            logger.warning(f"{request_id} | Key {key[-6:]} is exhausted")
                            key_manager.timeout_key(key, grounding)

                            bad_key_attempts += 1
                            if bad_key_attempts <= MAX_API_ATTEMPTS:
                                continue
                        if status_code == "INVALID_ARGUMENT":
                            retry = False
                            for detail in error.get('details', []):
                                reason = detail.get('reason', '')
                                if reason == 'API_KEY_INVALID':
                                    key_manager.remove_key_permanently(key, grounding)

                                    bad_key_attempts += 1
                                    if bad_key_attempts <= MAX_API_ATTEMPTS:
                                        retry = True
                            if retry:
                                continue
                    else:
                        logger.error(f"Unknown error: {decoded_response}")

                if decoded_response.get("promptFeedback", {}).get("blockReason", "") in ["OTHER", "PROHIBITED_CONTENT"]:
                    logger.warning(f"{request_id} | Got censored for no apparent reason")

                    censor_evade_attempts += 1
                    if censor_evade_attempts <= 3:
                        continue

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
        "NO_BILLING": "Ресурс веб-поиска закончился. Пожалуйста, попробуйте через несколько часов.",
        "INVALID_ARGUMENT": "В API был отправлен неверный параметр."
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
                status = response["error"]["status"]
                if status in errordict.keys() and show_error_message:
                    output += f"\n\n{errordict[response['error']['status']]}"

                non_default_model = await db.get_chat_parameter(message.chat.id, "g_model") == "gemini-1.5-pro-latest"
                grounding_enabled = await db.get_chat_parameter(message.chat.id, "g_web_search")
                if status == "INVALID_ARGUMENT" and grounding_enabled and non_default_model:
                    output += f"\n\nПопробуйте переключиться на стандартную _gemini-1.5-pro-latest_: `/set g_model gemini-1.5-pro-latest`"

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
                prompt_tokens = usage.get('promptTokenCount', 0)
                completion_tokens = usage.get('candidatesTokenCount', 0)

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
                logger.exception(f"{request_id} | Failed to process token usage metadata.")
        else:
            logger.warning(f"{request_id} | No token usage metadata.")

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

            non_default_model = await db.get_chat_parameter(message.chat.id, "g_model")
            if "thinking" in non_default_model and len(response["candidates"][0]["content"]["parts"]) > 1:
                part = -1  # use the last part since the first one is reasoning
            else:
                part = 0

            output = response["candidates"][0]["content"]["parts"][part]["text"].replace("  ", " ")

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

                    logger.debug(
                        f"{request_id} | Response is grounded. {error_prone_len(chunks)} chunks and {error_prone_len(queries)} queries.")
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

            if part == -1 and await db.get_chat_parameter(message.chat.id, "g_show_thinking"):
                output += "\n⎯⎯⎯⎯⎯\n\n💭 "
                output += response["candidates"][0]["content"]["parts"][0]["text"].replace("  ", " ")


        else:
            logger.warning(f"{request_id} | No candidates in response: {response}")
            output = "❌ *Gemini API не вернул никакого ответа.*\nБот, скорее всего, перегружен. Попробуйте снова через пару минут."

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

    logger.info(
        f"R: {request_id} | U: {message.from_user.id} ({message.from_user.first_name}) | C: {message.chat.id} ({message.chat.title}) | M: {message.message_id}"
    )

    chat_messages = await db.get_messages(message.chat.id)

    model_name = await db.get_chat_parameter(message.chat.id, "g_model")

    chat_type = "direct message (DM)" if message.from_user.id == message.chat.id else "group"
    chat_title = f" called {message.chat.title}" if message.from_user.id != message.chat.id else f" with {message.from_user.first_name}"

    if await db.get_chat_parameter(message.chat.id, "add_system_prompt") and await db.get_chat_parameter(
            message.chat.id, "add_system_messages"):
        sys_prompt_template = await get_system_prompt()
        sys_prompt_template = sys_prompt_template.format(
            chat_title=chat_title,
            chat_type=chat_type,
        )

        if await db.get_chat_parameter(message.chat.id, "add_system_messages"):
            additional_sys_messages = await get_system_messages(chat_messages)
            if additional_sys_messages:
                sys_prompt_template += "\n\n<behaviour_rules>\n"
                sys_prompt_template += "\n".join(["- " + text for text in additional_sys_messages])
                sys_prompt_template += "\n</behaviour_rules>"

        system_prompt = {
            "parts": {
                "text": sys_prompt_template
            }
        }
    else:
        system_prompt = None

    gen_start_time = time.perf_counter()

    async with simulate_typing(message.chat.id):
        try:
            response = await _call_gemini_api(
                request_id,
                message,
                chat_messages,
                system_prompt,
                model_name,
                float(await db.get_chat_parameter(message.chat.id, "g_temperature")),
                float(await db.get_chat_parameter(message.chat.id, "g_top_p")),
                int(await db.get_chat_parameter(message.chat.id, "g_top_k")),
                int(await db.get_chat_parameter(message.chat.id, "max_output_tokens")),
                bool(await db.get_chat_parameter(message.chat.id, "g_code_execution")),
                str(await db.get_chat_parameter(message.chat.id, "g_safety_threshold")),
                bool(await db.get_chat_parameter(message.chat.id, "g_web_search")),
                float(await db.get_chat_parameter(message.chat.id, "g_web_threshold"))
            )
        except Exception as api_error:
            traceback.print_exc()
            response = api_error

    gen_end_time = time.perf_counter()
    gen_timedelta = gen_end_time - gen_start_time

    logger.info(f"{request_id} | Complete | {round(gen_timedelta, 2)}s")

    show_error_message = await db.get_chat_parameter(message.chat.id, "show_error_messages")

    try:
        return await _handle_api_response(request_id, response, message, show_error_message)
    except Exception as e:
        logger.error(f"{request_id} | Failed to generate message. Exception: {e}")
        error_message = (": " + str(e)) if show_error_message else ""
        return ERROR_MESSAGES['unknown'].format(error_message)


async def count_tokens_for_chat(trigger_message: Message) -> int:
    key = await _get_api_key()

    try:
        prompt = await _prepare_prompt(trigger_message, await db.get_messages(trigger_message.chat.id), key)
    except IndexError:
        return 0

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
        logger.warning(f"Failed to count tokens: {e}")
        return 0


@alru_cache(ttl=300)
async def _get_available_models() -> List[str]:
    logger.info("GOOGLE | Getting available models...")
    model_list = []
    try:
        key = await key_manager.get_api_key()

        proxy = os.getenv("PROXY_URL")
        connector = ProxyConnector.from_url(proxy) if proxy else None

        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(
                    f"https://generativelanguage.googleapis.com/v1beta/models?key={key}",
                    timeout=10
            ) as response:
                response.raise_for_status()
                decoded_response = await response.json()

        hidden = ["bison", "aqa", "embedding", "gecko"]
        for model in decoded_response.get("models", []):
            if not any(hidden_word in model["name"] for hidden_word in hidden):
                model_list.append(model["name"].replace("models/", ""))
    except OutOfKeysException:
        logger.error("No active keys to get models with!")
    except Exception as e:
        logger.error(f"Failed to get available models. Exception: {e}")
    return model_list


async def get_available_models(message: Message) -> List[str]:
    return await _get_available_models()
