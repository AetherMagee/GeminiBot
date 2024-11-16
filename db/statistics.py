import datetime
from decimal import Decimal
from typing import Dict, List, Tuple

import asyncpg
from loguru import logger

import db.shared as dbs
from utils.definitions import chat_configs


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
        context_tokens: int,
        completion_tokens: int,
        model: str = None
) -> None:
    """Log a generation event with enhanced metrics"""
    try:
        async with dbs.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO statistics_generations 
                (timestamp, chat_id, user_id, endpoint, context_tokens, completion_tokens, 
                tokens_consumed, model)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                datetime.datetime.now(),
                chat_id,
                user_id,
                endpoint,
                context_tokens,
                completion_tokens,
                context_tokens + completion_tokens,
                model
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


async def migrate_statistics_table(conn):
    """Adds new columns to the statistics table for enhanced tracking"""
    migrations = [
        """ALTER TABLE statistics_generations 
           ADD COLUMN IF NOT EXISTS model TEXT""",

        """ALTER TABLE statistics_generations 
           ADD COLUMN IF NOT EXISTS context_tokens INTEGER DEFAULT 0""",

        """ALTER TABLE statistics_generations 
           ADD COLUMN IF NOT EXISTS completion_tokens INTEGER DEFAULT 0""",

        # Set existing tokens as completion tokens for backwards compatibility
        """UPDATE statistics_generations 
           SET completion_tokens = tokens_consumed, context_tokens = 0 
           WHERE completion_tokens IS NULL"""
    ]

    for migration in migrations:
        await conn.execute(migration)


async def get_model_usage(days: int = 30) -> List[Dict]:
    """Get usage statistics per model"""
    async with dbs.pool.acquire() as conn:
        # First, update NULL models to their defaults based on endpoint
        await conn.execute(
            """
            UPDATE statistics_generations
            SET model = CASE 
                WHEN endpoint = 'google' THEN $1
                WHEN endpoint = 'openai' THEN $2
                ELSE 'unknown'
            END
            WHERE model IS NULL
            """,
            chat_configs['google']['g_model']['default_value'].strip("'"),
            chat_configs['openai']['o_model']['default_value'].strip("'")
        )

        cutoff = datetime.datetime.now() - datetime.timedelta(days=days)

        # Get usage stats, handling both new and legacy token counting
        results = await conn.fetch(
            """
            SELECT 
                model,
                COUNT(*) as requests,
                SUM(CASE 
                    WHEN context_tokens > 0 OR completion_tokens > 0 THEN context_tokens
                    ELSE tokens_consumed * 0.95  -- For legacy records
                END) as context_tokens,
                SUM(CASE 
                    WHEN context_tokens > 0 OR completion_tokens > 0 THEN completion_tokens
                    ELSE tokens_consumed * 0.05  -- For legacy records
                END) as completion_tokens,
                SUM(COALESCE(tokens_consumed, context_tokens + completion_tokens)) as total_tokens
            FROM statistics_generations
            WHERE timestamp > $1 AND model IS NOT NULL
            GROUP BY model
            ORDER BY requests DESC
            """,
            cutoff
        )

        # Convert to list of dicts for easier manipulation
        usage_dict = {
            r['model']: dict(r) for r in results
        }

        # Add default models if not present
        default_models = {
            chat_configs['google']['g_model']['default_value'].strip("'"),
            chat_configs['openai']['o_model']['default_value'].strip("'")
        }

        for model in default_models:
            if model not in usage_dict:
                usage_dict[model] = {
                    'model': model,
                    'requests': 0,
                    'context_tokens': 0,
                    'completion_tokens': 0,
                    'total_tokens': 0
                }

        return sorted(
            usage_dict.values(),
            key=lambda x: x['requests'],
            reverse=True
        )


