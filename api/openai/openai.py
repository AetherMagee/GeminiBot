import asyncio
import os
import random
import time
from typing import List

import aiohttp
from aiogram.types import Message
from aiohttp_socks import ProxyConnector
from async_lru import alru_cache
from asyncpg import Record
from loguru import logger

import db
from api.google import format_message_for_prompt
from api.google.media import get_photo
from api.prompt import get_system_prompt
from utils import simulate_typing

# Environment variables
OPENAI_API_KEY = os.getenv("OAI_API_KEY")
PROXY_URL = os.getenv("PROXY_URL")
OAI_API_URL = os.getenv("OAI_API_URL")
OAI_ENABLED = os.getenv("OAI_ENABLED")


async def _send_request(
        messages_list: List[dict],
        url: str,
        key: str,
        model: str,
        request_id: int,
        temperature: float,
        top_p: float,
        frequency_penalty: float,
        presence_penalty: float,
        max_output_tokens: int,
        timeout: int,
) -> dict:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
    }
    data = {
        "model": model,
        "messages": messages_list,
        "temperature": temperature,
        "top_p": top_p,
        "frequency_penalty": frequency_penalty,
        "presence_penalty": presence_penalty,
        "max_tokens": max_output_tokens,
    }

    if "o1" in model and "trycloudflare" not in url:
        data["max_completion_tokens"] = max_output_tokens
        del data["max_tokens"]

    logger.info(f"{request_id} | Sending request to {url}")

    connector = ProxyConnector.from_url(PROXY_URL) if PROXY_URL else None

    gen_start_time = time.perf_counter()

    async with aiohttp.ClientSession(connector=connector) as session:
        try:
            async with session.post(
                    f"{url}v1/chat/completions",
                    headers=headers,
                    json=data,
                    timeout=timeout,
            ) as response:
                response_decoded = await response.json()

                gen_end_time = time.perf_counter()
                gen_timedelta = gen_end_time - gen_start_time

                logger.info(f"{request_id} | Сomplete | {response.status} | {round(gen_timedelta, 2)}s")
                return response_decoded
        except Exception as e:
            logger.error("Failed to parse response to JSON.")
            logger.exception(e)
            raise


async def get_prompt(
        trigger_message: Message,
        messages_list: List[Record],
        system_prompt: bool,
        system_messages: bool,
) -> List[dict]:
    is_direct_message = trigger_message.from_user.id == trigger_message.chat.id
    chat_type = "direct message (DM)" if is_direct_message else "group"
    chat_title = (
        f" with {trigger_message.from_user.first_name}"
        if is_direct_message
        else f" called {trigger_message.chat.title}"
    )

    system_prompt_template = await get_system_prompt()
    add_reply_to = await db.get_chat_parameter(trigger_message.chat.id, "add_reply_to")

    final_prompt = []
    if system_prompt and system_messages:
        final_prompt.append(
            {
                "role": "system",
                "content": system_prompt_template.format(
                    chat_type=chat_type,
                    chat_title=chat_title,
                ),
            }
        )

    last_role = None
    for message in messages_list:
        sender_id = message["sender_id"]

        if sender_id == 727:
            role = "system"
        elif sender_id == 0:
            role = "assistant"
        else:
            role = "user"

        formatted_message = await format_message_for_prompt(message, add_reply_to)

        if role == "system" and system_messages:
            formatted_message = formatted_message.replace("SYSTEM: ", "", 1)
        elif role == "assistant":
            formatted_message = await format_message_for_prompt(message, False)
            formatted_message = formatted_message.replace("You: ", "", 1)

        if last_role == role and final_prompt:
            final_prompt[-1]["content"] += f"\n{formatted_message}"
        else:
            final_prompt.append({"role": role, "content": formatted_message})
            last_role = role

    clarify_target_message = await db.get_chat_parameter(
        trigger_message.chat.id, "o_clarify_target_message"
    )
    if system_prompt and system_messages and clarify_target_message:
        final_prompt.append(
            {
                "role": "system",
                "content": (
                    "That's it with the chat history. The next User message will be your TARGET message. "
                    "This is the message that triggered this request in the first place. Read it, "
                    "make sure to not confuse what it's asking or talking about while NOT CONFUSING ONGOING TOPICS "
                    "based on the current chat history, and respond to it."
                ),
            }
        )
        target_msg = await db.get_specific_message(
            trigger_message.chat.id, trigger_message.message_id
        )
        final_prompt.append(
            {
                "role": "user",
                "content": await format_message_for_prompt(target_msg, add_reply_to),
            }
        )

    vision_enabled = await db.get_chat_parameter(trigger_message.chat.id, "o_vision")
    image = await get_photo(trigger_message, messages_list) if vision_enabled else None

    if image:
        last_message = final_prompt[-1]
        final_prompt[-1] = {
            "role": last_message["role"],
            "content": [
                {"type": "text", "text": last_message["content"]},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image}"}},
            ],
        }

    return final_prompt


