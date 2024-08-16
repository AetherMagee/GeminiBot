from async_lru import alru_cache

import db.shared as dbs
from utils.definitions import chat_configs


async def _create_config_entry(chat_id: int):
    async with dbs.pool.acquire() as conn:
        check_result = await conn.fetch("SELECT * FROM chat_config WHERE chat_id = $1", chat_id)
        if not check_result:
            await conn.execute("INSERT INTO chat_config VALUES ($1)", chat_id)


@alru_cache
async def get_chat_parameter(chat_id: int, parameter_name: str):
    await _create_config_entry(chat_id)
    async with dbs.pool.acquire() as conn:
        result = await conn.fetchrow(f"SELECT {parameter_name} FROM chat_config WHERE chat_id = $1", chat_id)
        return list(result)[0]


async def set_chat_parameter(chat_id: int, parameter_name: str, value):
    await _create_config_entry(chat_id)

    chat_endpoint = await get_chat_parameter(chat_id, "endpoint")
    available_parameters = chat_configs["all_endpoints"] | chat_configs[chat_endpoint]

    if available_parameters[parameter_name]["type"] == "text":
        value = f"\'{value}\'"

    async with dbs.pool.acquire() as conn:
        await conn.execute(f"UPDATE chat_config SET {parameter_name} = $1 WHERE chat_id = {chat_id}", value)

    get_chat_parameter.cache_invalidate(chat_id, parameter_name)