async def get_hourly_stats(hours: int) -> List[int]:
    """Get generation counts per hour for the last N hours"""
    async with dbs.pool.acquire() as conn:
        now = datetime.datetime.now()
        results = []
        for i in range(hours):
            start_time = now - datetime.timedelta(hours=i + 1)
            end_time = now - datetime.timedelta(hours=i)
            count = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM statistics_generations
                WHERE timestamp BETWEEN $1 AND $2
                """,
                start_time,
                end_time
            )
            results.append(count)
        return list(reversed(results))


async def calculate_costs(model_usage: List[Dict], prices: Dict) -> Dict:
    """Calculate costs based on token usage and pricing"""
    total_cost = Decimal('0')
    model_costs = {}

    default_pricing = prices.get('default', {'input': 0, 'output': 0})

    for usage in model_usage:
        model = usage['model']
        model_pricing = prices.get(model, default_pricing)

        # Convert tokens to Decimal and handle the division
        context_tokens = Decimal(str(usage['context_tokens']))
        completion_tokens = Decimal(str(usage['completion_tokens']))
        input_price = Decimal(str(model_pricing['input']))
        output_price = Decimal(str(model_pricing['output']))

        # Calculate costs for both input and output tokens
        context_cost = (context_tokens / Decimal('1000000')) * input_price
        completion_cost = (completion_tokens / Decimal('1000000')) * output_price
        model_cost = context_cost + completion_cost

        model_costs[model] = float(model_cost)  # Convert back to float for display
        total_cost += model_cost

    return {
        'total': float(total_cost),  # Convert back to float for display
        'per_model': model_costs
    }


async def get_cost_stats_for_entities(entity_type: str, limit: int = 5) -> List[Dict]:
    """Get token usage and cost estimates for users or chats"""
    async with dbs.pool.acquire() as conn:
        field = f"{entity_type}_id"

        results = await conn.fetch(
            f"""
            SELECT 
                {field},
                COUNT(*) as requests,
                SUM(CASE 
                    WHEN context_tokens > 0 OR completion_tokens > 0 THEN context_tokens
                    ELSE tokens_consumed * 0.95
                END) as context_tokens,
                SUM(CASE 
                    WHEN context_tokens > 0 OR completion_tokens > 0 THEN completion_tokens
                    ELSE tokens_consumed * 0.05
                END) as completion_tokens,
                model,
                SUM(COALESCE(tokens_consumed, context_tokens + completion_tokens)) as total_tokens
            FROM statistics_generations
            GROUP BY {field}, model
            ORDER BY total_tokens DESC
            """)

        # Organize by entity
        entities = {}
        for row in results:
            entity_id = row[field]
            if entity_id not in entities:
                entities[entity_id] = {
                    'id': entity_id,
                    'models': {},
                    'total_tokens': 0,
                    'total_requests': 0
                }

            entities[entity_id]['models'][row['model']] = {
                'context_tokens': row['context_tokens'],
                'completion_tokens': row['completion_tokens'],
                'total_tokens': row['total_tokens'],
                'requests': row['requests']
            }
            entities[entity_id]['total_tokens'] += row['total_tokens']
            entities[entity_id]['total_requests'] += row['requests']

        return sorted(
            entities.values(),
            key=lambda x: x['total_tokens'],
            reverse=True
        )[:limit]


async def get_total_cost_stats() -> Dict:
    """Get cost statistics for all time and last 30 days"""
    async with dbs.pool.acquire() as conn:
        thirty_days_ago = datetime.datetime.now() - datetime.timedelta(days=30)

        results = await conn.fetch(
            """
            SELECT 
                model,
                SUM(CASE 
                    WHEN context_tokens > 0 OR completion_tokens > 0 THEN context_tokens
                    ELSE tokens_consumed * 0.95
                END) as context_tokens,
                SUM(CASE 
                    WHEN context_tokens > 0 OR completion_tokens > 0 THEN completion_tokens
                    ELSE tokens_consumed * 0.05
                END) as completion_tokens,
                SUM(COALESCE(tokens_consumed, context_tokens + completion_tokens)) as total_tokens,
                COUNT(*) as requests
            FROM statistics_generations
            GROUP BY model
            """)

        recent_results = await conn.fetch(
            """
            SELECT 
                model,
                SUM(CASE 
                    WHEN context_tokens > 0 OR completion_tokens > 0 THEN context_tokens
                    ELSE tokens_consumed * 0.95
                END) as context_tokens,
                SUM(CASE 
                    WHEN context_tokens > 0 OR completion_tokens > 0 THEN completion_tokens
                    ELSE tokens_consumed * 0.05
                END) as completion_tokens,
                SUM(COALESCE(tokens_consumed, context_tokens + completion_tokens)) as total_tokens,
                COUNT(*) as requests
            FROM statistics_generations
            WHERE timestamp > $1
            GROUP BY model
            """,
            thirty_days_ago)

        return {
            'all_time': results,
            'last_30d': recent_results
        }
