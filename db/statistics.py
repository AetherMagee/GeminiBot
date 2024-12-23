import datetime
from decimal import Decimal
from typing import Dict, List, Tuple

import asyncpg
from loguru import logger

import db
import db.shared as dbs
from utils.definitions import chat_configs, prices


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

        f"""
            UPDATE statistics_generations
            SET model = CASE 
                WHEN endpoint = 'google' THEN '{chat_configs['google']['g_model']['default_value'].strip("'")}'
                WHEN endpoint = 'openai' THEN '{chat_configs['openai']['o_model']['default_value'].strip("'")}'
            END
            WHERE model IS NULL
            """,
    ]

    for migration in migrations:
        await conn.execute(migration)


async def get_model_usage(days: int = 30) -> List[Dict]:
    """Get usage statistics per model"""
    async with dbs.pool.acquire() as conn:
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


def get_model_price(model: str) -> Dict:
    """Get the price for a specific model"""

    if "gemini" in model:
        return {"input": 2.50, "output": 10.00}

    try:
        return prices[model]
    except KeyError:
        return {"input": 5.00, "output": 10.00}


async def calculate_costs(model_usage: List[Dict]) -> Dict:
    """Calculate costs based on token usage and pricing"""
    total_cost = Decimal('0')
    model_costs = {}

    for usage in model_usage:
        model = usage['model']
        model_pricing = get_model_price(model)

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


async def get_cache_stats():
    """Get statistics about the various LRU caches"""
    caches = {
        "Черный список": db.chats.blacklist.is_blacklisted,
        "Параметры": db.chats.chat_config.get_chat_parameter
    }

    stats = {}
    for name, cache in caches.items():
        cache_info = cache.cache_info()
        stats[name] = {
            "size": cache_info[3],
            "maxsize": cache_info[2],
            "hits": cache_info[0],
            "misses": cache_info[1],
            "hit_rate": round(cache_info[0] / (cache_info[0] + cache_info[1]) * 100, 1) if
            (cache_info[0] + cache_info[1]) > 0 else 0
        }
    return stats


async def get_database_stats() -> dict:
    """Get PostgreSQL database statistics"""
    async with dbs.pool.acquire() as conn:
        stats = {}

        # Database size
        size = await conn.fetchval("""
            SELECT pg_size_pretty(pg_database_size(current_database()))
        """)
        stats["total_size"] = size

        # Table sizes and row counts
        tables = await conn.fetch("""
            SELECT 
                relname as table_name,
                n_live_tup as row_count,
                pg_size_pretty(pg_total_relation_size(quote_ident(relname))) as total_size
            FROM pg_stat_user_tables
            ORDER BY pg_total_relation_size(quote_ident(relname)) DESC
        """)
        stats["tables"] = tables

        # Size of messages tables
        messages_size = await conn.fetchval("""
                    SELECT pg_size_pretty(pg_total_relation_size('messages'))
                    FROM pg_stat_user_tables
                """)
        stats["messages_tables_size"] = messages_size

        # Connection info
        connections = await conn.fetch("""
            SELECT 
                count(*) as total,
                count(*) filter (where state = 'active') as active,
                count(*) filter (where state = 'idle') as idle
            FROM pg_stat_activity 
            WHERE datname = current_database()
        """)
        stats["connections"] = connections[0]

        # Cache hit rates
        cache_stats = await conn.fetch("""
            SELECT 
                sum(heap_blks_read) as heap_read,
                sum(heap_blks_hit)  as heap_hit,
                sum(heap_blks_hit) / (sum(heap_blks_hit) + sum(heap_blks_read)) as ratio
            FROM pg_statio_user_tables
        """)

        total_blocks = cache_stats[0]["heap_read"] + cache_stats[0]["heap_hit"]
        stats["cache_hit_ratio"] = cache_stats[0]["ratio"] if total_blocks > 0 else 1.0

        return stats


