from aiogram.types import Message
from loguru import logger


async def no_markdown(text: str) -> str:
    """
    Strips the text of any markdown-related characters.
    Called if the Telegram API doesn't accept our output.
    """
    forbidden_characters = ['*', '_', ']', '[', '`', '\\']
    for character in forbidden_characters:
        text = text.replace(character, '')
    return text


async def get_message_text(message: Message, what_to_get: str = "both") -> str:
    if message.text:
        text = message.text
    elif message.caption:
        text = message.caption
    else:
        text = ""

    if what_to_get == "both":
        return text

    parts = text.split(" --force-answer ", maxsplit=1)
    if len(parts) == 1:
        parts = text.split(" —force-answer ", maxsplit=1)
        if len(parts) == 1:
            if what_to_get == "before_forced":
                return text
            return ""

    if what_to_get == "before_forced":
        return parts[0]
    elif what_to_get == "after_forced":
        return parts[1]
    else:
        raise NotImplementedError(f"Unknown what_to_get {what_to_get}")
