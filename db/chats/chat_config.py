import db.shared as dbs
from utils.definitions import chat_configs


async def _create_config_entry(chat_id: int):
    async with dbs.pool.acquire() as conn:
        check_result = await conn.fetch("SELECT * FROM chat_config WHERE chat_id = $1", chat_id)
        if not check_result:
            await conn.execute("INSERT INTO chat_config VALUES ($1)", chat_id)


async def get_chat_parameter(chat_id: int, parameter_name: str):
    await _create_config_entry(chat_id)
    async with dbs.pool.acquire() as conn:
        result = await conn.fetchrow(f"SELECT {parameter_name} FROM chat_config WHERE chat_id = {chat_id}")
        return list(result)[0]


async def set_chat_parameter(chat_id: int, parameter_name: str, value):
    await _create_config_entry(chat_id)

    if chat_configs[parameter_name]["type"] == "text":
        value = f"\'{value}\'"

    async with dbs.pool.acquire() as conn:
        await conn.execute(f"UPDATE chat_config SET {parameter_name} = {value} WHERE chat_id = {chat_id}")
