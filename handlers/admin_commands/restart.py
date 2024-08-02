from aiogram.types import Message, ReactionTypeEmoji
from loguru import logger


async def restart_command(message: Message) -> None:
    await message.react([ReactionTypeEmoji(emoji="👌")])
    logger.info("Restarting...")
    exit(1)  # docker auto restart goes brrr
