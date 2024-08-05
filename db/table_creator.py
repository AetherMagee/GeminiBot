from asyncpg import Connection
from loguru import logger

from db.chats import chat_config
from utils.definitions import chat_configs


async def create_message_table(conn: Connection, chat_id: str) -> None:
    """
    Creates a new table in the database for storing chat's messages.
    Fine to be called on every message.
    """
    await conn.execute(f"CREATE TABLE IF NOT EXISTS messages{chat_id}("
                       f"umid serial PRIMARY KEY, "
                       f"message_id bigint NOT NULL, "
                       f"timestamp timestamp NOT NULL, "
                       f"sender_id bigint NOT NULL, "
                       f"sender_username text, "
                       f"sender_name text, "
                       f"text text, "
                       f"reply_to_message_id bigint DEFAULT NULL, "
                       f"reply_to_message_trimmed_text text DEFAULT NULL, "
                       f"deleted boolean NOT NULL DEFAULT false)")


async def create_chat_config_table(conn: Connection) -> None:
    """
    Creates a new table in the database for storing chat configs.
    Should only be called on startup.
    TODO: Figure out what to do if columns are missing (e.g. when altering definitions and not resetting the DB)
    """
    command = "CREATE TABLE IF NOT EXISTS chat_config(chat_id bigint NOT NULL PRIMARY KEY"
    for parameter_list in chat_configs.keys():
        for parameter in chat_configs[parameter_list]:
            command += f", {parameter} {chat_configs[parameter_list][parameter]['type']} DEFAULT {chat_configs[parameter_list][parameter]['default_value']}"
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
                await conn.execute(f"ALTER TABLE chat_config ADD COLUMN IF NOT EXISTS "
                                   f"{parameter} {chat_configs[parameter_list][parameter]['type']} DEFAULT "
                                   f"{chat_configs[parameter_list][parameter]['default_value']}")
