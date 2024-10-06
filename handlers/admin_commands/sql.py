import os

from aiogram import html
from aiogram.types import FSInputFile, Message

import db.shared as dbs
from main import bot
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
        if "too long" in str(e):
            path = os.getenv("CACHE_PATH") + "out.txt"
            with open(path, "w") as file:
                file.write(str(result))
            await bot.send_document(message.chat.id, FSInputFile(path=path, filename="out.txt"))
        else:
            await message.reply(str(e))

