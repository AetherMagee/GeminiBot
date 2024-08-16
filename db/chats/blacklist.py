from async_lru import alru_cache

import db.shared as dbs


@alru_cache(maxsize=1024)
async def is_blacklisted(target: int) -> bool:
    async with dbs.pool.acquire() as conn:
        result = await conn.fetch("SELECT * FROM blacklist WHERE entity_id=$1", target)
        if result:
            return True
        return False


async def add_to_blacklist(target: int) -> None:
    async with dbs.pool.acquire() as conn:
        await conn.execute("INSERT INTO blacklist (entity_id) VALUES ($1)", target)
    is_blacklisted.cache_invalidate(target)


async def remove_from_blacklist(target: int) -> None:
    async with dbs.pool.acquire() as conn:
        await conn.execute("DELETE FROM blacklist WHERE entity_id = $1", target)
    is_blacklisted.cache_invalidate(target)


