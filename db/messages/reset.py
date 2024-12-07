import db.shared as dbs


async def mark_all_messages_as_deleted(chat_id: int):
    async with dbs.pool.acquire() as conn:
        await conn.execute("""
            UPDATE messages
            SET deleted = true
            WHERE chat_id = $1
            """, chat_id)

async def attempt_delete_message(chat_id: int, target: int) -> bool:
    async with dbs.pool.acquire() as conn:
        result = await conn.execute("""
            UPDATE messages
            SET deleted = true
            WHERE chat_id = $1 AND message_id = $2
            """, chat_id, target)
        if result.split(" ")[1] == "1":
            return True
        else:
            return False