async def generate_response(message: Message) -> str:
    request_id = random.randint(100000, 999999)
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    chat_id = message.chat.id
    chat_title = message.chat.title
    message_id = message.message_id

    logger.info(
        f"R: {request_id} | U: {user_id} ({user_name}) | C: {chat_id} ({chat_title}) | M: {message_id}"
    )

    if not OAI_ENABLED or OAI_ENABLED.lower() != "true":
        logger.warning(
            f"{request_id} | OpenAI endpoint is disabled. Raising NotImplementedError."
        )
        raise NotImplementedError("OpenAI endpoint is disabled globally.")

    show_errors = await db.get_chat_parameter(chat_id, "show_error_messages")
    append_system_prompt = await db.get_chat_parameter(chat_id, "add_system_prompt")
    add_system_messages = await db.get_chat_parameter(chat_id, "add_system_messages")

    messages = await db.get_messages(chat_id)
    model = await db.get_chat_parameter(chat_id, "o_model")
    log_prompt = await db.get_chat_parameter(chat_id, "o_log_prompt")
    prompt = await get_prompt(message, messages, append_system_prompt, add_system_messages)

    if log_prompt:
        logger.debug(prompt)

    logger.debug(f"{request_id} | Using model {model}")

    timeout = int(await db.get_chat_parameter(chat_id, "o_timeout"))
    url = await db.get_chat_parameter(chat_id, "o_url") or OAI_API_URL
    url = url.rstrip("/") + "/"

    key = await db.get_chat_parameter(chat_id, "o_key") or OPENAI_API_KEY
    typing_task = asyncio.create_task(simulate_typing(chat_id))

    try:
        response = await _send_request(
            messages_list=prompt,
            url=url,
            key=key,
            model=model,
            request_id=request_id,
            temperature=float(await db.get_chat_parameter(chat_id, "o_temperature")),
            top_p=float(await db.get_chat_parameter(chat_id, "o_top_p")),
            frequency_penalty=float(
                await db.get_chat_parameter(chat_id, "o_frequency_penalty")
            ),
            presence_penalty=float(
                await db.get_chat_parameter(chat_id, "o_presence_penalty")
            ),
            max_output_tokens=int(
                await db.get_chat_parameter(chat_id, "max_output_tokens")
            ),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        output = (
            f"❌ *Превышено время ожидания ответа от эндпоинта OpenAI.*\n"
            f"Нынешний таймаут: `{timeout}`"
        )
        return output
    except Exception as e:
        logger.exception(e)
        output = "❌ *Произошёл неизвестный сбой.*\n\nПожалуйста, попробуйте позже."
        return output
    finally:
        typing_task.cancel()
        try:
            await typing_task
        except asyncio.CancelledError:
            pass

    try:
        choice = response["choices"][0]
        output = choice["message"]["content"]
        finish_reason = choice.get("finish_reason")

        if finish_reason == "length":
            output = "❌ *Произошел сбой эндпоинта OpenAI.*"
            if show_errors:
                output += (
                    "\n\nГенерация была прервана на стороне эндпоинта из-за ограничения "
                    "`max_output_tokens`"
                )

        if "oai-proxy-error" in output:
            logger.warning(f"{request_id} | Response is OAI proxy error.")

            new_out = "❌ *Произошел сбой эндпоинта OpenAI.*"

            trigger_words = ["sk-", "AIzaSy"]
            if show_errors and not any([word in output for word in trigger_words]):
                new_out += f"\n\n{output}"

            output = new_out

        usage = response.get("usage")
        if usage:
            logger.debug(
                f"{request_id} | Tokens: {usage.get('total_tokens', 'N/A')} total "
                f"({usage.get('prompt_tokens', 'N/A')} prompt, "
                f"{usage.get('completion_tokens', 'N/A')} completion)"
            )
            await db.statistics.log_generation(
                chat_id,
                user_id,
                "openai",
                usage.get("prompt_tokens", 0),
                usage.get("completion_tokens", 0),
                model,
            )
        else:
            logger.warning(f"{request_id} | No usage information in response.")
    except (KeyError, IndexError, TypeError) as error:
        logger.exception(error)
        output = "❌ *Произошел неопознанный сбой эндпоинта OpenAI.*"
        if show_errors:
            error_message = response.get("error", {}).get("message", str(error))
            if not any(word in error_message.lower() for word in ["auth", "key", "sk-"]):
                output += f"\n\n{error_message}"

    return output


@alru_cache(ttl=300)
async def _get_available_models(url: str, key: str, get_all_models=False) -> List[str]:
    logger.info(f"Getting available models for {url} - ...{key[-6:]}")

    connector = ProxyConnector.from_url(PROXY_URL) if PROXY_URL else None
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
    }

    try:
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(
                    f"{url}v1/models", headers=headers, timeout=5
            ) as response:
                response_decoded = await response.json()

                allowed_keywords = ["gpt", "o1"]
                disallowed_keywords = ["realtime"]

                if not get_all_models:
                    return [
                        entry["id"]
                        for entry in response_decoded.get("data", [])
                        if any(kw in entry["id"] for kw in allowed_keywords)
                           and not any(dkw in entry["id"] for dkw in disallowed_keywords)
                    ]

                return [entry["id"] for entry in response_decoded.get("data", [])]
    except Exception as e:
        logger.warning("Failed to get available models.")
        logger.exception(e)
        return []


async def get_available_models(message: Message) -> List[str]:
    chat_id = message.chat.id
    url = await db.get_chat_parameter(chat_id, "o_url") or OAI_API_URL
    url = url.rstrip("/") + "/"

    key = await db.get_chat_parameter(chat_id, "o_key") or OPENAI_API_KEY

    return await _get_available_models(url, key)