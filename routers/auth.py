"""
=============================================================================
Organic Marketing AI — Authentication Router
=============================================================================
Handles admin login (cookie-based JWT) and user API authentication
(Bearer token JWT) using SQLAlchemy 2.0 Async ORM.
=============================================================================
"""

from __future__ import annotations

import asyncio
import re
import secrets
from datetime import timedelta
from typing import Optional

import bcrypt
import jwt
from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from loguru import logger
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, field_validator
from sqlalchemy import select

from auth import create_access_token
from config import settings
from database import AsyncSessionLocal, User
from rate_limit import limiter

router = APIRouter(tags=["Authentication"])
templates = Jinja2Templates(directory="templates")


# =============================================================================
# Admin Login (Cookie-based — for marketing dashboard)
# =============================================================================
@router.get("/admin/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")


@router.post("/admin/login")
async def login(response: Response, username: str = Form(...), password: str = Form(...)):
    correct_username = secrets.compare_digest(
        username.encode("utf8"), settings.admin_username.encode("utf8")
    )
    correct_password = secrets.compare_digest(
        password.encode("utf8"), settings.admin_password.encode("utf8")
    )

    if not (correct_username and correct_password):
        return RedirectResponse(url="/admin/login?error=1", status_code=303)

    token = create_access_token(data={"sub": username})

    redirect = RedirectResponse(url="/admin", status_code=303)
    redirect.set_cookie(
        key="admin_session",
        value=token,
        httponly=True,
        max_age=86400,  # 1 day
        samesite="lax",
        secure=(settings.environment == "production"),
    )
    return redirect


@router.get("/admin/logout")
async def logout():
    redirect = RedirectResponse(url="/admin/login", status_code=303)
    redirect.delete_cookie("admin_session")
    return redirect


