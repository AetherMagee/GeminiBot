import datetime
from typing import Dict, List, Optional

import asyncpg
from loguru import logger

import db.shared as dbs
from utils.definitions import prices, DEFAULT_INPUT_PRICE, DEFAULT_OUTPUT_PRICE
from utils.usernames import get_entity_title


# Database Schema Management
async def create_statistics_table(conn: asyncpg.Connection) -> None:
    """Creates tables for storing statistics"""
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS statistics_generations (
            id serial PRIMARY KEY,
            timestamp timestamp NOT NULL,
            chat_id bigint NOT NULL,
            user_id bigint NOT NULL,
            endpoint text NOT NULL,
            tokens_consumed integer DEFAULT 0,
            model TEXT,
            context_tokens INTEGER DEFAULT 0,
            completion_tokens INTEGER DEFAULT 0
        )
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_statistics_generations_timestamp 
        ON statistics_generations (timestamp DESC)
    """)


async def migrate_statistics_table(conn: asyncpg.Connection) -> None:
    """Adds new columns to the statistics table for enhanced tracking"""
    migrations = [
        """ALTER TABLE statistics_generations 
           ADD COLUMN IF NOT EXISTS model TEXT""",
        """ALTER TABLE statistics_generations 
           ADD COLUMN IF NOT EXISTS context_tokens INTEGER DEFAULT 0""",
        """ALTER TABLE statistics_generations 
           ADD COLUMN IF NOT EXISTS completion_tokens INTEGER DEFAULT 0""",
        """UPDATE statistics_generations 
           SET completion_tokens = tokens_consumed, context_tokens = 0 
           WHERE completion_tokens IS NULL"""
    ]

    for migration in migrations:
        await conn.execute(migration)


# Core Statistics Logging
async def log_generation(
        chat_id: int,
        user_id: int,
        endpoint: str,
        context_tokens: int,
        completion_tokens: int,
        model: str = None
) -> None:
    """Log a generation event with token usage metrics"""
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


# Time-based Query Helpers
async def get_stats_for_period(
        start_time: datetime.datetime,
        end_time: Optional[datetime.datetime] = None
) -> Dict:
    """Get comprehensive statistics for a time period"""
    if not end_time:
        end_time = datetime.datetime.now()

    async with dbs.pool.acquire() as conn:
        stats = {}

        # Get basic counts
        stats['generation_count'] = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM statistics_generations
            WHERE timestamp BETWEEN $1 AND $2
            """,
            start_time, end_time
        )

        # Get token usage per model
        model_usage = await conn.fetch(
            """
            SELECT 
                model,
                COUNT(*) as requests,
                SUM(context_tokens) as context_tokens,
                SUM(completion_tokens) as completion_tokens,
                SUM(tokens_consumed) as total_tokens
            FROM statistics_generations
            WHERE timestamp BETWEEN $1 AND $2
            GROUP BY model
            """,
            start_time, end_time
        )
        stats['model_usage'] = [dict(row) for row in model_usage]

        # Get unique users
        stats['unique_users'] = await conn.fetchval(
            """
            SELECT COUNT(DISTINCT user_id)
            FROM statistics_generations
            WHERE timestamp BETWEEN $1 AND $2
            """,
            start_time, end_time
        )

        return stats


# Cost Calculation
def calculate_model_cost(
        context_tokens: int,
        completion_tokens: int,
        model: str
) -> float:
    """
    Calculate cost for a specific model's usage.
    All Gemini models use the same fixed pricing regardless of version.
    Falls back to default pricing for unknown non-Gemini models.
    """
    # Fixed pricing for all Gemini models
    if model and 'gemini' in model.lower():
        return (context_tokens / 1_000_000) * 2.50 + (completion_tokens / 1_000_000) * 10.00

    # For all other models, use the pricing dictionary or defaults
    model_prices = prices.get(model, {"input": DEFAULT_INPUT_PRICE, "output": DEFAULT_OUTPUT_PRICE})

    context_cost = (context_tokens / 1_000_000) * model_prices["input"]
    completion_cost = (completion_tokens / 1_000_000) * model_prices["output"]

    return context_cost + completion_cost


async def get_cost_analysis(
        start_time: datetime.datetime,
        end_time: Optional[datetime.datetime] = None
) -> Dict:
    """Get comprehensive cost analysis for a time period"""
    stats = await get_stats_for_period(start_time, end_time)

    total_cost = 0.0
    model_costs = {}

    for model_stat in stats['model_usage']:
        model = model_stat['model']
        cost = calculate_model_cost(
            model_stat['context_tokens'],
            model_stat['completion_tokens'],
            model
        )
        model_costs[model] = cost
        total_cost += cost

    return {
        'total_cost': total_cost,
        'per_model': model_costs,
        'model_usage': stats['model_usage']
    }


# Entity Statistics (Users/Chats)
async def get_entity_stats(
        entity_type: str,
        limit: int = 5,
        days: int = 30
) -> List[Dict]:
    """Get usage statistics for users or chats"""
    if entity_type not in ['user', 'chat']:
        raise ValueError("Entity type must be 'user' or 'chat'")

    cutoff = datetime.datetime.now() - datetime.timedelta(days=days)

    async with dbs.pool.acquire() as conn:
        results = await conn.fetch(
            f"""
            SELECT 
                {entity_type}_id as entity_id,
                model,
                COUNT(*) as requests,
                SUM(context_tokens) as context_tokens,
                SUM(completion_tokens) as completion_tokens,
                SUM(tokens_consumed) as total_tokens
            FROM statistics_generations
            WHERE timestamp > $1
            GROUP BY {entity_type}_id, model
            """,
            cutoff
        )

        # Process results into entity-centric format
        entities = {}
        for row in results:
            entity_id = row['entity_id']
            if entity_id not in entities:
                entities[entity_id] = {
                    'id': entity_id,
                    'name': await get_entity_title(entity_id),
                    'models': {},
                    'total_tokens': 0,
                    'total_requests': 0,
                    'total_cost': 0.0
                }

            model = row['model']
            entities[entity_id]['models'][model] = {
                'requests': row['requests'],
                'context_tokens': row['context_tokens'],
                'completion_tokens': row['completion_tokens'],
                'total_tokens': row['total_tokens']
            }

            cost = calculate_model_cost(
                row['context_tokens'],
                row['completion_tokens'],
                model
            )

            entities[entity_id]['total_tokens'] += row['total_tokens']
            entities[entity_id]['total_requests'] += row['requests']
            entities[entity_id]['total_cost'] += cost

        # Sort and limit results
        sorted_entities = sorted(
            entities.values(),
            key=lambda x: x['total_tokens'],
            reverse=True
        )[:limit]

        return sorted_entities


# Activity Patterns
async def get_hourly_activity(hours: int = 24) -> List[int]:
    """Get generation counts per hour for the specified period"""
    async with dbs.pool.acquire() as conn:
        now = datetime.datetime.now()
        counts = []

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
            counts.append(count)

        return list(reversed(counts))
