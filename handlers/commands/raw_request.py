from aiogram import html
from aiogram.enums import ParseMode
from aiogram.types import Message
from loguru import logger

from api.google import generate_response
from utils import get_message_text


async def raw_command(message: Message) -> None:
    # TODO: Support OpenAI endpoint
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
            await message.reply(html.quote(output))
        except Exception:
            await message.reply(f"❌ <b>Telegram не принимает ответ бота.</b> <i>({len(output)} символов)</i>")
