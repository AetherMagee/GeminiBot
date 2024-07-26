import db.shared as dbs


async def _create_chat_config_entry_if_not_exists(chat_id: int):
    async with dbs.pool.acquire() as conn:
        check_result = await conn.fetch("SELECT * FROM chat_config WHERE chat_id = $1", chat_id)
        if not check_result:
            await conn.execute("INSERT INTO chat_config VALUES ($1)", chat_id)


async def get_chat_parameter(chat_id: int, parameter_name: str):
    await _create_chat_config_entry_if_not_exists(chat_id)
    async with dbs.pool.acquire() as conn:
        result = await conn.fetchrow(f"SELECT {parameter_name} FROM chat_config WHERE chat_id = {chat_id}")
        return list(result)[0]
