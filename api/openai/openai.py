import asyncio
import os
import random
import traceback
from typing import List

import aiohttp
import requests
from aiogram.types import Message
from asyncpg import Record
from loguru import logger

import db
from api.google import ERROR_MESSAGES, format_message_for_prompt
from api.google.media import get_photo
from utils import simulate_typing

OPENAI_URL = os.getenv("OAI_API_URL")
OPENAI_API_KEY = os.getenv("OAI_API_KEY")
with open(os.getenv("OAI_PROMPT_PART1_PATH"), "r") as f:
    prompt_p1 = f.read()
with open(os.getenv("OAI_PROMPT_PART2_PATH"), "r") as f:
    prompt_p2 = f.read()


async def _send_request(
        messages_list: List[dict],
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
        "Authorization": f"Bearer {OPENAI_API_KEY}"
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
    logger.info(f"{request_id} | Sending request to {OPENAI_URL}")
    async with aiohttp.ClientSession() as session:
        async with session.post(OPENAI_URL + "v1/chat/completions", headers=headers, json=data, timeout=timeout) as response:
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
    chat_title = f" called {trigger_message.chat.title}" if trigger_message.from_user.id != trigger_message.chat.id else f" with {trigger_message.from_user.first_name}"

    add_reply_to = await db.get_chat_parameter(trigger_message.chat.id, "add_reply_to")

    final = []
    if system_prompt:
        final.append({
            "role": "system",
            "content": prompt_p1.format(
                chat_type=chat_type,
                chat_title=chat_title,
            )
        })
        final.append({
            "role": "system",
            "content": prompt_p2
        })

    user_message_buffer = []
    for index, message in enumerate(messages_list):
        if message["sender_id"] not in [0, 727]:
            user_message_buffer.append(await format_message_for_prompt(message, add_reply_to))
            if index == len(messages_list) - 1:
                final.append({
                    "role": "user",
                    "content": "\n".join(user_message_buffer)
                })
                break
        else:
            if user_message_buffer:
                final.append({
                    "role": "user",
                    "content": "\n".join(user_message_buffer)
                })
                user_message_buffer.clear()
            if message["sender_id"] == 727:
                final.append({
                    "role": "system",
                    "content": (await format_message_for_prompt(message, False)).replace("SYSTEM: ", "", 1)
                })
            elif message["sender_id"] == 0:
                final.append({
                    "role": "assistant",
                    "content": (await format_message_for_prompt(message, False)).replace("You: ", "", 1)
                })
            else:
                logger.error("How did we get here?")
                logger.debug(index)
                logger.debug(message)

    if await db.get_chat_parameter(trigger_message.chat.id, "o_vision"):
        image = await get_photo(
            trigger_message,
            messages_list,
            "base64"
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

    typing_task = asyncio.create_task(simulate_typing(message.chat.id))
    try:
        api_task = asyncio.create_task(_send_request(
            prompt,
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
        response = None

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
        if "oai-proxy-error" in output:
            logger.debug(output)
            output = "❌ *Произошел сбой эндпоинта OpenAI.*"
            if show_errors:
                output += "\n\n" + response["choices"][0]["message"]["content"]
    except (KeyError, TypeError) as error:
        logger.debug(response)
        output = "❌ *Произошел сбой эндпоинта OpenAI.*"
        if show_errors:
            output += "\n\n" + str(error)
    finally:
        if output.startswith("❌"):
            await db.save_system_message(message.chat.id, ERROR_MESSAGES["system_failure"])

        return output


def get_available_models() -> list:
    try:
        logger.info("OAI | Getting available models...")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENAI_API_KEY}"
        }

        response = requests.get(OPENAI_URL + "models", headers=headers, timeout=5)
        result = []
        for object in response.json()["data"]:
            result.append(object["id"])

        return result
    except Exception as e:
        traceback.print_exc()
        return []
