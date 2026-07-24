"""
=============================================================================
Organic Marketing AI — Distributed Lock Service
=============================================================================
Provides distributed locks for preventing race conditions when posting
to social platforms. Falls back to in-memory asyncio locks if Redis
is unavailable (single-instance mode).
=============================================================================
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Dict

from loguru import logger

# In-memory fallback locks (for single-instance deployments without Redis)
_memory_locks: Dict[str, asyncio.Lock] = {}


def _get_memory_lock(key: str) -> asyncio.Lock:
    """Get or create an in-memory asyncio lock for a given key."""
    if key not in _memory_locks:
        _memory_locks[key] = asyncio.Lock()
    return _memory_locks[key]


@contextlib.asynccontextmanager
async def distributed_lock(lock_key: str, timeout_seconds: int = 30):
    """
    Acquires a distributed lock using Redis SET NX.
    Falls back to in-memory asyncio locks if Redis is unavailable.
    Yields True if acquired, False otherwise.
    """
    lock_name = f"lock:{lock_key}"

    # Try Redis first
    try:
        import redis.asyncio as redis
        from config import settings

        client = redis.from_url(settings.redis_url)
        acquired = await client.set(lock_name, "locked", nx=True, ex=timeout_seconds)

        try:
            if acquired:
                logger.debug(f"Acquired Redis lock: {lock_name}")
                yield True
            else:
                logger.warning(f"Failed to acquire Redis lock: {lock_name}")
                yield False
        finally:
            if acquired:
                await client.delete(lock_name)
                logger.debug(f"Released Redis lock: {lock_name}")
            await client.aclose()
        return

    except Exception as e:
        logger.debug(f"Redis unavailable for lock ({e}), using in-memory fallback")

    # Fallback to in-memory lock
    lock = _get_memory_lock(lock_key)
    try:
        acquired = lock.locked() is False
        if acquired:
            await lock.acquire()
            logger.debug(f"Acquired memory lock: {lock_name}")
            yield True
        else:
            logger.warning(f"Memory lock busy: {lock_name}")
            yield False
    finally:
        if acquired and lock.locked():
            lock.release()
            logger.debug(f"Released memory lock: {lock_name}")
