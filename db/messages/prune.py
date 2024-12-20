import datetime
from typing import Union

from loguru import logger

import db.shared as dbs


async def delete_old_messages(retention_days: int, target_chat: Union[int, None]):
    async with dbs.pool.acquire() as conn:
        initial_size = await conn.fetchval("SELECT pg_total_relation_size('messages');")

        cutoff_time = datetime.datetime.now() - datetime.timedelta(days=retention_days)

        delete_query = "DELETE FROM messages WHERE timestamp < $1"
        params = [cutoff_time]
        if target_chat is not None:
            delete_query += " AND chat_id = $2"
            params.append(target_chat)

        result = await conn.execute(delete_query, *params)  # The scary delete operation itself

        deleted_count = int(result.split(" ")[-1])

        logger.info(f"Deleted {deleted_count} messages from {target_chat if target_chat else 'all chats'}")

        # Perform VACUUM FULL on messages table to reclaim space
        await conn.execute("VACUUM FULL messages;")

        # Get new size of the messages table
        final_size = await conn.fetchval("SELECT pg_total_relation_size('messages');")

        size_diff = initial_size - final_size

        # Prettify sizes
        def prettify_size(size_in_bytes):
            for unit in ['bytes', 'KB', 'MB', 'GB', 'TB']:
                if size_in_bytes < 1024:
                    return f"{size_in_bytes:.2f} {unit}"
                size_in_bytes /= 1024
            return f"{size_in_bytes:.2f} PB"

        initial_size_pretty = prettify_size(initial_size)
        final_size_pretty = prettify_size(final_size)
        size_diff_pretty = prettify_size(size_diff)

        logger.info(f"{initial_size_pretty} -> {final_size_pretty} ({size_diff_pretty} reclaimed)")

        return {
            'deleted_count': deleted_count,
            'initial_size': initial_size_pretty,
            'final_size': final_size_pretty,
            'freed_space': size_diff_pretty
        }
