from aiogram.types import Message
from loguru import logger


def log_command(message: Message) -> None:
    if not message.text.startswith("/"):
        return
    logger.debug(f"{message.from_user.id} | {message.chat.id} | {message.text if message.text else message.caption}")
