"""Connecting YouTube, and respecting the quota that makes it unusual.

Every other platform here is limited by what a customer's audience will
tolerate. YouTube is limited by arithmetic: an upload costs 1,600 units
against a default 10,000 per day, and that budget belongs to the application
rather than to a channel. Six uploads a day, shared by every customer.

That is small enough to be a design constraint rather than a footnote. One
workspace publishing every four hours would exhaust it before lunch and take
everyone else's uploads with it.
"""

import inspect

import pytest

from routers import youtube_oauth as yt
from services import youtube_service as ytsvc


SRC_CONNECT = inspect.getsource(yt.youtube_connect)
SRC_CALLBACK = inspect.getsource(yt.youtube_callback)


# =============================================================================
# Reachable and guarded
# =============================================================================

def test_the_endpoints_are_registered():
    from fastapi.testclient import TestClient

    import main

    with TestClient(main.app, raise_server_exceptions=False) as c:
        assert c.get("/api/v1/youtube/connect").status_code == 401
        assert c.post("/api/v1/youtube/disconnect").status_code == 401


def test_a_workspace_that_is_not_yours_is_refused():
    assert "bp.userId != user_id" in SRC_CONNECT
    assert "bp.userId != user_id" in inspect.getsource(yt.youtube_disconnect)


def test_missing_credentials_give_a_503_that_names_them():
    assert "503" in SRC_CONNECT
    assert "YOUTUBE_CLIENT_ID" in SRC_CONNECT


def test_state_cannot_be_borrowed_from_another_provider():
    src = inspect.getsource(yt._decode_state)
    assert 'purpose") != "youtube_oauth"' in src


def test_every_callback_outcome_redirects_somewhere_readable():
    from fastapi.testclient import TestClient

    import main

    with TestClient(main.app, raise_server_exceptions=False) as c:
        for query in ("", "?error=access_denied", "?code=abc"):
            r = c.get(f"/api/v1/youtube/callback{query}", follow_redirects=False)
            assert r.status_code in (302, 307), f"{query} did not redirect"
            assert "/dashboard/" in r.headers.get("location", "")


# =============================================================================
# The refresh token, which is the whole connection
# =============================================================================

def test_the_authorisation_asks_for_a_refresh_token():
    """Google returns one only with access_type=offline AND prompt=consent.
    Without both, a reconnecting customer gets an access token, no refresh
    token, and a connection that works for one hour and then stops."""
    assert '"access_type": "offline"' in SRC_CONNECT
    assert '"prompt": "consent"' in SRC_CONNECT


def test_a_connection_without_a_refresh_token_is_refused_not_stored():
    """Storing it would produce a connection that publishes once and then
    fails silently every cycle afterwards."""
    assert "refresh_token" in SRC_CALLBACK
    assert "did not return a long-lived token" in SRC_CALLBACK


def test_the_refresh_token_is_encrypted_before_storage():
    assert "encrypt_token(refresh_token)" in SRC_CALLBACK


def test_only_the_refresh_token_is_kept():
    """The access token expires in an hour and the scheduler runs on a
    multi-hour interval, so a stored one is reliably stale."""
    assert "youtubeAccessToken" not in SRC_CALLBACK


def test_the_channel_is_read_rather_than_assumed():
    """A Google account with no channel cannot be published to, and saying so
    at connect time is better than a failed upload a day later."""
    assert "mine" in SRC_CALLBACK
    assert "has no YouTube channel" in SRC_CALLBACK


def test_the_scopes_are_the_two_that_are_needed():
    assert "youtube.upload" in yt.SCOPES
    assert "youtube.readonly" in yt.SCOPES
    # Nothing that could edit or delete existing videos.
    assert "youtube.force-ssl" not in yt.SCOPES
    assert "youtubepartner" not in yt.SCOPES


# =============================================================================
# The quota
# =============================================================================

def test_there_is_a_daily_ceiling_below_what_google_allows():
    """10,000 units at 1,600 an upload is six. The ceiling has to sit under
    that, because a failed upload can still cost quota."""
    assert 1 <= ytsvc.DAILY_UPLOAD_CEILING <= 6


def test_the_ceiling_is_configurable_without_a_deploy():
    src = inspect.getsource(ytsvc)
    assert "YOUTUBE_DAILY_UPLOAD_CEILING" in src


def test_uploads_are_refused_once_the_budget_is_spent(monkeypatch):
    """Not merely reported — refused. Attempting anyway spends quota that
    belongs to every other customer on the platform."""
    monkeypatch.setattr(ytsvc, "_uploads_today", {"day": ytsvc._today(), "count": 999})
    assert ytsvc.quota_remaining() == 0


def test_a_fresh_day_restores_the_budget(monkeypatch):
    monkeypatch.setattr(ytsvc, "_uploads_today", {"day": "1999-01-01", "count": 999})
    assert ytsvc.quota_remaining() == ytsvc.DAILY_UPLOAD_CEILING


@pytest.mark.asyncio
async def test_an_exhausted_quota_returns_none_without_calling_google(monkeypatch):
    called = {"n": 0}

    async def should_not_run(*a, **kw):
        called["n"] += 1
        return "token"

    monkeypatch.setattr(ytsvc, "_uploads_today", {"day": ytsvc._today(), "count": 999})
    monkeypatch.setattr(ytsvc, "_credentials", should_not_run)

    out = await ytsvc.upload_video("ws", "https://x/v.mp4", "Title")
    assert out is None
    assert called["n"] == 0, "it went to Google with no quota left"


@pytest.mark.asyncio
async def test_an_unconnected_workspace_returns_none_rather_than_raising(monkeypatch):
    """A YouTube failure must not take down the Meta post sharing the same
    automation run."""
    async def none(*a, **kw):
        return None

    monkeypatch.setattr(ytsvc, "_uploads_today", {"day": None, "count": 0})
    monkeypatch.setattr(ytsvc, "_credentials", none)
    assert await ytsvc.upload_video("ws", "https://x/v.mp4", "Title") is None


def test_the_title_is_cut_to_what_youtube_accepts():
    """Titles are capped at 100 characters and angle brackets are rejected."""
    src = inspect.getsource(ytsvc.upload_video)
    assert "[:100]" in src
    assert '"<"' in src


# =============================================================================
# The interface
# =============================================================================

def test_the_panel_can_start_it():
    import pathlib

    ws = (
        pathlib.Path(__file__).resolve().parent.parent
        / "frontend" / "src" / "pages" / "dashboard" / "Workspaces.jsx"
    )
    src = ws.read_text(encoding="utf-8")
    assert "/youtube/connect" in src
    assert "Connect YouTube" in src


def test_the_panel_says_uploads_are_limited():
    """The customer should learn the constraint before connecting, not from a
    post that never appeared."""
    import pathlib

    ws = (
        pathlib.Path(__file__).resolve().parent.parent
        / "frontend" / "src" / "pages" / "dashboard" / "Workspaces.jsx"
    )
    src = ws.read_text(encoding="utf-8")
    assert "limited number of uploads per day" in src