async def get_entity_tokens_consumed(entity_id: int, entity_type: str, days: int = None) -> int:
    """Get total tokens consumed by an entity (chat or user) over the last N days"""
    async with dbs.pool.acquire() as conn:
        field = f"{entity_type}_id"

        if days:
            cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
            total_tokens = await conn.fetchval(
                f"""
                SELECT COALESCE(SUM(tokens_consumed), 0)
                FROM statistics_generations
                WHERE {field} = $1 AND timestamp >= $2
                """,
                entity_id, cutoff
            )
        else:
            # All time
            total_tokens = await conn.fetchval(
                f"""
                SELECT COALESCE(SUM(tokens_consumed), 0)
                FROM statistics_generations
                WHERE {field} = $1
                """,
                entity_id
            )
        return total_tokens


async def get_entity_model_usage(entity_id: int, entity_type: str, days: int = None) -> List[Dict]:
    """Get usage statistics per model for an entity (chat or user)"""
    async with dbs.pool.acquire() as conn:
        field = f"{entity_type}_id"

        if days:
            cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
            time_condition = "AND timestamp >= $2"
            params = [entity_id, cutoff]
        else:
            time_condition = ""
            params = [entity_id]

        results = await conn.fetch(
            f"""
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
            WHERE {field} = $1 {time_condition}
            GROUP BY model
            ORDER BY requests DESC
            """,
            *params
        )
        return [dict(r) for r in results]


async def get_entity_daily_counts(entity_id: int, entity_type: str, days: int = 7) -> List[int]:
    """Get daily generation counts for an entity (chat or user) over the last N days"""
    async with dbs.pool.acquire() as conn:
        field = f"{entity_type}_id"

        counts = []
        now = datetime.datetime.now()
        for i in range(days):
            start_time = (now - datetime.timedelta(days=(i + 1))).replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = (now - datetime.timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
            count = await conn.fetchval(
                f"""
                SELECT COUNT(*)
                FROM statistics_generations
                WHERE {field} = $1 AND timestamp >= $2 AND timestamp < $3
                """,
                entity_id, start_time, end_time
            )
            counts.append(count)
        return list(reversed(counts))


async def get_top_users_in_chat(chat_id: int, limit: int = 5) -> List[Dict]:
    """Get top users by generation count in a chat"""
    async with dbs.pool.acquire() as conn:
        results = await conn.fetch(
            """
            SELECT user_id, COUNT(*) as generations
            FROM statistics_generations
            WHERE chat_id = $1
            GROUP BY user_id
            ORDER BY generations DESC
            LIMIT $2
            """,
            chat_id,
            limit
        )
        return [{'user_id': r['user_id'], 'generations': r['generations']} for r in results]


async def get_entity_generation_counts(entity_id: int, entity_type: str, days: int = None) -> int:
    """Get total number of generations for an entity (chat or user) over the last N days"""
    async with dbs.pool.acquire() as conn:
        field = f"{entity_type}_id"

        if days:
            cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
            count = await conn.fetchval(
                f"""
                SELECT COUNT(*)
                FROM statistics_generations
                WHERE {field} = $1 AND timestamp >= $2
                """,
                entity_id, cutoff
            )
        else:
            # All time
            count = await conn.fetchval(
                f"""
                SELECT COUNT(*)
                FROM statistics_generations
                WHERE {field} = $1
                """,
                entity_id
            )
        return count


async def get_top_chats_for_user(user_id: int, limit: int = 3) -> List[Dict]:
    """Get top chats by generation count for a user"""
    async with dbs.pool.acquire() as conn:
        results = await conn.fetch(
            """
            SELECT chat_id, COUNT(*) as generations
            FROM statistics_generations
            WHERE user_id = $1
            GROUP BY chat_id
            ORDER BY generations DESC
            LIMIT $2
            """,
            user_id,
            limit
        )
        return [{'chat_id': r['chat_id'], 'generations': r['generations']} for r in results]
