from asyncpg import Connection
from loguru import logger

from utils.definitions import chat_configs


async def create_message_table(conn: Connection, chat_id: str) -> None:
    """
    Creates a new table in the database for storing chat's messages and ensures the necessary indexes.
    Fine to be called on every message.
    """
    table_name = f"messages{chat_id}"
    await conn.execute(f"CREATE TABLE IF NOT EXISTS {table_name} ("
                       f"umid serial PRIMARY KEY, "
                       f"message_id bigint NOT NULL, "
                       f"timestamp timestamp NOT NULL, "
                       f"sender_id bigint NOT NULL, "
                       f"sender_username text, "
                       f"sender_name text, "
                       f"text text, "
                       f"reply_to_message_id bigint DEFAULT NULL, "
                       f"reply_to_message_trimmed_text text DEFAULT NULL, "
                       f"media_file_id text DEFAULT NULL, "
                       f"media_type text DEFAULT NULL, "
                       f"deleted boolean NOT NULL DEFAULT false)"
                       )
    # Create indexes for performance improvement
    await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_timestamp ON {table_name} (timestamp DESC)")
    await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_deleted ON {table_name} (deleted)")
    await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_message_id ON {table_name} (message_id)")
    await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_sender_id ON {table_name} (sender_id)")


async def create_chat_config_table(conn: Connection) -> None:
    """
    Creates a new table in the database for storing chat configs.
    Should only be called on startup.
    """
    command = "CREATE TABLE IF NOT EXISTS chat_config(chat_id bigint NOT NULL PRIMARY KEY"
    for parameter_list in chat_configs.keys():
        for parameter in chat_configs[parameter_list]:
            default_value = chat_configs[parameter_list][parameter]['default_value']
            if default_value is None:
                default_value = "NULL"

            command += (f", {parameter} {chat_configs[parameter_list][parameter]['type']} DEFAULT "
                        f"{default_value}")
    command += ")"

    await conn.execute(command)

    # Check if all the columns are in place
    for parameter_list in chat_configs.keys():
        for parameter in chat_configs[parameter_list]:
            check_result = await conn.fetch(f"SELECT EXISTS (SELECT 1 "
                                            f"FROM information_schema.columns WHERE table_schema='public' "
                                            f"AND table_name='chat_config' AND column_name='{parameter}')")
            if not check_result[0]["exists"]:
                logger.error(f"{parameter} is missing in your chat_config table!")
                default_value = chat_configs[parameter_list][parameter]['default_value']
                if default_value is None:
                    default_value = "NULL"
                await conn.execute(f"ALTER TABLE chat_config ADD COLUMN IF NOT EXISTS "
                                   f"{parameter} {chat_configs[parameter_list][parameter]['type']} DEFAULT "
                                   f"{default_value}")


async def create_blacklist_table(conn: Connection) -> None:
    command = "CREATE TABLE IF NOT EXISTS blacklist(internal_id serial PRIMARY KEY, entity_id bigint NOT NULL)"
    await conn.execute(command)


async def drop_orphan_columns(conn: Connection) -> None:
    # Get the expected columns from chat_configs
    expected_columns = set()
    for param_group in chat_configs.values():
        for param, config in param_group.items():
            expected_columns.add(param)
    expected_columns.add("chat_id")

    # Fetch existing columns from 'chat_config' table
    existing_columns_query = """
    SELECT column_name
    FROM information_schema.columns
    WHERE table_name = 'chat_config'
    """
    existing_columns = {row['column_name'] for row in await conn.fetch(existing_columns_query)}

    # Identify orphan columns
    orphan_columns = existing_columns - expected_columns

    # Drop orphan columns
    for column in orphan_columns:
        try:
            logger.warning(f"Dropping orphan column from chat_config: {column}")
            await conn.execute(f"ALTER TABLE chat_config DROP COLUMN {column}")
        except Exception as e:
            logger.error(f"Failed to drop column {column} from chat_config: {e}")


async def create_indexes(conn: Connection) -> None:
    table_names = await conn.fetch(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name LIKE 'messages%'"
    )

    for table in table_names:
        table_name = table['table_name']
        # Add indexes if not present
        await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_timestamp ON "
                           f"{table_name} (timestamp DESC)")
        await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_deleted ON "
                           f"{table_name} (deleted)")
        await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_message_id ON "
                           f"{table_name} (message_id)")
        await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_sender_id ON "
                           f"{table_name} (sender_id)")
