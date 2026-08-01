"""Creating a workspace must survive its own background plumbing.

The workspace row is committed before background tasks are scheduled, so a
failure while scheduling means the user sees an error for a business that
already exists. Reported live: a 500 on POST /api/v1/businesses which had
created the workspace anyway.

Setting a sys.modules entry to None makes `import x` raise ImportError, which
reproduces a missing dependency without uninstalling anything.
"""

import sys

import pytest

from services.onboarding_service import OnboardingService


@pytest.fixture
def no_redis(monkeypatch):
    """Force the inline fallback path."""
    async def _fail(*a, **k):
        raise ConnectionError("Redis unavailable")

    import arq
    monkeypatch.setattr(arq, "create_pool", _fail)


@pytest.mark.asyncio
async def test_missing_optional_dependency_does_not_fail_creation(no_redis, monkeypatch):
    """The exact live failure.

    Redis was down, so the fallback ran inline. That fallback imports
    catalog_service, which imports aiohttp at module level. aiohttp was never
    declared in requirements, so the ImportError escaped through
    create_business_profile as a 500 — after the workspace was committed.
    """
    monkeypatch.setitem(sys.modules, "services.catalog_service", None)

    # Must return rather than raise.
    await OnboardingService._enqueue_onboarding_tasks(
        "u1", "ws1", "https://example.com/feed.xml"
    )


@pytest.mark.asyncio
async def test_creative_population_failure_is_contained(no_redis, monkeypatch):
    monkeypatch.setitem(sys.modules, "services.creative_service", None)
    await OnboardingService._enqueue_onboarding_tasks("u1", "ws1", None)


@pytest.mark.asyncio
async def test_both_unavailable_still_returns(no_redis, monkeypatch):
    monkeypatch.setitem(sys.modules, "services.creative_service", None)
    monkeypatch.setitem(sys.modules, "services.catalog_service", None)
    await OnboardingService._enqueue_onboarding_tasks(
        "u1", "ws1", "https://example.com/feed.xml"
    )


@pytest.mark.asyncio
async def test_creative_failure_does_not_block_catalog_sync(no_redis, monkeypatch):
    """The two tasks are isolated, so one broken module cannot stop the other
    being scheduled."""
    monkeypatch.setitem(sys.modules, "services.creative_service", None)

    # catalog_service imports aiohttp at module level, which may genuinely be
    # absent here. Stubbing it keeps this test about isolation rather than
    # about which packages happen to be installed on the machine running it.
    import types
    stub = types.ModuleType("services.catalog_service")

    async def sync_workspace_catalog(workspace_id):
        return None

    stub.sync_workspace_catalog = sync_workspace_catalog
    monkeypatch.setitem(sys.modules, "services.catalog_service", stub)

    scheduled = []
    import services.onboarding_service as osvc
    monkeypatch.setattr(
        osvc, "spawn_background", lambda coro, name: scheduled.append(name)
    )

    await OnboardingService._enqueue_onboarding_tasks(
        "u1", "ws1", "https://example.com/feed.xml"
    )
    assert any("sync_workspace_catalog" in s for s in scheduled), (
        f"catalog sync was skipped after creative population failed: {scheduled}"
    )
