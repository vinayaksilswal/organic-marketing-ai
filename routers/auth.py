"""
=============================================================================
Organic Marketing AI — Authentication Router
=============================================================================
Handles admin login (cookie-based JWT) and user API authentication
(Bearer token JWT) using SQLAlchemy 2.0 Async ORM.
=============================================================================
"""

from __future__ import annotations

import re
import secrets
from typing import Optional

import bcrypt
import jwt
from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, field_validator
from sqlalchemy import select

from auth import create_access_token
from config import settings
from database import AsyncSessionLocal, User

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
# Niche / Industry Options API
# =============================================================================
@router.get("/api/v1/niches")
async def get_niche_options():
    """Return the predefined list of business niches for onboarding."""
    from services.seed_service import NICHE_OPTIONS
    return {"success": True, "niches": NICHE_OPTIONS}

