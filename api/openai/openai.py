import asyncio
import os
import random
from typing import List

import aiohttp
import requests
from aiogram.types import Message
from asyncpg import Record
from loguru import logger

import db
from api.google import format_message_for_prompt, ERROR_MESSAGES
from utils import simulate_typing

OPENAI_URL = os.getenv("OAI_API_URL")
OPENAI_API_KEY = os.getenv("OAI_API_KEY")
with open(os.getenv("OAI_PROMPT_PART1_PATH"), "r") as f:
    prompt_p1 = f.read()
with open(os.getenv("OAI_PROMPT_PART2_PATH"), "r") as f:
    prompt_p2 = f.read()


async def _send_request(messages_list: List[dict], model: str, request_id: int) -> dict:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }
    data = {
        "model": model,
        "messages": messages_list
    }
    logger.debug(f"{request_id} | Sending request to {OPENAI_URL}")
    async with aiohttp.ClientSession() as session:
        async with session.post(OPENAI_URL + "v1/chat/completions", headers=headers, json=data) as response:
            logger.debug(f"{request_id} | Complete | {response.status}")
            return await response.json()


async def get_prompt(trigger_message: Message, messages_list: List[Record]) -> List[dict]:
    chat_type = "direct message (DM)" if trigger_message.from_user.id == trigger_message.chat.id else "group"
    chat_title = f" called {trigger_message.chat.title}" if trigger_message.from_user.id != trigger_message.chat.id else f" with {trigger_message.from_user.first_name}"

    final = [{
        "role": "system",
        "content": prompt_p1.format(
            chat_type=chat_type,
            chat_title=chat_title,
        )
    }]

    for message in messages_list:
        message_as_text = await format_message_for_prompt(message)
        if message_as_text.startswith("You: "):
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

    final.append({
        "role": "system",
        "content": prompt_p2
    })

    return final


async def generate_response(message: Message) -> str:
    request_id = random.randint(100000, 999999)
    logger.debug(
        f"RID: {request_id} | UID: {message.from_user.id} | CID: {message.chat.id} | MID: {message.message_id}"
    )
    show_errors = await db.get_chat_parameter(message.chat.id, "show_error_messages")

    messages = await db.get_messages(message.chat.id)

    prompt = await get_prompt(message, messages)
    typing_task = asyncio.create_task(simulate_typing(message.chat.id))
    api_task = asyncio.create_task(_send_request(
        prompt,
        await db.get_chat_parameter(message.chat.id, "o_model"),
        request_id
    ))
    response = await api_task
    typing_task.cancel()
    try:
        await typing_task
    except asyncio.CancelledError:
        pass

    try:
        output = response["choices"][0]["message"]["content"]
        if "oai-proxy-error" in output:
            logger.debug(output)
            output = "❌ Произошел сбой эндпоинта OpenAI."
            if show_errors:
                output += "\n\n" + response["choices"][0]["message"]["content"]
    except KeyError:
        logger.debug(response)
        output = "❌ *Произошел сбой эндпоинта OpenAI.*"
    finally:
        if output.startswith("❌"):
            await db.save_system_message(message.chat.id, ERROR_MESSAGES["system_failure"])
        else:
            await db.save_our_message(message, output)

        return output


def get_available_models() -> list:
    logger.debug("Getting available models...")
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer 1ee1823c-c51a-4735-9c35-87b6ca7dd463"
    }

    response = requests.get(OPENAI_URL + "models", headers=headers, timeout=5)
    result = []
    for object in response.json()["data"]:
        result.append(object["id"])

    return result
