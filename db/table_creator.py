from asyncpg import Connection


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
    TODO: Alter rows as the bot gets made
    """
    await conn.execute("CREATE TABLE IF NOT EXISTS chat_config("
                       "chat_id bigint PRIMARY KEY, "
                       "system_prompt_mode integer DEFAULT 0, "
                       "custom_system_prompt text DEFAULT NULL, "
                       "message_history_limit integer DEFAULT 1000, "
                       "max_attempts integer DEFAULT 3)")
