import db.shared as dbs


async def __create_telegram_chat_config_if_does_not_exist_in_database_postgres(chat_id: int):
    async with dbs.pool.acquire() as conn:
        check_result = await conn.fetch("SELECT * FROM chat_config WHERE chat_id = $1", chat_id)
        if not check_result:
            await conn.execute("INSERT INTO chat_config VALUES ($1)", chat_id)


async def get_chat_parameter(chat_id: int, parameter_name: str):
    await __create_telegram_chat_config_if_does_not_exist_in_database_postgres(chat_id)
    async with dbs.pool.acquire() as conn:
        result = await conn.fetchrow(f"SELECT {parameter_name} FROM chat_config WHERE chat_id = {chat_id}")
        return list(result)[0]
