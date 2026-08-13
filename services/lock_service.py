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
import time
from typing import Dict

from loguru import logger

# How often to re-attempt a Redis lock while waiting. Short enough that a
# waiter starts promptly once the holder finishes, long enough that waiting
# two minutes is a few dozen commands rather than thousands.
_RETRY_INTERVAL = 1.5

# In-memory fallback locks (for single-instance deployments without Redis)
_memory_locks: Dict[str, asyncio.Lock] = {}


def _get_memory_lock(key: str) -> asyncio.Lock:
    """Get or create an in-memory asyncio lock for a given key."""
    if key not in _memory_locks:
        _memory_locks[key] = asyncio.Lock()
    return _memory_locks[key]


@contextlib.asynccontextmanager
async def distributed_lock(
    lock_key: str, timeout_seconds: int = 30, wait_seconds: float = 0
):
    """
    Acquires a distributed lock using Redis SET NX.
    Falls back to in-memory asyncio locks if Redis is unavailable.
    Yields True if acquired, False otherwise.

    wait_seconds is why this exists in its current form. Both paths used to
    give up the instant the lock was held, which turned any overlap into lost
    work rather than delayed work. Publishing a video to Instagram takes
    thirty to sixty seconds end to end, so a manual run starting while the
    scheduled one is mid-upload — or simply pressing the button twice — meant
    the second post was dropped with "Another post to this account is already
    in progress", and its asset was still marked as used so it never came
    back. That is the intermittency: it works, until two things coincide.

    Waiting costs a caller some seconds and preserves the post. Giving up
    costs nothing and loses it. For publishing, waiting is obviously right.

    The default stays 0 so callers that genuinely want "skip if busy" — the
    marketing loop's own overrun guard — keep that behaviour by not asking
    for anything different.
    """
    lock_name = f"lock:{lock_key}"
    deadline = time.monotonic() + max(wait_seconds, 0)

    # Try Redis first
    client = None
    try:
        import redis.asyncio as redis
        from config import settings

        client = redis.from_url(settings.redis_url)
        acquired = await client.set(lock_name, "locked", nx=True, ex=timeout_seconds)

        # Poll rather than block: SET NX has no blocking form, and a short
        # sleep between attempts is cheap next to a video upload.
        while not acquired and time.monotonic() < deadline:
            await asyncio.sleep(_RETRY_INTERVAL)
            acquired = await client.set(lock_name, "locked", nx=True, ex=timeout_seconds)

        try:
            if acquired:
                logger.debug(f"Acquired Redis lock: {lock_name}")
                yield True
            else:
                logger.warning(
                    f"Could not acquire Redis lock {lock_name} after "
                    f"{wait_seconds:.0f}s of waiting"
                )
                yield False
        finally:
            if acquired:
                await client.delete(lock_name)
                logger.debug(f"Released Redis lock: {lock_name}")
            await client.aclose()
        return

    except Exception as e:
        logger.debug(f"Redis unavailable for lock ({e}), using in-memory fallback")
        if client is not None:
            try:
                await client.aclose()
            except Exception:
                pass

    # Fallback to in-memory lock.
    lock = _get_memory_lock(lock_key)
    acquired = False
    try:
        remaining = deadline - time.monotonic()
        if remaining > 0:
            # asyncio.Lock.acquire() queues properly, so waiters are served in
            # order instead of racing each other.
            try:
                await asyncio.wait_for(lock.acquire(), timeout=remaining)
                acquired = True
            except asyncio.TimeoutError:
                acquired = False
        elif not lock.locked():
            await lock.acquire()
            acquired = True

        if acquired:
            logger.debug(f"Acquired memory lock: {lock_name}")
            yield True
        else:
            logger.warning(f"Memory lock busy: {lock_name}")
            yield False
    finally:
        # Guarded on our own acquisition, not on lock.locked(): another waiter
        # may hold it by now, and releasing someone else's lock is worse than
        # not releasing at all.
        if acquired:
            lock.release()
            logger.debug(f"Released memory lock: {lock_name}")
