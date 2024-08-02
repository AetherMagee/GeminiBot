from aiogram.types import Message

import db.shared as dbs
from utils import log_command


async def sql_command(message: Message):
    await log_command(message)
    try:
        command = message.text.split(" ", maxsplit=1)
        async with dbs.pool.acquire() as conn:
            result = await conn.execute(command[1])
            await message.reply(str(result))
    except Exception as e:
        await message.reply(str(e))

