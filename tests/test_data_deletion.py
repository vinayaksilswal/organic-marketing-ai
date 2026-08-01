"""Account deletion: Meta's callback, and GDPR erasure and export.

Run against a real database. Deletion is irreversible and touches eighteen
tables, so a mocked session would prove nothing about whether rows actually go
away or whether another tenant's rows survive.
"""

import base64
import hashlib
import hmac
import json
import uuid

import pytest
from sqlalchemy import func, select

from database import (
    Audience,
    BusinessProfile,
    Media,
    SocialConnection,
    SocialPost,
    Subscription,
    User,
)
from prompt_engine.db_models import CaptionVersion
from routers.data_deletion import _parse_signed_request, _purge_user

SECRET = "test-app-secret"


def _sign(payload: dict, secret: str = SECRET) -> str:
    """Build a signed_request the way Meta does."""
    raw = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    sig = hmac.new(secret.encode(), raw.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(sig).decode().rstrip("=") + "." + raw


async def _seed(session, user_id: str, ws_id: str, fb_user_id: str | None = None):
    session.add(User(id=user_id, email=f"{user_id}@example.com", password="hash"))
    session.add(BusinessProfile(id=ws_id, userId=user_id, name=f"WS {ws_id}"))
    session.add(Media(
        id=f"m-{ws_id}", userId=user_id, businessProfileId=ws_id,
        filename="a.jpg", mimeType="image/jpeg", url=f"https://cdn/{ws_id}.jpg",
    ))
    session.add(SocialPost(
        id=f"p-{ws_id}", userId=user_id, businessProfileId=ws_id,
        platform="BOTH", type="IMAGE", status="POSTED", caption="hi",
        mediaUrls=[f"https://cdn/{ws_id}.jpg"],
    ))
    session.add(Audience(
        id=f"a-{ws_id}", userId=user_id, businessProfileId=ws_id,
        email=f"sub-{ws_id}@example.com",
    ))
    session.add(CaptionVersion(
        id=f"c-{ws_id}", businessProfileId=ws_id, caption_text="hello",
    ))
    session.add(SocialConnection(
        id=f"s-{ws_id}", userId=user_id, businessProfileId=ws_id,
        fbAccessToken="encrypted", fbPageId="page-1", fbUserId=fb_user_id,
    ))
    session.add(Subscription(
        id=f"sub-{ws_id}", userId=user_id, planCode="starter", status="ACTIVE",
    ))
    await session.commit()


async def _count(session, model) -> int:
    return (await session.execute(select(func.count()).select_from(model))).scalar()


# ── signed request verification ──────────────────────────────────────────────

def test_valid_signed_request_is_decoded():
    payload = {"algorithm": "HMAC-SHA256", "user_id": "fb-123"}
    assert _parse_signed_request(_sign(payload), SECRET)["user_id"] == "fb-123"


def test_wrong_secret_is_rejected():
    """The endpoint deletes data and has no other authentication."""
    signed = _sign({"algorithm": "HMAC-SHA256", "user_id": "fb-123"})
    assert _parse_signed_request(signed, "attacker-secret") is None


def test_tampered_payload_is_rejected():
    signed = _sign({"algorithm": "HMAC-SHA256", "user_id": "fb-123"})
    sig, payload = signed.split(".", 1)
    forged = base64.urlsafe_b64encode(
        json.dumps({"algorithm": "HMAC-SHA256", "user_id": "fb-999"}).encode()
    ).decode().rstrip("=")
    assert _parse_signed_request(f"{sig}.{forged}", SECRET) is None


@pytest.mark.parametrize("bad", ["", "nodot", "a.b.c.d", "!!!.???", None])
def test_malformed_signed_requests_do_not_raise(bad):
    assert _parse_signed_request(bad, SECRET) is None


def test_unexpected_algorithm_is_rejected():
    """A payload claiming 'none' must not bypass the HMAC check."""
    raw = base64.urlsafe_b64encode(
        json.dumps({"algorithm": "none", "user_id": "fb-123"}).encode()
    ).decode().rstrip("=")
    sig = hmac.new(SECRET.encode(), raw.encode(), hashlib.sha256).digest()
    signed = base64.urlsafe_b64encode(sig).decode().rstrip("=") + "." + raw
    assert _parse_signed_request(signed, SECRET) is None


# ── the purge itself ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_purge_removes_every_trace_of_the_user(db_session):
    await _seed(db_session, "u1", "ws1", fb_user_id="fb-1")

    counts = await _purge_user(db_session, "u1")

    for model in (User, BusinessProfile, Media, SocialPost, Audience,
                  CaptionVersion, SocialConnection, Subscription):
        remaining = await _count(db_session, model)
        assert remaining == 0, f"{model.__name__} still has {remaining} rows"
    assert counts["User"] == 1


@pytest.mark.asyncio
async def test_purge_does_not_touch_another_tenant(db_session):
    """The failure that would matter most: deleting someone else's account."""
    await _seed(db_session, "u1", "ws1", fb_user_id="fb-1")
    await _seed(db_session, "u2", "ws2", fb_user_id="fb-2")

    await _purge_user(db_session, "u1")

    survivors = (await db_session.execute(select(User.id))).scalars().all()
    assert survivors == ["u2"]
    for model in (BusinessProfile, Media, SocialPost, Audience,
                  CaptionVersion, SocialConnection, Subscription):
        assert await _count(db_session, model) == 1, (
            f"{model.__name__} lost the other tenant's row"
        )


@pytest.mark.asyncio
async def test_purge_covers_multiple_workspaces(db_session):
    await _seed(db_session, "u1", "ws1")
    db_session.add(BusinessProfile(id="ws1b", userId="u1", name="Second"))
    db_session.add(Media(
        id="m-ws1b", userId="u1", businessProfileId="ws1b",
        filename="b.jpg", mimeType="image/jpeg", url="https://cdn/b.jpg",
    ))
    await db_session.commit()

    await _purge_user(db_session, "u1")
    assert await _count(db_session, BusinessProfile) == 0
    assert await _count(db_session, Media) == 0


@pytest.mark.asyncio
async def test_purge_of_unknown_user_is_a_no_op(db_session):
    await _seed(db_session, "u1", "ws1")
    counts = await _purge_user(db_session, "does-not-exist")
    assert counts["User"] == 0
    assert await _count(db_session, User) == 1


@pytest.mark.asyncio
async def test_stored_tokens_are_destroyed(db_session):
    """Encrypted Page tokens are the most sensitive thing held, and they are
    what Meta's deletion requirement is actually about."""
    await _seed(db_session, "u1", "ws1", fb_user_id="fb-1")
    assert await _count(db_session, SocialConnection) == 1

    await _purge_user(db_session, "u1")

    rows = (await db_session.execute(select(SocialConnection))).scalars().all()
    assert rows == []
