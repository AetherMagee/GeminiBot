from aiogram.enums import ParseMode
from aiogram.types import Message
from loguru import logger

import utils
from api.google import generate_response


async def raw_command(message: Message) -> None:
    command = message.text.split(" ", maxsplit=1)
    if len(command) != 2:
        await message.reply("❌ <b>Использование команды:</b> <i>/raw [текст]</i>")
        return

    output = await generate_response(message)
    try:
        await message.reply(output, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Failed to send response: {e}")
        try:
            output = await utils.no_markdown(output)
            await message.reply(output)
        except Exception:
            await message.reply("❌ <b>Gemini API выдало какой то пиздец с которым я даже не знаю как работать, "
                                "поэтому вместо него держите это сообщение об ошибке.</b>")
