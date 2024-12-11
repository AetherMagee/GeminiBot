import os
from typing import Dict, List

from aiogram.types import Message
from asyncpg import Record

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
        result += f"[> {message['reply_to_message_trimmed_text']}] "

    if message["text"]:
        result += message["text"]
    else:
        if message["media_type"] == "photo":
            result += "[photo.jpg]"
        elif message["media_type"] == "other":
            result += "[miscellaneous_file]"
        else:
            result += "*No text*"
    return result


async def _prepare_prompt(trigger_message: Message, chat_messages: List[Record], token: str) -> List[Dict]:
    result = []
    message_buffer = []
    current_role = None
    last_user_block = None

    for message in chat_messages:
        if message["sender_id"] == 727:
            continue  # Skip system messages

        if message["sender_id"] == 0:
            role = 'model'
            formatted_message = await format_message_for_prompt(message, False)
            formatted_message = formatted_message.replace("You: ", "", 1)
        else:
            role = 'user'
            formatted_message = await format_message_for_prompt(message)

        if current_role is None:
            current_role = role
            message_buffer.append(formatted_message)
        elif role == current_role:
            message_buffer.append(formatted_message)
        else:
            # Flush the buffer when the role changes
            block = {
                "role": current_role,
                "parts": [{
                    "text": "\n".join(message_buffer)
                }],
            }
            result.append(block)
            # Update last_user_block if the current role is 'user'
            if current_role == 'user':
                last_user_block = block
            # Reset the buffer and update the current role
            message_buffer = [formatted_message]
            current_role = role

    # Flush any remaining messages in the buffer
    if message_buffer:
        block = {
            "role": current_role,
            "parts": [{
                "text": "\n".join(message_buffer)
            }],
        }
        result.append(block)
        # Update last_user_block if the current role is 'user'
        if current_role == 'user':
            last_user_block = block

    # If the last block is 'model', duplicate the last 'user' block
    if result[-1]["role"] != 'user':
        if last_user_block is not None:
            # Append a copy of the last_user_block
            duplicated_block = {
                "role": 'user',
                "parts": last_user_block["parts"].copy()
            }
            result.append(duplicated_block)
        else:
            # If no user messages were found, append an empty 'user' block
            result.append({
                "role": 'user',
                "parts": [{
                    "text": ""
                }],
            })

    # Handle images and other media files
    image = await get_photo(trigger_message, chat_messages)
    other_file = await get_other_media(trigger_message, token, chat_messages)

    if image:
        last_message = result[-1]
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
        last_message = result[-1]
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
