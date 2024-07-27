from aiogram.types import Message

import db.shared as dbs


async def sql_command(message: Message):
    try:
        command = message.text.split(" ", maxsplit=1)
        async with dbs.pool.acquire() as conn:
            result = await conn.execute(command[1])
            await message.reply(str(result))
    except Exception as e:
        await message.reply(str(e))

