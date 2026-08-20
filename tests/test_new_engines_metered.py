"""Every endpoint that spends money counts what it spent.

The four engines added most recently — Faceless Shorts, the Viral Validator,
PostShip, and the autopilot config — arrived with the quota checks missing on
two of them. Both call a paid model; neither counted it. A free account is
capped at three generations a month and could have run the validator and
PostShip without limit, which is the cheapest possible way to spend someone
else's API budget.

Two of these tests are about tenancy rather than money. The router's workspace
guard reads the X-Workspace-Id HEADER, so anything identified in the request
BODY is outside it. `analyze-algorithm` takes a media_id in the body.
"""

import inspect

import pytest

from routers import creative_api


# Endpoints that call a model and therefore must meter. The autopilot config
# endpoint is deliberately absent: it writes settings and calls nothing.
PAID_ENDPOINTS = [
    "generate_faceless_short_endpoint",
    "analyze_algorithm_endpoint",
    "generate_postship_endpoint",
]


@pytest.mark.parametrize("name", PAID_ENDPOINTS)
def test_a_paid_endpoint_checks_quota_before_spending(name):
    fn = getattr(creative_api, name)
    src = inspect.getsource(fn)
    assert "check_quota" in src, f"{name} calls a model without checking the plan"
    assert "402" in src, f"{name} refuses without the status code the client acts on"


@pytest.mark.parametrize("name", PAID_ENDPOINTS)
def test_the_check_comes_before_the_work(name):
    """Checking after the call means the money is already gone."""
    src = inspect.getsource(getattr(creative_api, name))
    check = src.index("check_quota")
    for marker in ("generate_postship_bundle(", "analyze_short_form_content(", "generate_faceless_short("):
        if marker in src:
            assert check < src.index(marker), f"{name} spends before it checks"


@pytest.mark.parametrize("name", ["analyze_algorithm_endpoint", "generate_postship_endpoint"])
def test_usage_is_recorded_not_just_checked(name):
    """A check with no record is a limit that never fills."""
    src = inspect.getsource(getattr(creative_api, name))
    assert "record_usage" in src, f"{name} checks the quota but never counts against it"


def test_a_body_supplied_media_id_is_scoped_to_its_owner():
    """The router guard covers the workspace HEADER. A media id in the body is
    outside it, so scoring another tenant's asset would return its caption."""
    src = inspect.getsource(creative_api.analyze_algorithm_endpoint)
    assert "media_item.userId != user_id" in src, (
        "analyze-algorithm reads a media row without checking who owns it"
    )


def test_postship_does_not_use_a_detached_profile():
    """The profile is read inside one session and used after it closes. Holding
    the object risks a lazy attribute raising in a path already paid for."""
    src = inspect.getsource(creative_api.generate_postship_endpoint)
    tail = src[src.index("generate_postship_bundle("):]
    assert "profile.id" not in tail, "a detached ORM object is used after its session closed"
    assert "profile_id" in tail
