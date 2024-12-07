import db.shared as dbs


async def replace_message(chat_id: int, message_id: int, text: str):
    async with dbs.pool.acquire() as conn:
        result = await conn.execute("""
            UPDATE messages
            SET text = $1
            WHERE chat_id = $2 AND message_id = $3
            """, text, chat_id, message_id)
        if result.split(" ")[1] == "1":
            return True
        else:
            return False
