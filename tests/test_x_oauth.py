"""Connecting X, so the publishing code that already existed can run.

services/twitter_service.py could post from the day it was written, and the
worker calls it on every publish. It has never posted once, because nothing
could put a token in the database: no connect flow, no button, no way for a
customer to grant access. The capability existed and did nothing — the same
shape as the keyframes that were generated and dropped, and the insights that
were read and discarded.

The flow is OAuth 1.0a rather than 2.0, and that is not a preference.
tweepy.Client is constructed in twitter_service with consumer key, consumer
secret, access token and access token secret, which is 1.0a user context.
Issuing 2.0 bearer tokens here would mean rewriting the half that already
works.
"""

import inspect

import pytest

from routers import x_oauth


SRC_CONNECT = inspect.getsource(x_oauth.x_connect)
SRC_CALLBACK = inspect.getsource(x_oauth.x_callback)


# =============================================================================
# It is reachable, and it is guarded
# =============================================================================

def test_the_endpoints_are_registered():
    from fastapi.testclient import TestClient

    import main

    with TestClient(main.app, raise_server_exceptions=False) as c:
        assert c.get("/api/v1/x/connect").status_code == 401
        assert c.post("/api/v1/x/disconnect").status_code == 401


def test_connect_refuses_a_workspace_that_is_not_yours():
    """workspace_id arrives as a query parameter, outside any header guard."""
    assert "bp.userId != user_id" in SRC_CONNECT


def test_disconnect_refuses_a_workspace_that_is_not_yours():
    assert "bp.userId != user_id" in inspect.getsource(x_oauth.x_disconnect)


def test_a_missing_app_key_is_a_clear_503_not_a_crash():
    assert "_configured()" in SRC_CONNECT
    assert "503" in SRC_CONNECT
    assert "TWITTER_API_KEY" in SRC_CONNECT


# =============================================================================
# The callback is looked at by a person in a browser
# =============================================================================

def test_every_callback_outcome_redirects_somewhere_readable():
    """A person is looking at this in a tab. An error rendered as raw JSON is a
    dead end they cannot act on."""
    from fastapi.testclient import TestClient

    import main

    with TestClient(main.app, raise_server_exceptions=False) as c:
        for query in ("", "?denied=1", "?oauth_token=x"):
            r = c.get(f"/api/v1/x/callback{query}", follow_redirects=False)
            assert r.status_code in (302, 307), f"{query} did not redirect"
            assert "/dashboard/" in r.headers.get("location", "")


def test_a_cancelled_connection_says_so_rather_than_erroring():
    from fastapi.testclient import TestClient

    import main

    with TestClient(main.app, raise_server_exceptions=False) as c:
        r = c.get("/api/v1/x/callback?denied=1", follow_redirects=False)
    assert "cancelled" in r.headers["location"]


# =============================================================================
# The handshake
# =============================================================================

def test_state_cannot_be_borrowed_from_another_provider():
    """A state minted for Meta must not be accepted here."""
    src = inspect.getsource(x_oauth._decode_state)
    assert 'purpose") != "x_oauth"' in src


def test_a_used_request_token_cannot_be_replayed():
    """pop, not get: the pending entry is consumed by the first callback."""
    assert "_PENDING.pop(" in SRC_CALLBACK


def test_tokens_are_encrypted_before_they_are_stored():
    assert "encrypt_token(access_token)" in SRC_CALLBACK
    assert "encrypt_token(access_secret)" in SRC_CALLBACK


def test_the_blocking_handshake_runs_off_the_event_loop():
    """tweepy's OAuth calls are synchronous network I/O. On the loop they stall
    every other request on a single-worker deployment."""
    assert "asyncio.to_thread" in SRC_CONNECT
    assert "asyncio.to_thread" in SRC_CALLBACK


def test_the_columns_it_writes_are_the_ones_publishing_reads():
    """The whole point is that the existing posting code starts working."""
    from services.twitter_service import TwitterService

    reader = inspect.getsource(TwitterService._get_client)
    assert "twitterAccessToken" in reader and "twitterAccessToken" in SRC_CALLBACK
    assert "twitterAccessSecret" in reader and "twitterAccessSecret" in SRC_CALLBACK


def test_the_interface_can_actually_start_it():
    """A flow with no button is the bug this is fixing."""
    import pathlib

    ws = pathlib.Path(__file__).resolve().parent.parent / "frontend" / "src" / "pages" / "dashboard" / "Workspaces.jsx"
    src = ws.read_text(encoding="utf-8")
    assert "/x/connect" in src
    assert "Connect X" in src
