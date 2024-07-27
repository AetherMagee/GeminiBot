import os
import sys

import asyncpg
from loguru import logger

pool: asyncpg.Pool = None


async def sanitize_chat_id(chat_id: int) -> str:
    """
    Postgres is annoying with its table name limitations.
    This simply replaces a "-" with a "_"
    """
    return str(chat_id).replace("-", "_")


async def initialize_connection_pool() -> None:
    logger.debug("Creating a connection pool...")
    try:
        global pool
        pool = await asyncpg.create_pool(
            user=os.environ.get("POSTGRES_USER"),
            password=os.environ.get("POSTGRES_PASSWORD"),
            host="db",
            database=os.environ.get("POSTGRES_USER"),
            min_size=2,
            max_size=10
        )
        logger.info("Connection pool ready.")
    except Exception as e:
        logger.error(f"Couldn't create connection pool: {e}")
        sys.exit(1)
