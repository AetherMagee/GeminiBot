from asyncpg import Record, UndefinedTableError

import db
import db.shared as dbs
from db.table_creator import create_message_table


async def get_messages(chat_id: int, message_limit: int = None) -> list[Record]:
    if not message_limit:
        message_limit = await db.get_chat_parameter(chat_id, 'message_limit')

    async with dbs.pool.acquire() as conn:
        try:
            results = await conn.fetch(f"SELECT * FROM messages{await dbs.sanitize_chat_id(chat_id)} "
                                       f"WHERE deleted=false ORDER BY timestamp "
                                       f"LIMIT {message_limit}")

            return results
        except UndefinedTableError:
            await create_message_table(conn, await dbs.sanitize_chat_id(chat_id))
            await get_messages(chat_id)
