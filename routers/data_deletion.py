"""Account deletion and data export.

Two obligations, one implementation:

  Meta App Review requires a Data Deletion Callback. When a user removes the
  app from their Facebook account, Meta POSTs a signed_request here and expects
  a status URL plus a confirmation code back. Without this endpoint the app is
  rejected, which is what blocked review.

  GDPR Article 17 (erasure) and Article 20 (portability) require the same
  capability for the user directly, on request, without going through Meta.

Deletion is genuinely destructive and irreversible, so it is deliberately
awkward: the authenticated route requires the account's own email typed back as
confirmation. The Meta callback cannot ask for that, so it is authenticated by
the signed request's HMAC instead — anyone can POST to it, but only Meta can
sign it.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import delete, select

from config import settings
from database import (
    AsyncSessionLocal,
    Audience,
    BusinessProfile,
    EmailCampaign,
    EmailConfig,
    MarketingLog,
    MarketingState,
    Media,
    Product,
    SocialCampaign,
    SocialConnection,
    SocialPost,
    Subscription,
    TeamMember,
    UsageCounter,
    User,
    VideoApiConfig,
)
# Safe to import here: routers are not on the Alembic import path, which is
# why database.py must not do this (see the note at the foot of that module).
from prompt_engine.db_models import CaptionVersion, PromptVersion
from routers.auth import verify_user

router = APIRouter(tags=["Data Deletion"])


# Ordered child-first so a foreign key never blocks a parent delete. Each entry
# is (model, column) — everything scoped by workspace is removed via the
# workspace ids the user owns, everything scoped by user directly by user id.
_WORKSPACE_SCOPED = [
    (CaptionVersion, "businessProfileId"),
    (PromptVersion, "businessProfileId"),
    (MarketingLog, "businessProfileId"),
    (MarketingState, "businessProfileId"),
    (SocialPost, "businessProfileId"),
    (SocialCampaign, "businessProfileId"),
    (EmailCampaign, "businessProfileId"),
    (EmailConfig, "businessProfileId"),
    (SocialConnection, "businessProfileId"),
    (VideoApiConfig, "businessProfileId"),
    (Media, "businessProfileId"),
    (Product, "businessProfileId"),
    (Audience, "businessProfileId"),
    (TeamMember, "businessProfileId"),
]

_USER_SCOPED = [
    (UsageCounter, "userId"),
    (Subscription, "userId"),
    (TeamMember, "userId"),
]


async def _purge_user(session, user_id: str) -> Dict[str, int]:
    """Delete everything belonging to this user. Returns per-table counts.

    Prompt-engine tables are deleted explicitly rather than left to the
    BusinessProfile cascade: that cascade is ORM-level, and these are bulk
    DELETE statements which bypass it entirely.
    """
    counts: Dict[str, int] = {}

    workspace_ids = (
        await session.execute(
            select(BusinessProfile.id).where(BusinessProfile.userId == user_id)
        )
    ).scalars().all()

    if workspace_ids:
        for model, column in _WORKSPACE_SCOPED:
            result = await session.execute(
                delete(model).where(getattr(model, column).in_(workspace_ids))
            )
            if result.rowcount:
                counts[model.__name__] = counts.get(model.__name__, 0) + result.rowcount

    for model, column in _USER_SCOPED:
        result = await session.execute(
            delete(model).where(getattr(model, column) == user_id)
        )
        if result.rowcount:
            counts[model.__name__] = counts.get(model.__name__, 0) + result.rowcount

    # Workspaces last among owned rows, then the account itself.
    result = await session.execute(
        delete(BusinessProfile).where(BusinessProfile.userId == user_id)
    )
    if result.rowcount:
        counts["BusinessProfile"] = result.rowcount

    result = await session.execute(delete(User).where(User.id == user_id))
    counts["User"] = result.rowcount

    await session.commit()
    return counts


# ─────────────────────────────────────────────────────────────────────────────
# Meta Data Deletion Callback
# ─────────────────────────────────────────────────────────────────────────────

def _parse_signed_request(signed_request: str, app_secret: str) -> Optional[dict]:
    """Verify and decode Meta's signed_request.

    Format is `<base64url signature>.<base64url json payload>`, signed with
    HMAC-SHA256 over the raw payload segment using the app secret. A failed
    signature means the caller is not Meta, so the request is rejected rather
    than trusted — this endpoint deletes data and is unauthenticated otherwise.
    """
    try:
        encoded_sig, payload = signed_request.split(".", 1)
    except (ValueError, AttributeError):
        return None

    def _b64(value: str) -> bytes:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))

    try:
        signature = _b64(encoded_sig)
        data = json.loads(_b64(payload))
    except Exception:
        return None

    if str(data.get("algorithm", "")).upper() != "HMAC-SHA256":
        return None

    expected = hmac.new(
        app_secret.encode(), payload.encode(), hashlib.sha256
    ).digest()
    if not hmac.compare_digest(signature, expected):
        return None
    return data


@router.post("/api/v1/data-deletion/facebook")
async def facebook_data_deletion(request: Request):
    """Meta's Data Deletion Callback.

    Meta sends `signed_request` as form data and expects JSON back containing a
    URL the user can visit to check status, plus a confirmation code.
    """
    app_secret = getattr(settings, "fb_app_secret", None)
    if not app_secret:
        logger.error("Data deletion callback hit but no Meta app secret configured")
        raise HTTPException(
            status_code=503,
            detail="Data deletion is not configured. Contact support to erase your data.",
        )

    form = await request.form()
    signed_request = form.get("signed_request")
    if not signed_request:
        raise HTTPException(status_code=400, detail="signed_request is required")

    data = _parse_signed_request(str(signed_request), app_secret)
    if not data:
        # Invalid signature means this did not come from Meta.
        logger.warning("Rejected data-deletion callback with an invalid signature")
        raise HTTPException(status_code=400, detail="Invalid signed_request")

    fb_user_id = str(data.get("user_id") or "")
    confirmation_code = secrets.token_hex(8)

    deleted: Dict[str, int] = {}
    async with AsyncSessionLocal() as session:
        # The Facebook user id is stored on the social connection, which is how
        # a Meta-initiated deletion maps back to a local account.
        conn_stmt = select(SocialConnection).where(
            SocialConnection.fbUserId == fb_user_id
        )
        connections = (await session.execute(conn_stmt)).scalars().all()
        user_ids = {c.userId for c in connections if c.userId}

        for user_id in user_ids:
            try:
                counts = await _purge_user(session, user_id)
                for k, v in counts.items():
                    deleted[k] = deleted.get(k, 0) + v
            except Exception as e:
                logger.error(f"Data deletion failed for user {user_id}: {e}")
                raise HTTPException(
                    status_code=500, detail="Deletion failed, please contact support"
                )

    logger.info(
        f"Meta data deletion for fb_user={fb_user_id}: "
        f"{len(user_ids)} account(s), rows={deleted}"
    )

    base = str(
        getattr(settings, "backend_url", None) or request.base_url
    ).rstrip("/")
    return {
        "url": f"{base}/data-deletion-status/{confirmation_code}",
        "confirmation_code": confirmation_code,
    }


@router.get("/data-deletion-status/{confirmation_code}", response_class=HTMLResponse)
async def data_deletion_status(confirmation_code: str):
    """The page Meta links the user to after a deletion request."""
    safe_code = "".join(c for c in confirmation_code if c.isalnum())[:32]
    return HTMLResponse(
        f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Data deletion &mdash; OrganicAI</title>
<style>
 body{{font:16px/1.6 system-ui,-apple-system,Segoe UI,sans-serif;margin:0;
      background:#0b0d10;color:#e8eaed;display:grid;place-items:center;min-height:100vh}}
 main{{max-width:34rem;padding:2rem}}
 code{{background:#1a1d21;padding:.15em .45em;border-radius:4px}}
 a{{color:#7aa2ff}}
</style></head><body><main>
<h1>Your data has been deleted</h1>
<p>The request completed. Your account, business profiles, connected social
accounts, stored access tokens, media, posts and scheduling history have been
permanently removed from OrganicAI.</p>
<p>Confirmation code: <code>{safe_code}</code></p>
<p>Deletion is immediate and cannot be undone. If you believe data remains,
email <a href="mailto:vinayaksilswal@gmail.com">vinayaksilswal@gmail.com</a>
quoting the code above.</p>
</main></body></html>"""
    )


