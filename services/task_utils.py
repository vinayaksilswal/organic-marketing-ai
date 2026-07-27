"""
=============================================================================
Background task helpers
=============================================================================
asyncio only keeps a *weak* reference to tasks created with create_task(), so
a fire-and-forget task can be garbage collected mid-execution. In this app
that meant a customer could add a business and have their creative generation
silently vanish. These helpers keep a strong reference until the task is done
and make failures visible in the logs instead of swallowing them.
=============================================================================
"""

from __future__ import annotations

import asyncio
from typing import Coroutine

from loguru import logger

_BACKGROUND_TASKS: set[asyncio.Task] = set()


def spawn_background(coro: Coroutine, label: str) -> asyncio.Task:
    """Run a coroutine detached, keeping it alive and logging any failure."""
    task = asyncio.create_task(coro)
    _BACKGROUND_TASKS.add(task)

    def _done(t: asyncio.Task) -> None:
        _BACKGROUND_TASKS.discard(t)
        if t.cancelled():
            logger.warning(f"Background task cancelled: {label}")
            return
        exc = t.exception()
        if exc:
            logger.opt(exception=exc).error(f"Background task failed: {label}")
        else:
            logger.info(f"Background task completed: {label}")

    task.add_done_callback(_done)
    return task


def pending_count() -> int:
    """How many detached tasks are still in flight (surfaced by admin status)."""
    return len(_BACKGROUND_TASKS)
