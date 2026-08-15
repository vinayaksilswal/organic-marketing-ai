"""Stored media is capped, and the cap is the one that bounds the storage bill.

Every plan has always declared a `media` limit and the billing screen has
always displayed it. Nothing ever checked it and nothing ever recorded it, so
the limit was decoration and the number on screen was a permanent zero --
while object storage, the largest variable cost in the product, ran unmetered.

The cap is a standing library size rather than a monthly upload meter, because
storage bills for what is held. A folder imported in January is still being
paid for in March, which an upload counter stops counting.
"""

import inspect

import pytest

from services import billing_service as billing
from routers import api as api_router
from routers import marketing as marketing_router


def test_every_plan_declares_a_media_limit():
    for code, plan in billing.PLANS.items():
        assert "media" in plan["limits"], f"{code} has no media limit"


@pytest.mark.parametrize("code", ["free", "starter", "growth"])
def test_paying_plans_still_cap_storage(code):
    """Only enterprise is unlimited. A null here is an unbounded storage bill."""
    assert billing.PLANS[code]["limits"]["media"] is not None


def test_media_is_counted_not_metered():
    """A COUNT cannot drift; a counter has to be incremented at every one of a
    dozen Media insert sites, forever."""
    src = inspect.getsource(billing.check_media_quota)
    assert "media_count" in src, "the cap no longer reads live rows"

    count_src = inspect.getsource(billing.media_count)
    assert "Media" in count_src and "func.count" in count_src


def test_the_billing_screen_reports_real_storage_use():
    """UsageCounter has no media rows, so reading usage there showed zero
    forever. The summary has to count."""
    src = inspect.getsource(billing.billing_summary)
    assert 'usage["media"] = await media_count' in src


def test_a_capped_customer_is_told_the_limit_and_the_way_out():
    src = inspect.getsource(billing.check_media_quota)
    assert "Delete" in src, "the message does not offer the free way out"
    assert "upgrade" in src.lower(), "the message does not offer the paid one"


def test_single_upload_is_gated():
    src = inspect.getsource(api_router.upload_media)
    assert "check_media_quota" in src, "/upload-media stores without checking"
    assert "402" in src


def test_bulk_upload_is_gated_before_the_batch_is_read():
    """A folder import is the one request that can blow a limit by three
    figures. Reading it all into a 512MB worker only to reject it turns a 402
    into an outage."""
    src = inspect.getsource(marketing_router.bulk_upload_media)
    assert "check_media_quota" in src, "/media/bulk-upload stores without checking"

    check = src.index("check_media_quota")
    read = src.index("await f.read()")
    assert check < read, "the batch is read into memory before the quota check"


def test_bulk_upload_counts_only_the_new_files():
    """Re-running an interrupted import must not be refused on assets the
    account already holds."""
    src = inspect.getsource(marketing_router.bulk_upload_media)
    assert "len(fresh)" in src, "the check counts the whole batch, duplicates included"
