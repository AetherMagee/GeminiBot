from asyncpg import UndefinedTableError

import db
import db.shared as dbs


async def replace_message(chat_id: int, message_id: int, text: str):
    san_chat_id = await dbs.sanitize_chat_id(chat_id)
    async with dbs.pool.acquire() as conn:
        try:
            result = await conn.execute(f"UPDATE messages{san_chat_id} SET text=$1 WHERE message_id=$2", text, message_id)
            if str(result).split(" ")[1] == "1":
                return True
            else:
                return False
        except UndefinedTableError:
            await db.table_creator.create_message_table(conn, san_chat_id)
            return True

