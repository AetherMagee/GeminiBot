import datetime
from typing import Dict, List, Tuple

import asyncpg
from loguru import logger

import db.shared as dbs


async def create_statistics_table(conn: asyncpg.Connection) -> None:
    """Creates tables for storing statistics"""
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS statistics_generations (
            id serial PRIMARY KEY,
            timestamp timestamp NOT NULL,
            chat_id bigint NOT NULL,
            user_id bigint NOT NULL,
            endpoint text NOT NULL,
            tokens_consumed integer DEFAULT 0
        )
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_statistics_generations_timestamp 
        ON statistics_generations (timestamp DESC)
    """)


async def log_generation(
        chat_id: int,
        user_id: int,
        endpoint: str,
        tokens: int
) -> None:
    """Log a generation event"""
    try:
        async with dbs.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO statistics_generations 
                (timestamp, chat_id, user_id, endpoint, tokens_consumed)
                VALUES ($1, $2, $3, $4, $5)
                """,
                datetime.datetime.now(),
                chat_id,
                user_id,
                endpoint,
                tokens
            )
    except Exception as e:
        logger.error(f"Failed to log generation stats: {e}")


async def get_active_users(days: int) -> Tuple[int, List[int]]:
    """Get count and list of users who triggered generations in last N days"""
    async with dbs.pool.acquire() as conn:
        cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
        results = await conn.fetch(
            """
            SELECT DISTINCT user_id
            FROM statistics_generations
            WHERE timestamp > $1
            """,
            cutoff
        )
        users = [r['user_id'] for r in results]
        return len(users), users


async def get_top_users(days: int, limit: int = 5) -> List[Dict]:
    """Get top users by generation count in last N days"""
    async with dbs.pool.acquire() as conn:
        cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
        results = await conn.fetch(
            """
            SELECT user_id, COUNT(*) as generations
            FROM statistics_generations
            WHERE timestamp > $1
            GROUP BY user_id
            ORDER BY generations DESC
            LIMIT $2
            """,
            cutoff,
            limit
        )
        return [{'user_id': r['user_id'], 'generations': r['generations']} for r in results]


async def get_token_stats() -> Tuple[int, List[Dict]]:
    """Get total tokens consumed and top 5 chats by token consumption"""
    async with dbs.pool.acquire() as conn:
        total = await conn.fetchval(
            "SELECT COALESCE(SUM(tokens_consumed), 0) FROM statistics_generations"
        )

        top_chats = await conn.fetch(
            """
            SELECT chat_id, SUM(tokens_consumed) as tokens
            FROM statistics_generations
            GROUP BY chat_id
            ORDER BY tokens DESC
            LIMIT 5
            """
        )
        return total, [{'chat_id': r['chat_id'], 'tokens': r['tokens']} for r in top_chats]


async def get_tokens_consumed(days: int) -> int:
    """Get total tokens consumed in the last N days."""
    async with dbs.pool.acquire() as conn:
        cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
        total_tokens = await conn.fetchval(
            """
            SELECT COALESCE(SUM(tokens_consumed), 0)
            FROM statistics_generations
            WHERE timestamp >= $1
            """,
            cutoff
        )
        return total_tokens


async def get_generation_counts(days: int) -> int:
    """Get total number of generations in last N days"""
    async with dbs.pool.acquire() as conn:
        cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
        return await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM statistics_generations
            WHERE timestamp > $1
            """,
            cutoff
        )


async def get_generation_counts_period(start_time: datetime.datetime, end_time: datetime.datetime = None) -> int:
    """Get total number of generations in a custom time period"""
    async with dbs.pool.acquire() as conn:
        if not end_time:
            end_time = datetime.datetime.now()
        return await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM statistics_generations
            WHERE timestamp BETWEEN $1 AND $2
            """,
            start_time, end_time
        )


async def get_tokens_consumed_period(start_time: datetime.datetime, end_time: datetime.datetime = None) -> int:
    """Get total tokens consumed in a custom time period."""
    async with dbs.pool.acquire() as conn:
        if not end_time:
            end_time = datetime.datetime.now()
        total_tokens = await conn.fetchval(
            """
            SELECT COALESCE(SUM(tokens_consumed), 0)
            FROM statistics_generations
            WHERE timestamp BETWEEN $1 AND $2
            """,
            start_time, end_time
        )
        return total_tokens


async def get_request_count(chat_id: int, interval: datetime.timedelta) -> int:
    """Get the number of requests for a chat within a time interval"""
    async with dbs.pool.acquire() as conn:
        cutoff = datetime.datetime.now() - interval
        return await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM statistics_generations
            WHERE chat_id = $1 AND timestamp > $2
            """,
            chat_id,
            cutoff
        )