# =============================================================================
# User Authentication Dependency (Bearer token)
# =============================================================================
def verify_user(request: Request) -> str:
    """
    FastAPI dependency that extracts and validates user JWT from
    the Authorization header. Returns the user ID.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id: str = payload.get("sub")
        token_type = payload.get("type")
        if not user_id or token_type != "user":
            raise HTTPException(status_code=401, detail="Invalid user session")
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid session: {str(e)}")

def get_workspace_id(request: Request) -> Optional[str]:
    """
    Extracts the workspace ID from the X-Workspace-Id header.
    """
    return request.headers.get("X-Workspace-Id")


# Paths whose answer depends on the authenticated user and not on the
# X-Workspace-Id header. Each one already filters by user_id in its own
# handler; listing them here only stops a stale header from locking a client
# out of the calls it needs to recover.
#
# Kept as an explicit set rather than a prefix match: "/api/v1/businesses" is
# user-scoped, but "/api/v1/businesses/{id}" acts on one workspace and must
# stay guarded.
_USER_SCOPED_PATHS = {
    "/api/v1/businesses",          # list mine, and create a new one
    "/api/v1/users/me",            # who am I
    "/api/v1/billing/me",          # my plan and usage
    "/api/v1/billing/plans",
    "/api/v1/team",                # my invitations across workspaces
}


async def verify_workspace_access(
    request: Request, user_id: str = Depends(verify_user)
) -> Optional[str]:
    """Reject a request naming a workspace the caller has no claim to.

    verify_user proves who is calling. It does not prove that the workspace in
    X-Workspace-Id belongs to them -- and row-level security does not either,
    because it scopes queries to whatever workspace it is handed. Together
    those meant any signed-up account could pass another customer's workspace
    id and read their catalog, delete their media, or publish to their social
    accounts. Twenty workspace-scoped endpoints relied on nothing but the
    header being present.

    Applied at the router level rather than per endpoint, so it cannot be
    forgotten on the next one added. A request with no workspace header is
    passed through untouched: plenty of endpoints legitimately have none, and
    those that need one already reject it themselves.

    Access means: the workspace is yours, you are an accepted team member of
    it, or you are a superadmin.
    """
    # Endpoints that answer "what do I have access to", not "act on this
    # workspace". They filter by the authenticated user themselves and never
    # read the header, so enforcing it here is not security, it is a deadlock:
    #
    # The client stores the active workspace in localStorage and attaches it to
    # every request. When a second user signs in on the same browser they
    # inherit the previous user's workspace id -- so listing their own
    # workspaces was refused, which is the one call that would have corrected
    # the stale value. The dashboard 404'd on every request, permanently, and
    # the only escape was clearing site data. Creating a business had the same
    # shape from the other end: a new account has no workspace, so requiring
    # one in order to make one is circular.
    path = request.url.path.rstrip("/")
    if path in _USER_SCOPED_PATHS:
        return None

    workspace_id = request.headers.get("x-workspace-id") or request.headers.get(
        "X-Workspace-Id"
    )
    if not workspace_id:
        return None

    from sqlalchemy import select

    from database import AsyncSessionLocal, BusinessProfile, TeamMember, User

    async with AsyncSessionLocal() as session:
        profile = await session.get(BusinessProfile, workspace_id)
        if profile is None:
            # Deliberately the same answer as "not yours": distinguishing the
            # two lets an attacker enumerate which workspace ids exist.
            raise HTTPException(status_code=404, detail="Workspace not found")

        if profile.userId == user_id:
            return workspace_id

        member = (await session.execute(
            select(TeamMember).where(
                TeamMember.businessProfileId == workspace_id,
                TeamMember.userId == user_id,
                TeamMember.status == "ACCEPTED",
            )
        )).scalars().first()
        if member is not None:
            return workspace_id

        user = await session.get(User, user_id)
        if user is not None and getattr(user, "isSuperAdmin", False):
            return workspace_id

    logger.warning(
        f"Blocked cross-tenant access: user {user_id} requested workspace "
        f"{workspace_id} owned by {profile.userId}"
    )
    raise HTTPException(status_code=404, detail="Workspace not found")

# =============================================================================
# User Registration & Login Models
# =============================================================================
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


class UserRegister(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not EMAIL_REGEX.match(v):
            raise ValueError("Please enter a valid email address")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return v


class UserLogin(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        return v.strip().lower()


# =============================================================================
# User Registration & Login API Endpoints
# =============================================================================
@router.post("/api/v1/auth/register")
async def api_register(data: UserRegister, request: Request):
    """Register a new user account using SQLAlchemy 2.0 Async Session."""
    try:
        async with AsyncSessionLocal() as session:
            stmt = select(User).where(User.email == data.email)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                raise HTTPException(
                    status_code=409, detail="An account with this email already exists"
                )

            hashed = bcrypt.hashpw(data.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            user = User(email=data.email, password=hashed)
            session.add(user)
            await session.commit()
            await session.refresh(user)

            token = create_access_token(data={"sub": user.id, "type": "user"})
            return {
                "success": True,
                "token": token,
                "user": {"id": user.id, "email": user.email},
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database error: {str(e)}")


@router.post("/api/v1/auth/login")
async def api_login(data: UserLogin, request: Request):
    """Log in an existing user using SQLAlchemy 2.0 Async Session."""
    try:
        async with AsyncSessionLocal() as session:
            stmt = select(User).where(User.email == data.email)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if not user or not bcrypt.checkpw(data.password.encode("utf-8"), user.password.encode("utf-8")):
                raise HTTPException(status_code=401, detail="Invalid email or password")

            token = create_access_token(data={"sub": user.id, "type": "user"})
            return {
                "success": True,
                "token": token,
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "isSuperAdmin": getattr(user, "isSuperAdmin", False),
                },
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database error: {str(e)}")


# =============================================================================
# Password Reset
# =============================================================================
class ForgotPasswordRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        return v.strip().lower()


class ResetPasswordRequest(BaseModel):
    token: str
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return v


def password_fingerprint(password_hash: str) -> str:
    """A short digest of the stored password hash.

    Carried inside the reset token and re-checked when the token is redeemed.
    Because a bcrypt hash changes every time the password is set, this makes a
    reset link single-use and kills every other outstanding link at the same
    moment: the fingerprint no longer matches what is in the database.

    Without it the token was a bearer credential valid for a full hour and
    replayable for the whole of it. A reset email sitting in a mailbox someone
    else can read could be used again after the owner had already recovered
    their account -- which is the exact scenario a password reset exists to
    close.
    """
    import hashlib

    return hashlib.sha256((password_hash or "").encode("utf-8")).hexdigest()[:16]


async def _send_reset_email(to_email: str, reset_link: str) -> bool:
    """Send the reset email. Returns whether it actually went out.

    The Resend SDK is synchronous. Called directly from an async endpoint it
    blocks the event loop for the duration of an outbound HTTPS request, and
    this service runs a single uvicorn worker -- so one slow send stalls every
    other request in flight. Same class of fault as the ffmpeg call that
    froze the server, and the same fix.
    """
    from loguru import logger

    if not settings.resend_api_key:
        # Previously this fell through and the endpoint still answered "a reset
        # link has been sent". The user waited for an email that was never
        # attempted, with nothing in the logs to say so.
        logger.error(
            "Password reset requested but RESEND_API_KEY is not configured. "
            "No email was sent, and the caller was told one was. Set the key "
            "in the environment or password recovery does not exist."
        )
        return False

    def _send() -> None:
        import resend

        resend.api_key = settings.resend_api_key
        resend.Emails.send({
            "from": f"Organiflo <noreply@{settings.resend_from_domain or 'organicai.pro'}>",
            "to": [to_email],
            "subject": "Reset your Organiflo password",
            "html": (
                f"<p>You requested a password reset.</p>"
                f'<p><a href="{reset_link}">Click here to reset your password</a></p>'
                f"<p>This link expires in 1 hour and can only be used once. "
                f"If you didn't request this, you can ignore this email.</p>"
            ),
        })

    try:
        await asyncio.to_thread(_send)
        logger.info(f"Password reset email sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send reset email to {to_email}: {e}")
        return False


@router.post("/api/v1/auth/forgot-password")
@limiter.limit("5/hour")
async def forgot_password(request: Request, data: ForgotPasswordRequest):
    """Send a password reset email with a single-use, time-limited token.

    Rate limited hard. The global default of 200/minute is right for ordinary
    API traffic and badly wrong here: this endpoint sends mail to an address
    the caller supplies, so an unthrottled one is a way to flood somebody
    else's inbox and burn the sending quota at the same time.
    """
    async with AsyncSessionLocal() as session:
        stmt = select(User).where(User.email == data.email)
        user = (await session.execute(stmt)).scalar_one_or_none()

    # The same answer either way, so the endpoint cannot be used to find out
    # which email addresses have accounts.
    neutral = {
        "success": True,
        "message": "If that email exists, a reset link has been sent.",
    }
    if not user:
        return neutral

    reset_token = create_access_token(
        data={
            "sub": user.id,
            "type": "password_reset",
            "pw": password_fingerprint(user.password),
        },
        expires_delta=timedelta(hours=1),
    )

    frontend_url = settings.allowed_origins[0] if settings.allowed_origins else "https://organic-marketing-ai.vercel.app"
    reset_link = f"{frontend_url}/reset-password?token={reset_token}"

    await _send_reset_email(data.email, reset_link)
    return neutral


@router.post("/api/v1/auth/reset-password")
async def reset_password(data: ResetPasswordRequest):
    """Verify the reset token and update the user's password."""
    try:
        payload = jwt.decode(data.token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = payload.get("sub")
        token_type = payload.get("type")
        if not user_id or token_type != "password_reset":
            raise HTTPException(status_code=400, detail="Invalid reset token")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=400, detail="Reset link has expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=400, detail="Invalid reset token")

    async with AsyncSessionLocal() as session:
        stmt = select(User).where(User.id == user_id)
        user = (await session.execute(stmt)).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # The token carries a digest of the password hash it was issued
        # against. If the password has changed since -- because this link was
        # already used, or a newer link was -- the digest no longer matches and
        # the link is spent. This is what makes a reset single-use.
        issued_for = payload.get("pw")
        if issued_for and issued_for != password_fingerprint(user.password):
            raise HTTPException(
                status_code=400,
                detail="This reset link has already been used. Request a new one.",
            )

        user.password = bcrypt.hashpw(data.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        await session.commit()

        from loguru import logger
        logger.info(f"Password reset completed for user {user.id}")

    return {"success": True, "message": "Password has been reset successfully"}


# =============================================================================
# Niche / Industry Options API
# =============================================================================
@router.get("/api/v1/niches")
async def get_niche_options():
    """Return the predefined list of business niches for onboarding."""
    from services.seed_service import NICHE_OPTIONS
    return {"success": True, "niches": NICHE_OPTIONS}