@router.get("/data-deletion", response_class=HTMLResponse)
async def data_deletion_instructions():
    """Data Deletion Instructions URL, the other form Meta accepts."""
    return HTMLResponse(
        """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>How to delete your data &mdash; OrganicAI</title>
<style>
 body{font:16px/1.6 system-ui,-apple-system,Segoe UI,sans-serif;margin:0;
      background:#0b0d10;color:#e8eaed;display:grid;place-items:center;min-height:100vh}
 main{max-width:38rem;padding:2rem}
 li{margin:.4rem 0}
 a{color:#7aa2ff}
</style></head><body><main>
<h1>Deleting your OrganicAI data</h1>
<p>You can erase your account and everything in it at any time. There are two
ways, and both delete the same thing.</p>
<h2>From OrganicAI</h2>
<ol>
 <li>Sign in and open <strong>Settings</strong>.</li>
 <li>Choose <strong>Delete account</strong>.</li>
 <li>Type your email address to confirm.</li>
</ol>
<h2>From Facebook</h2>
<ol>
 <li>Open <strong>Settings &amp; privacy &rarr; Settings</strong> on Facebook.</li>
 <li>Go to <strong>Apps and Websites</strong>.</li>
 <li>Remove <strong>OrganicAI</strong>. Facebook notifies us and we delete your
     data automatically.</li>
</ol>
<h2>What gets deleted</h2>
<p>Your account and login, every business profile, all connected Facebook and
Instagram accounts including stored access tokens, uploaded and generated
media, captions and prompts, scheduled and published post history, email
lists and configuration, team memberships, and billing records.</p>
<p>Deletion is permanent and takes effect immediately. Posts already published
to Facebook or Instagram live on those platforms and must be deleted there.</p>
<p>Questions: <a href="mailto:vinayaksilswal@gmail.com">vinayaksilswal@gmail.com</a></p>
</main></body></html>"""
    )


