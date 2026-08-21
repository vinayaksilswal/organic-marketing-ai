"""Connecting LinkedIn, and posting as somebody who exists.

services/linkedin_service.py could post from the day it was written and the
worker calls it on every publish. It never posted once, and two separate
things stopped it.

Nothing could put a token in the database -- the interface asked a customer to
obtain and paste a LinkedIn access token by hand, which almost nobody can do,
and which expires in sixty days with no refresh and no warning.

And `_get_credentials` returned a single global LINKEDIN_ORGANIZATION_ID from
the environment, which was never set. `post_text` returns None without it, so
every workspace failed the same way regardless of tokens.

The actor is stored per connection now. urn:li:person:xxx needs only
w_member_social; urn:li:organization:123 needs LinkedIn's Community Management
API and app review. A customer publishes on their profile this week and moves
to a Page when the review clears, without a second code path.
"""

import inspect

import pytest

from routers import linkedin_oauth
from services.linkedin_service import LinkedInService


SRC_CONNECT = inspect.getsource(linkedin_oauth.linkedin_connect)
SRC_CALLBACK = inspect.getsource(linkedin_oauth.linkedin_callback)
SRC_CREDS = inspect.getsource(LinkedInService._get_credentials)


# =============================================================================
# Reachable and guarded
# =============================================================================

def test_the_endpoints_are_registered():
    from fastapi.testclient import TestClient

    import main

    with TestClient(main.app, raise_server_exceptions=False) as c:
        assert c.get("/api/v1/linkedin/connect").status_code == 401
        assert c.post("/api/v1/linkedin/disconnect").status_code == 401


def test_a_workspace_that_is_not_yours_is_refused():
    assert "bp.userId != user_id" in SRC_CONNECT
    assert "bp.userId != user_id" in inspect.getsource(linkedin_oauth.linkedin_disconnect)


def test_missing_credentials_give_a_503_that_names_them():
    assert "503" in SRC_CONNECT
    assert "LINKEDIN_CLIENT_ID" in SRC_CONNECT


# =============================================================================
# Scopes that do not need app review
# =============================================================================

def test_the_scopes_avoid_app_review():
    """w_member_social posts as a person and needs no review. Anything
    organization-scoped does, and would make this unusable on day one."""
    assert "w_member_social" in linkedin_oauth.SCOPES
    assert "openid" in linkedin_oauth.SCOPES
    assert "w_organization_social" not in linkedin_oauth.SCOPES


def test_the_member_id_is_read_rather_than_assumed():
    """Without the actor URN every post is rejected, so a missing sub claim
    must fail loudly at connect time rather than silently at post time."""
    assert "userinfo" in SRC_CALLBACK.lower()
    assert 'profile.get("sub")' in SRC_CALLBACK
    assert "did not return your profile id" in SRC_CALLBACK


# =============================================================================
# The half that actually posts
# =============================================================================

def test_the_actor_comes_from_the_connection_not_one_global_env_var():
    assert "linkedinActorUrn" in SRC_CREDS
    assert "linkedinActorUrn" in SRC_CALLBACK


def test_the_env_var_still_works_as_a_fallback():
    """An operator who has completed app review should be able to point every
    workspace at one Page without reconnecting them."""
    assert "default_org_id" in SRC_CREDS
    assert "urn:li:organization:" in SRC_CREDS


def test_a_stored_urn_is_not_wrapped_in_another_prefix():
    """The stored value is already a complete URN. Rebuilding it as
    urn:li:organization:{value} is what would break personal posting."""
    for method in ("post_text", "share_article"):
        fn = getattr(LinkedInService, method, None)
        if fn is None:
            continue
        src = inspect.getsource(fn)
        assert "urn:li:organization:{org_id}" not in src, f"{method} still rebuilds the URN"


# =============================================================================
# The round trip
# =============================================================================

def test_state_cannot_be_borrowed_from_another_provider():
    src = inspect.getsource(linkedin_oauth._decode_state)
    assert 'purpose") != "linkedin_oauth"' in src


def test_every_callback_outcome_redirects_somewhere_readable():
    from fastapi.testclient import TestClient

    import main

    with TestClient(main.app, raise_server_exceptions=False) as c:
        for query in ("", "?error=user_cancelled_login", "?code=abc"):
            r = c.get(f"/api/v1/linkedin/callback{query}", follow_redirects=False)
            assert r.status_code in (302, 307), f"{query} did not redirect"
            assert "/dashboard/" in r.headers.get("location", "")


def test_the_token_is_encrypted_before_storage():
    assert "encrypt_token(access_token)" in SRC_CALLBACK


def test_the_interface_can_start_it_without_pasting_a_token():
    import pathlib

    ws = pathlib.Path(__file__).resolve().parent.parent / "frontend" / "src" / "pages" / "dashboard" / "Workspaces.jsx"
    src = ws.read_text(encoding="utf-8")
    assert "/linkedin/connect" in src
    assert "Connect LinkedIn" in src
    assert "Paste token" not in src, "the manual token field is back"
