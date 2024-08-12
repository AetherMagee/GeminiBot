from aiogram.types import Message
from loguru import logger

import db


async def handle_message_edit(message: Message) -> None:
    logger.info(f"Updating message {message.message_id} in {message.chat.id}")
    await db.replace_message(message.chat.id, message.message_id, message.text)