# ─────────────────────────────────────────────────────────────────────────────
# GDPR: self-serve erasure and export
# ─────────────────────────────────────────────────────────────────────────────

class DeleteAccountRequest(BaseModel):
    confirm_email: str


@router.delete("/api/v1/account")
async def delete_own_account(
    body: DeleteAccountRequest, user_id: str = Depends(verify_user)
):
    """GDPR Article 17. Irreversible, so it requires the email typed back."""
    async with AsyncSessionLocal() as session:
        user = await session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Account not found")

        if body.confirm_email.strip().lower() != (user.email or "").lower():
            raise HTTPException(
                status_code=400,
                detail="Confirmation email does not match this account.",
            )

        email = user.email
        counts = await _purge_user(session, user_id)

    logger.info(f"Account deleted on user request: {email} rows={counts}")
    return {
        "success": True,
        "message": "Your account and all associated data have been permanently deleted.",
        "deleted": counts,
    }


@router.get("/api/v1/account/export")
async def export_own_data(user_id: str = Depends(verify_user)):
    """GDPR Article 20. Everything held about the user, as JSON.

    Secrets are deliberately excluded: the password hash and the encrypted
    social tokens are not the user's data to take with them, and exporting
    them would turn a portability request into a credential leak.
    """
    def _rows(objs: List[Any], drop: tuple = ()) -> List[dict]:
        out = []
        for o in objs:
            row = {}
            for c in o.__table__.columns:
                if c.name in drop:
                    continue
                v = getattr(o, c.name, None)
                row[c.name] = v.isoformat() if isinstance(v, datetime) else v
            out.append(row)
        return out

    async with AsyncSessionLocal() as session:
        user = await session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Account not found")

        workspaces = (
            await session.execute(
                select(BusinessProfile).where(BusinessProfile.userId == user_id)
            )
        ).scalars().all()
        ws_ids = [w.id for w in workspaces]

        async def fetch(model, column="businessProfileId"):
            if not ws_ids:
                return []
            return (
                await session.execute(
                    select(model).where(getattr(model, column).in_(ws_ids))
                )
            ).scalars().all()

        export = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "account": _rows([user], drop=("password",))[0],
            "business_profiles": _rows(workspaces),
            "media": _rows(await fetch(Media)),
            "posts": _rows(await fetch(SocialPost)),
            "campaigns": _rows(await fetch(SocialCampaign)),
            "products": _rows(await fetch(Product)),
            "audiences": _rows(await fetch(Audience)),
            "email_campaigns": _rows(await fetch(EmailCampaign)),
            "marketing_log": _rows(await fetch(MarketingLog)),
            # Tokens are encrypted at rest and are credentials, not user data.
            "social_connections": _rows(
                await fetch(SocialConnection),
                drop=(
                    "fbAccessToken",
                    "twitterAccessToken",
                    "twitterAccessSecret",
                    "linkedinAccessToken",
                ),
            ),
            "subscriptions": _rows(
                (
                    await session.execute(
                        select(Subscription).where(Subscription.userId == user_id)
                    )
                ).scalars().all()
            ),
        }

    return export
