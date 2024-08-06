from aiogram.types import Message, ReactionTypeEmoji
from loguru import logger

from main import bot
from utils import log_command


async def directsend_command(message: Message):
    await log_command(message)
    command = message.text.split(' ', maxsplit=2)
    logger.info(f"Sending direct message to {command[1]}")
    await bot.send_message(int(command[1]), command[2])
    await message.react([ReactionTypeEmoji(emoji="👌")])
