"""
=============================================================================
Organic Marketing AI — Distributed Lock Service
=============================================================================
Provides Redis-based distributed locks to ensure idempotent API requests and
prevent rate limits / race conditions when posting to social platforms.
=============================================================================
"""

import contextlib
import redis.asyncio as redis
from loguru import logger
from config import settings

# Global Redis pool
_redis_client = None

def get_redis_client():
    global _redis_client
    if not _redis_client:
        _redis_client = redis.from_url(settings.redis_url)
    return _redis_client

@contextlib.asynccontextmanager
async def distributed_lock(lock_key: str, timeout_seconds: int = 30):
    """
    Acquires a distributed lock using Redis SET NX.
    Yields True if acquired, False otherwise.
    """
    client = get_redis_client()
    lock_name = f"lock:{lock_key}"
    
    acquired = await client.set(lock_name, "locked", nx=True, ex=timeout_seconds)
    
    try:
        if acquired:
            logger.debug(f"Acquired distributed lock: {lock_name}")
            yield True
        else:
            logger.warning(f"Failed to acquire distributed lock: {lock_name}")
            yield False
    finally:
        if acquired:
            await client.delete(lock_name)
            logger.debug(f"Released distributed lock: {lock_name}")
