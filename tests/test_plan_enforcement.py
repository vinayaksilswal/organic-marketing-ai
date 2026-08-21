"""The subscription has to be enforced where the value is delivered.

Manual posting through the API was always metered. The autonomous loop -- the
thing the subscription exists to sell -- was not. So the free tier advertised
"5 published posts a month" while the scheduler published every one to four
hours, indefinitely, unmetered.

Connect an account on the free plan and you received the entire paid product,
forever, for nothing. There was no reason for any customer to upgrade, which
makes this a pricing bug rather than a missing feature.
"""

import inspect

import pytest

import worker
from services import billing_service as billing


@pytest.fixture(scope="module")
def task_source() -> str:
    return inspect.getsource(worker.context_aggregation_task)


def test_the_autonomous_path_checks_the_plan(task_source):
    assert "check_quota" in task_source, (
        "the scheduled publish path still ignores the customer's plan"
    )


def test_the_check_happens_before_publishing(task_source):
    """Checking after the post has gone out bills for something already given
    away."""
    check = task_source.index("check_quota")
    assert "publish_everywhere" in task_source, "the publishing landmark moved again"
    publish = task_source.index("publish_everywhere")
    assert check < publish


def test_usage_is_recorded_only_on_success(task_source):
    """A failed attempt must not consume an allowance -- that turns an outage
    into a bill the customer pays twice for."""
    assert "record_usage" in task_source
    record = task_source.index("record_usage")
    success = task_source.index("if is_success:")
    assert success < record, "usage is recorded regardless of the outcome"


def test_one_post_counts_once_across_platforms(task_source):
    """A post carried to Facebook and Instagram is one published post, not
    two. Counting per platform would halve every plan's real allowance."""
    assert task_source.count("record_usage") == 1


def test_over_quota_drafts_rather_than_failing(task_source):
    """A workspace at its limit is behaving exactly as its plan describes.
    Recording a draft leaves the operator something to publish by hand."""
    assert "auto_approve = False" in task_source
    assert "Plan limit" in task_source


@pytest.mark.parametrize("code,expected", [
    ("free", 5),
    ("starter", 60),
    ("growth", 300),
    ("agency", None),
])
def test_the_published_limits_are_what_the_plans_advertise(code, expected):
    """The pricing page and the enforcement have to agree, or the product is
    either lying to buyers or leaking revenue."""
    assert billing.PLANS[code]["limits"]["posts"] == expected


def test_the_free_tier_cannot_out_post_the_paid_one():
    free = billing.PLANS["free"]["limits"]["posts"]
    starter = billing.PLANS["starter"]["limits"]["posts"]
    assert free < starter, "the free plan is not actually limited"


def test_a_metered_free_plan_still_demonstrates_the_product():
    """Five posts a month has to be enough to see it working, or the free tier
    sells nothing. At one post a day it is five days of evidence."""
    assert billing.PLANS["free"]["limits"]["posts"] >= 3


def test_enterprise_is_granted_not_purchasable():
    """Unlimited must never be self-selectable at checkout."""
    assert "enterprise" not in billing.PAID_PLANS
    assert billing.PLANS["enterprise"].get("hidden") is True
