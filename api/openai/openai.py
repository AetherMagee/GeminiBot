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
from api.google import format_message_for_prompt, ERROR_MESSAGES
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
    }
    logger.debug(f"{request_id} | Sending request to {OPENAI_URL}")
    async with aiohttp.ClientSession() as session:
        async with session.post(OPENAI_URL + "v1/chat/completions", headers=headers, json=data) as response:
            logger.debug(f"{request_id} | Complete | {response.status}")
            return await response.json()


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

    for message in messages_list:
        message_as_text = await format_message_for_prompt(message, add_reply_to)
        if message == messages_list[-1]:
            continue
        elif message_as_text.startswith("You: "):
            final.append({
                "role": "assistant",
                "content": message_as_text.replace("You: ", "")
            })
        elif message_as_text.startswith("SYSTEM: "):
            final.append({
                "role": "system",
                "content": message_as_text.replace("SYSTEM: ", "")
            })
        else:
            final.append({
                "role": "user",
                "content": message_as_text
            })

    if system_prompt:
        final.append({
            "role": "system",
            "content": prompt_p2
        })

    if await db.get_chat_parameter(trigger_message.chat.id, "o_vision"):
        image = await get_photo(trigger_message, "base64")
    else:
        image = None

    if not image:
        final.append({
            "role": "user",
            "content": await format_message_for_prompt(messages_list[-1], add_reply_to)
        })
    else:
        final.append({
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": await format_message_for_prompt(messages_list[-1], add_reply_to)
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image}"
                    }
                }
            ]
        })

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
    prompt = await get_prompt(message, messages, append_system_prompt)

    logger.debug(f"{request_id} | Using model {model}")

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
        ))
        response = await api_task
    except Exception as e:
        logger.debug(e)
        response = None

    typing_task.cancel()
    try:
        await typing_task
    except asyncio.CancelledError:
        pass

    try:
        output = response["choices"][0]["message"]["content"]
        if "oai-proxy-error" in output:
            logger.debug(output)
            output = "❌ *Произошел сбой эндпоинта OpenAI.*"
            if show_errors:
                output += "\n\n" + response["choices"][0]["message"]["content"]
    except KeyError:
        logger.debug(response)
        output = "❌ *Произошел сбой эндпоинта OpenAI.*"
    finally:
        if output.startswith("❌"):
            await db.save_system_message(message.chat.id, ERROR_MESSAGES["system_failure"])

        return output


def get_available_models() -> list:
    try:
        logger.debug("Getting available models...")
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
