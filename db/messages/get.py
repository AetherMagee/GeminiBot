from asyncpg import Record

import db
import db.shared as dbs


async def get_messages(chat_id: int, message_limit: int = None) -> list[Record]:
    if not message_limit:
        message_limit = await db.get_chat_parameter(chat_id, 'message_limit')

    async with dbs.pool.acquire() as conn:
        results = await conn.fetch("""
            SELECT * FROM messages
            WHERE chat_id = $1 AND deleted = false
            ORDER BY timestamp DESC
            LIMIT $2
            """, chat_id, message_limit)

        if not results:
            return []
        results.reverse()
        return results

async def get_specific_message(chat_id: int, message_id: int) -> Record | None:
    async with dbs.pool.acquire() as conn:
        result = await conn.fetchrow("""
            SELECT * FROM messages 
            WHERE chat_id = $1 AND message_id = $2 AND deleted = false
            """, chat_id, message_id)
        return result
