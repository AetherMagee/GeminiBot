import datetime

from loguru import logger

import db.shared
import db.shared as dbs


async def delete_old_messages(retention_days: int, target_chat: int or None):
    async with dbs.pool.acquire() as conn:
        cutoff_time = datetime.datetime.now() - datetime.timedelta(days=retention_days)
        deleted = {}

        if not target_chat:
            table_list = await conn.fetch(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name LIKE 'messages%'"
            )
        else:
            table_list = [{"table_name": "messages" + await db.shared.sanitize_chat_id(target_chat)}]

        for table in table_list:
            table_name = table['table_name']
            delete_query = f"DELETE FROM {table_name} WHERE timestamp < $1"
            result = await conn.execute(delete_query, cutoff_time)

            deleted_count = int(result.split(" ")[-1])
            logger.info(f"Deleted {deleted_count} messages from {table_name}")
            deleted[table_name] = deleted_count

        return deleted
