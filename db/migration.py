from loguru import logger

import db.shared as dbs


async def migrate_messages_tables():
    async with dbs.pool.acquire() as conn:
        table_list = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' AND 
                  table_name LIKE 'messages%' AND 
                  table_type = 'BASE TABLE' AND 
                  table_name != 'messages'
        """)

        total_migrated = 0
        for table in table_list:
            table_name = table['table_name']
            if table_name == 'messages':
                continue

            # Extract chat_id from table_name
            chat_id_str = table_name.replace('messages', '').replace('_', '-')
            try:
                chat_id = int(chat_id_str)
            except ValueError:
                print(f"Cannot parse chat_id from table name {table_name}")
                continue

            logger.info(f"Migrating table {table_name} for chat_id {chat_id}")

            await conn.execute(f"""
                INSERT INTO messages 
                (chat_id, message_id, timestamp, sender_id, sender_username, sender_name, text, 
                 reply_to_message_id, reply_to_message_trimmed_text, media_file_id, media_type, deleted)
                SELECT {chat_id}, message_id, timestamp, sender_id, sender_username, sender_name, text,
                       reply_to_message_id, reply_to_message_trimmed_text, media_file_id, media_type, deleted
                FROM {table_name}
                ON CONFLICT (chat_id, message_id) DO NOTHING;
            """)

            await conn.execute(f"DROP TABLE {table_name}")

            total_migrated += 1

        if total_migrated:
            logger.success(f"Migration completed. Total tables migrated: {total_migrated}")
