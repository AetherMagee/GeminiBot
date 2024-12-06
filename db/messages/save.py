import datetime

from aiogram.types import Message
from asyncpg import UndefinedTableError

import db.shared as dbs
from api.media import get_file
from db.table_creator import create_message_table
from utils import get_message_text


def truncate_str(reply_text: str, max_length=50) -> str:
    """
    Shorten string to given max length
    ("The quick brown fox jumped over the lazy dog", 30) -> "The quick ... lazy dog"
    """
    if not reply_text:
        return ""

    reply_text = reply_text.replace('\n', ' ')
    if len(reply_text) > max_length:
        part_length = max_length // 2 - len(" {...} ") // 2
        start = reply_text[:part_length]
        end = reply_text[-part_length:]
        start_slice = start.rsplit(' ', 1)[0] if ' ' in start else start
        end_slice = end.split(' ', 1)[1] if ' ' in end else end
        return f"{start_slice} ... {end_slice}"
    elif len(reply_text) > max_length // 2:
        truncated_text = reply_text[:max_length - 3]
        return f"{truncated_text.rsplit(' ', 1)[0]}..." if ' ' in truncated_text else truncated_text + "..."
    return reply_text


async def _save_message(chat_id: int, message_id: int, time: datetime.datetime, sender_id: int, sender_uname: str,
                        sender_name: str, text: str, reply_to_message_id: int or None,
                        reply_to_message_text: str or None, media_file_id: str or None, media_type: str or None) -> None:
    async with dbs.pool.acquire() as conn:
        sanitized_chat_id = await dbs.sanitize_chat_id(chat_id)
        try:
            await conn.execute(f"INSERT INTO messages{sanitized_chat_id} (message_id, timestamp, sender_id, "
                               f"sender_username, sender_name, text, "
                               f"reply_to_message_id, reply_to_message_trimmed_text, media_file_id, media_type) "
                               f"VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)",
                               message_id,
                               time,
                               sender_id,
                               sender_uname,
                               sender_name,
                               text,
                               reply_to_message_id,
                               reply_to_message_text,
                               media_file_id,
                               media_type)
        except UndefinedTableError:
            await create_message_table(conn, sanitized_chat_id)
            await _save_message(chat_id, message_id, time, sender_id, sender_uname,
                                sender_name, text, reply_to_message_id, reply_to_message_text, media_file_id, media_type)


async def save_aiogram_message(message: Message):
    file_id, media_type = await get_file(message)
    if message.quote:
        reply_text = truncate_str(message.quote.text)
    elif message.reply_to_message:
        reply_text = truncate_str(await get_message_text(message.reply_to_message))
    else:
        reply_text = None

    await _save_message(
        message.chat.id,
        message.message_id,
        datetime.datetime.now(),
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
        await get_message_text(message, "before_forced"),
        message.reply_to_message.message_id if message.reply_to_message else None,
        reply_text,
        file_id,
        media_type
    )


async def save_our_message(trigger_message: Message, text: str, our_message_id: int):
    await _save_message(
        trigger_message.chat.id,
        our_message_id,
        datetime.datetime.now(),
        0,
        "You",
        "You",
        text,
        trigger_message.message_id,
        truncate_str(await get_message_text(trigger_message, "before_forced")),
        None,
        None
    )


async def save_system_message(chat_id: int, text: str):
    await _save_message(
        chat_id,
        0,
        datetime.datetime.now(),
        727,
        "SYSTEM",
        "SYSTEM",
        text,
        None,
        None,
        None,
        None
    )
