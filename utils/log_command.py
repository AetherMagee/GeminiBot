from aiogram.types import Message
from loguru import logger


async def log_command(message: Message) -> None:
    text = message.text if message.text else message.caption
    if not text.startswith("/"):
        return
    logger.info(f"{message.from_user.id} | {message.chat.id} | {text}")
