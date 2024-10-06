import os
import sys
import traceback

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
    logger.info("Creating a connection pool...")
    try:
        global pool
        pool = await asyncpg.create_pool(
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD"),
            host=os.getenv("POSTGRES_HOST"),
            database=os.getenv("POSTGRES_USER"),
            min_size=int(os.getenv("POSTGRES_POOL_MIN_CONNECTIONS")),
            max_size=int(os.getenv("POSTGRES_POOL_MAX_CONNECTIONS")),
            max_inactive_connection_lifetime=100
        )
        logger.info("Connection pool ready.")
    except Exception as e:
        traceback.print_exc()
        logger.error(f"Couldn't create connection pool: {e}")
        sys.exit(1)
