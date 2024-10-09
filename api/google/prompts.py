import os
from typing import Dict, List

from aiogram.types import Message
from asyncpg import Record
from loguru import logger

from api.google.media import get_other_media, get_photo

bot_id = int(os.getenv("TELEGRAM_TOKEN").split(":")[0])


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
            if message["sender_id"] == 727:
                logger.warning("Got a system message. Ignoring...")
                continue
            elif message["sender_id"] == 0:
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


async def get_system_messages(chat_messages: List[Record]) -> List[str]:
    result = []
    for message in chat_messages:
        if message["sender_id"] == 727:
            result.append(message["text"])

    return result
