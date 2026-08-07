"""The OAuth redirect must point at a service that is actually serving.

After a migration the previous Render host was suspended. The Meta app still
redirected there, so every customer clicking "Connect Facebook" landed on a
page reading "This service has been suspended by its owner" -- carrying a valid
authorisation code in the query string that nothing was alive to exchange.

Nothing in the platform noticed. Health checks passed on the new host, the
scheduler kept publishing, and the only symptom was that no new account could
ever be connected. That is the kind of break that hides until a customer
reports it, which for a self-serve product means until they leave.
"""

import re

import httpx
import pytest

from config import settings

LIVE = "https://organic-marketing-ai-0abh.onrender.com"
SUSPENDED = "https://organic-marketing-ai1.onrender.com"


def test_the_configured_host_is_not_the_suspended_one():
    assert SUSPENDED not in (settings.backend_public_url or ""), (
        "OAuth redirects point at the suspended service; no customer can "
        "connect an account"
    )


def test_the_redirect_uri_is_absolute_and_https():
    """Meta rejects a relative or http redirect outright, and the failure
    surfaces as a generic 'URL blocked' with no detail."""
    from routers.meta_oauth import _redirect_uri

    uri = _redirect_uri()
    assert uri.startswith("https://"), uri
    assert uri.endswith("/api/v1/meta/callback"), uri
    assert " " not in uri


def test_the_redirect_uri_has_no_trailing_slash_before_the_path():
    """A double slash produces a URI that does not match what is registered in
    the app settings, and Meta compares them literally."""
    from routers.meta_oauth import _redirect_uri

    assert "//api/v1" not in _redirect_uri()


def test_a_missing_host_fails_loudly_rather_than_building_a_broken_uri():
    from routers.meta_oauth import _redirect_uri

    import routers.meta_oauth as mod

    original = mod.settings.backend_public_url
    try:
        mod.settings.backend_public_url = ""
        with pytest.raises(Exception) as exc:
            _redirect_uri()
        assert "BACKEND_PUBLIC_URL" in str(exc.value)
    finally:
        mod.settings.backend_public_url = original


@pytest.mark.slow
def test_the_configured_host_actually_answers():
    """The point of the whole file: a URI that resolves to a suspended service
    is worse than a misconfigured one, because it looks correct."""
    url = (settings.backend_public_url or "").rstrip("/") + "/health"
    if not url.startswith("https://"):
        pytest.skip("no public host configured")
    try:
        r = httpx.get(url, timeout=60)
    except Exception as e:
        pytest.fail(f"configured OAuth host is unreachable: {type(e).__name__}")
    assert r.status_code == 200, (
        f"configured OAuth host returned {r.status_code}; customers cannot "
        f"complete Facebook Login against it"
    )
    assert re.search(r'"status"\s*:\s*"healthy"', r.text), r.text[:200]
