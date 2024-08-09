from aiogram import html
from aiogram.types import Message

import db.shared as dbs
from utils import log_command


async def sql_command(message: Message):
    await log_command(message)

    message_text = message.text
    fetch = False
    if "-fetch" in message_text:
        message_text = message_text.replace(" -fetch", "")
        fetch = True

    try:
        command = message_text.split(" ", maxsplit=1)
        async with dbs.pool.acquire() as conn:
            if fetch:
                result = await conn.fetch(command[1])
            else:
                result = await conn.execute(command[1])
            await message.reply(html.quote(str(result)))
    except Exception as e:
        await message.reply(str(e))

