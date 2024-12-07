from asyncpg import Connection
from loguru import logger

from utils.definitions import chat_configs


async def create_messages_table(conn: Connection) -> None:
    """
    Creates the messages table. Should only be called once at startup.
    """
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            umid serial PRIMARY KEY,
            chat_id bigint NOT NULL,
            message_id bigint NOT NULL,
            timestamp timestamp NOT NULL,
            sender_id bigint NOT NULL,
            sender_username text,
            sender_name text,
            text text,
            reply_to_message_id bigint DEFAULT NULL,
            reply_to_message_trimmed_text text DEFAULT NULL,
            media_file_id text DEFAULT NULL,
            media_type text DEFAULT NULL,
            deleted boolean NOT NULL DEFAULT false,
            UNIQUE (chat_id, message_id)
        )
    """)
    # Create indexes
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_messages_chat_id_timestamp ON messages (chat_id, timestamp DESC)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_chat_id_message_id ON messages (chat_id, message_id)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_chat_id_deleted ON messages (chat_id, deleted)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_chat_id_sender_id ON messages (chat_id, sender_id)")


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

    # Check existing column defaults and values
    # Claude 3.6 sonnet code ahead
    for parameter_list in chat_configs.keys():
        for parameter in chat_configs[parameter_list]:
            if parameter == 'chat_id':
                continue

            current_default = await conn.fetchval(
                f"SELECT column_default FROM information_schema.columns "
                f"WHERE table_name = 'chat_config' AND column_name = '{parameter}'"
            )

            if current_default is None:
                continue

            current_default = current_default.split('::', 1)[0]
            if current_default.startswith("'") and current_default.endswith("'"):
                current_default = current_default[1:-1]
            if current_default.lower() == 'true':
                current_default = True
            elif current_default.lower() == 'false':
                current_default = False
            elif current_default.replace('.', '').isdigit():
                if '.' in current_default:
                    current_default = float(current_default)
                else:
                    current_default = int(current_default)

            config_default = chat_configs[parameter_list][parameter]['default_value']
            if isinstance(config_default, str):
                config_default = config_default.strip("'")

            if current_default != config_default:
                logger.warning(
                    f"Default value mismatch for {parameter}: DB: {current_default} vs Config: {config_default}")

                if config_default is None:
                    config_default_sql = "NULL"
                elif isinstance(config_default, str):
                    config_default_sql = f"'{config_default}'"
                elif isinstance(config_default, bool):
                    config_default_sql = str(config_default)
                else:
                    config_default_sql = str(config_default)

                if current_default is None:
                    current_default_sql = "NULL"
                elif isinstance(current_default, str):
                    current_default_sql = f"'{current_default}'"
                elif isinstance(current_default, bool):
                    current_default_sql = str(current_default)
                else:
                    current_default_sql = str(current_default)

                await conn.execute(
                    f"ALTER TABLE chat_config ALTER COLUMN {parameter} SET DEFAULT {config_default_sql}"
                )

                res = await conn.execute(
                    f"UPDATE chat_config SET {parameter} = {config_default_sql} "
                    f"WHERE {parameter} IS NOT DISTINCT FROM {current_default_sql}"
                )
                logger.warning(f"Updated {str(res).split(' ')[1]} values for {parameter}")

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
