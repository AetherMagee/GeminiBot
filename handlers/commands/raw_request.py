from aiogram.enums import ParseMode
from aiogram.types import Message
from loguru import logger

from api.google import generate_response
from utils import get_message_text, no_markdown


async def raw_command(message: Message) -> None:
    message_text = await get_message_text(message)
    command = message_text.split(" ", maxsplit=1)
    if len(command) != 2:
        await message.reply("❌ <b>Использование команды:</b> <i>/raw [текст]</i>")
        return

    output = await generate_response(message)
    try:
        await message.reply(output, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Failed to send response: {e}")
        try:
            output = await no_markdown(output)
            await message.reply(output)
        except Exception:
            await message.reply("❌ <b>Telegram не принимает ответ бота.</b>")