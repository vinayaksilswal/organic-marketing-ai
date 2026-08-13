"""Overlapping publishes queue instead of one being thrown away.

The organiflo account published to Facebook twice and Instagram once. The
missing post recorded "Another post to this Instagram account is already in
progress" — two runs started a minute apart, and an Instagram video takes
thirty to sixty seconds to upload, so the second met a held lock and was
dropped rather than delayed.

That is the shape of every "it works, then it breaks" report: nothing is
broken, two things simply coincided.
"""

import asyncio

import pytest

from services.lock_service import distributed_lock


async def _hold(key, seconds, log, name):
    async with distributed_lock(key, timeout_seconds=30, wait_seconds=0) as got:
        log.append((name, got))
        if got:
            await asyncio.sleep(seconds)


class TestWaiting:
    @pytest.mark.asyncio
    async def test_a_waiter_gets_the_lock_after_the_holder_finishes(self):
        key = "test-wait-success"
        log = []

        async def holder():
            async with distributed_lock(key, timeout_seconds=30) as got:
                log.append(("holder", got))
                await asyncio.sleep(0.3)

        async def waiter():
            await asyncio.sleep(0.05)   # start while the holder has it
            async with distributed_lock(key, timeout_seconds=30, wait_seconds=5) as got:
                log.append(("waiter", got))

        await asyncio.gather(holder(), waiter())

        assert ("holder", True) in log
        # The whole point: the second caller is served, not refused.
        assert ("waiter", True) in log

    @pytest.mark.asyncio
    async def test_without_waiting_the_second_caller_is_refused(self):
        """The old behaviour, pinned so the regression is visible if it returns."""
        key = "test-no-wait"
        log = []

        async def holder():
            async with distributed_lock(key, timeout_seconds=30) as got:
                log.append(("holder", got))
                await asyncio.sleep(0.3)

        async def waiter():
            await asyncio.sleep(0.05)
            async with distributed_lock(key, timeout_seconds=30, wait_seconds=0) as got:
                log.append(("waiter", got))

        await asyncio.gather(holder(), waiter())
        assert ("waiter", False) in log

    @pytest.mark.asyncio
    async def test_waiting_gives_up_rather_than_hanging(self):
        """A waiter must not block a worker forever behind a stuck holder."""
        key = "test-wait-timeout"
        log = []

        async def holder():
            async with distributed_lock(key, timeout_seconds=30) as got:
                log.append(("holder", got))
                await asyncio.sleep(1.2)

        async def waiter():
            await asyncio.sleep(0.05)
            async with distributed_lock(key, timeout_seconds=30, wait_seconds=0.3) as got:
                log.append(("waiter", got))

        await asyncio.gather(holder(), waiter())
        assert ("waiter", False) in log

    @pytest.mark.asyncio
    async def test_three_overlapping_callers_are_all_served(self):
        """Every publish gets its turn, none is silently discarded."""
        key = "test-wait-queue"
        served = []

        async def caller(name):
            async with distributed_lock(key, timeout_seconds=30, wait_seconds=8) as got:
                served.append((name, got))
                await asyncio.sleep(0.15)

        await asyncio.gather(caller("a"), caller("b"), caller("c"))
        assert len(served) == 3
        assert all(got for _, got in served), served

    @pytest.mark.asyncio
    async def test_different_accounts_never_block_each_other(self):
        """The lock is per account. One slow upload must not stall the rest."""
        order = []

        async def caller(key, name):
            async with distributed_lock(key, timeout_seconds=30, wait_seconds=5) as got:
                order.append((name, got))
                await asyncio.sleep(0.1)

        await asyncio.gather(
            caller("ig_post_account_one", "one"),
            caller("ig_post_account_two", "two"),
        )
        assert ("one", True) in order and ("two", True) in order


class TestRelease:
    @pytest.mark.asyncio
    async def test_the_lock_is_released_even_when_the_body_raises(self):
        """A failed publish must not leave the account locked out."""
        key = "test-release-on-error"

        with pytest.raises(RuntimeError):
            async with distributed_lock(key, timeout_seconds=30) as got:
                assert got
                raise RuntimeError("publish blew up")

        # Free immediately, with no waiting needed.
        async with distributed_lock(key, timeout_seconds=30, wait_seconds=0) as got:
            assert got, "the lock stayed held after an exception"
