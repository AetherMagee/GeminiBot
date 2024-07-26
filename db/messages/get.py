from asyncpg import Record

import db
import db.shared as dbs


async def get_messages(chat_id: int) -> list[Record]:
    async with dbs.pool.acquire() as conn:
        results = await conn.fetch(f"SELECT * FROM messages{await dbs.sanitize_chat_id(chat_id)} "
                                   f"WHERE deleted=false ORDER BY timestamp "
                                   f"LIMIT {await db.get_chat_parameter(chat_id, 'message_history_limit')}")

        return results
