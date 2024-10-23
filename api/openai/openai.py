import asyncio
import os
import random
from typing import List

import aiohttp
from aiogram.types import Message
from asyncpg import Record
from loguru import logger

import db
from api.google import format_message_for_prompt
from api.google.media import get_photo
from api.prompt import get_system_prompt
from utils import simulate_typing

OPENAI_API_KEY = os.getenv("OAI_API_KEY")


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
        timeout: int
) -> dict:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}"
    }
    data = {
        "model": model,
        "messages": messages_list,
        "temperature": temperature,
        "top_p": top_p,
        "frequency_penalty": frequency_penalty,
        "presence_penalty": presence_penalty,
        "max_tokens": max_output_tokens
    }
    if "o1" in model and "trycloudflare" not in url:
        data["max_completion_tokens"] = max_output_tokens

    logger.info(f"{request_id} | Sending request to {url}")
    async with aiohttp.ClientSession() as session:
        async with session.post(url + "v1/chat/completions", headers=headers, json=data,
                                timeout=timeout) as response:
            try:
                response_decoded = await response.json()
            except Exception as e:
                logger.error(f"Failed to parse response to json: ")
                logger.error(e)
                logger.debug(response_decoded)
                raise e
            logger.info(f"{request_id} | Complete | {response.status}")
            return response_decoded


async def get_prompt(trigger_message: Message, messages_list: List[Record], system_prompt: bool) -> List[dict]:
    chat_type = "direct message (DM)" if trigger_message.from_user.id == trigger_message.chat.id else "group"
    chat_title = f" called {trigger_message.chat.title}" if trigger_message.from_user.id != trigger_message.chat.id \
        else f" with {trigger_message.from_user.first_name}"
    system_prompt_template = await get_system_prompt()

    add_reply_to = await db.get_chat_parameter(trigger_message.chat.id, "add_reply_to")

    final = []
    if system_prompt:
        final.append({
            "role": "system",
            "content": system_prompt_template.format(
                chat_type=chat_type,
                chat_title=chat_title,
            )
        })

    last_role = None
    for index, message in enumerate(messages_list):
        sender_id = message["sender_id"]

        if sender_id == 727:
            role = "system"
        elif sender_id == 0:
            role = "assistant"
        else:
            role = "user"

        formatted_message = await format_message_for_prompt(message, add_reply_to)

        if role == "system":
            if system_prompt:
                formatted_message = formatted_message.replace("SYSTEM: ", "", 1)
        elif role == "assistant":
            formatted_message = await format_message_for_prompt(message, False)
            formatted_message = formatted_message.replace("You: ", "", 1)

        if last_role == role and final:
            final[-1]["content"] += "\n" + formatted_message
        else:
            final.append({
                "role": role,
                "content": formatted_message
            })
            last_role = role

    if await db.get_chat_parameter(trigger_message.chat.id, "o_vision"):
        image = await get_photo(
            trigger_message,
            messages_list
        )
    else:
        image = None

    if image:
        index = -1
        last_message = final[index]
        final[index] = {
            "role": last_message["role"],
            "content": [
                {
                    "type": "text",
                    "text": last_message["content"]
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image}"
                    }
                }
            ]
        }

    return final


async def generate_response(message: Message) -> str:
    request_id = random.randint(100000, 999999)
    logger.debug(
        f"RID: {request_id} | UID: {message.from_user.id} | CID: {message.chat.id} | MID: {message.message_id}"
    )

    if not os.getenv("OAI_ENABLED") or os.getenv("OAI_ENABLED").lower() != "true":
        logger.warning(f"{request_id} | OAI endpoint is disabled yet a request was received. Throwing an exception.")
        raise NotImplementedError("OpenAI endpoint is disabled globally.")

    show_errors = await db.get_chat_parameter(message.chat.id, "show_error_messages")
    append_system_prompt = await db.get_chat_parameter(message.chat.id, "o_add_system_prompt")

    messages = await db.get_messages(message.chat.id)
    model = await db.get_chat_parameter(message.chat.id, "o_model")
    log_prompt = await db.get_chat_parameter(message.chat.id, "o_log_prompt")
    prompt = await get_prompt(message, messages, append_system_prompt)
    if log_prompt:
        logger.debug(prompt)

    logger.debug(f"{request_id} | Using model {model}")

    timeout = int(await db.get_chat_parameter(message.chat.id, "o_timeout"))
    timed_out = False

    url = await db.get_chat_parameter(message.chat.id, "o_url")
    if not url:
        url = os.getenv("OAI_API_URL")
    if not url.endswith("/"):
        url = url + "/"

    key = await db.get_chat_parameter(message.chat.id, "o_key")
    if not key:
        key = os.getenv("OAI_API_KEY")

    typing_task = asyncio.create_task(simulate_typing(message.chat.id))
    try:
        api_task = asyncio.create_task(_send_request(
            prompt,
            url,
            key,
            model,
            request_id,
            float(await db.get_chat_parameter(message.chat.id, "o_temperature")),
            float(await db.get_chat_parameter(message.chat.id, "o_top_p")),
            float(await db.get_chat_parameter(message.chat.id, "o_frequency_penalty")),
            float(await db.get_chat_parameter(message.chat.id, "o_presence_penalty")),
            int(await db.get_chat_parameter(message.chat.id, "max_output_tokens")),
            timeout
        ))
        response = await api_task
    except asyncio.TimeoutError:
        timed_out = True
    except Exception as e:
        logger.debug(e)
        output = "❌ *Произошел сбой эндпоинта OpenAI.*"
        if show_errors:
            output += "\n\n" + str(e)
        return output

    typing_task.cancel()
    try:
        await typing_task
    except asyncio.CancelledError:
        pass

    if timed_out:
        output = f"❌ *Превышено время ожидания ответа от эндпоинта OpenAI.*\nНынешний таймаут: `{timeout}`"
        return output

    try:
        output = response["choices"][0]["message"]["content"]
        if response["choices"][0]["finish_reason"] and response["choices"][0]["finish_reason"] == "length":
            output = "❌ *Произошел сбой эндпоинта OpenAI.*"
            if show_errors:
                output += "\n\nГенерация была прервана на стороне эндпоинта из за ограничения `max_output_tokens`"
        if "oai-proxy-error" in output:
            logger.debug(output)
            output = "❌ *Произошел сбой эндпоинта OpenAI.*"
            if show_errors:
                output += "\n\n" + response["choices"][0]["message"]["content"]
    except (KeyError, TypeError) as error:
        logger.debug(response)
        output = "❌ *Произошел сбой эндпоинта OpenAI.*"
        if show_errors:
            if response["error"] and response["error"]["message"]:
                output += "\n\n" + response["error"]["message"]
            else:
                output += "\n\n" + str(error)

    return output
