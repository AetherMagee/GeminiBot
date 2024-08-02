from aiogram.types import Message
from loguru import logger

from utils import get_message_text


async def log_command(message: Message) -> None:
    text = await get_message_text(message)
    if not text.startswith("/"):
        return
    logger.debug(f"{message.from_user.id} | {message.chat.id} | {text}")
