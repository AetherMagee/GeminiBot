from typing import List

from aiogram.types import Message
from asyncpg import Record
from loguru import logger


async def get_file(message: Message) -> List[str] or None:
    # Prioritize photos
    if message.photo and message.photo[-1].file_size < 10_000_000:
        return message.photo[-1].file_id, "photo"

    for media_type in [message.audio, message.video, message.voice, message.document, message.video_note,
                       message.sticker]:
        if media_type and media_type.file_size < 10_000_000:
            return media_type.file_id, "other"

    return None, None


async def get_file_id_from_chain(
        trigger_message_id: int,
        all_messages: List[Record],
        required_type: str,
        max_depth: int
) -> str or None:
    if required_type not in ["photo", "other"]:
        raise ValueError("Unknown required_type")

    lookup_dict = {sublist[1]: sublist for sublist in all_messages}

    trigger_message = lookup_dict[trigger_message_id]

    if trigger_message["media_file_id"] and trigger_message["media_type"] == required_type:
        return trigger_message["media_file_id"]

    async def check_reply(message: Record, current_depth: int) -> str or None:
        if message["media_file_id"]:
            if message["media_type"] == required_type:
                return message["media_file_id"]
        if message["reply_to_message_id"]:
            if current_depth <= max_depth:
                try:
                    return await check_reply(lookup_dict[message["reply_to_message_id"]], current_depth + 1)
                except KeyError:
                    return None
        return None

    return await check_reply(trigger_message, 1)



