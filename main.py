"""
=============================================================================
Organic Marketing AI — FastAPI Application Entry Point
=============================================================================
This is the control center for the entire autonomous marketing platform.
It hosts the AI chatbot, marketing automation scheduler, and all
API endpoints for social media, email, and Stripe integrations.

Uses SQLAlchemy 2.0 Async ORM + asyncpg for direct, pure-Python database
access with zero binary dependencies.
=============================================================================
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from loguru import logger
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import select, func, text

from config import settings
from database import init_db, close_db, AsyncSessionLocal, User, Audience, SocialPost, SocialCampaign, BusinessProfile, MarketingLog
from exceptions import OrganicMarketingException

# =============================================================================
# Loguru Configuration
# =============================================================================
logger.remove()
if settings.environment == "production":
    logger.add(
        sys.stdout,
        format="{time} | {level} | {name}:{function}:{line} - {message}",
        serialize=True,
    )
else:
    logger.add(
        sys.stdout,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
    )


# =============================================================================
# Application Lifespan — Non-Blocking Async Context Manager
# =============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Manages application startup non-blockingly so Render web server boots in < 1 second.
    Database initialization, schema migration, seeding, and scheduler start happen
    in a background task so the HTTP server is available immediately.
    """
    from services.scheduler import create_scheduler, shutdown_scheduler
    from services.seed_service import run_all_seeds

    logger.info("=" * 60)
    logger.info("Organic Marketing AI Platform — Starting Up")
    logger.info(f"Environment: {settings.environment}")
    logger.info("=" * 60)

    async def bg_bootstrap():
        try:
            # 1. Initialize database engine and create tables
            engine = await init_db()
            app.state.db_engine = engine
            app.state.db_ready = True
            logger.info("SQLAlchemy ORM connected to PostgreSQL")

            # 2. Minimal schema migrations for new columns (idempotent)
            try:
                async with engine.begin() as conn:
                    migrations = [
                        'ALTER TABLE "User" ADD COLUMN IF NOT EXISTS "isSuperAdmin" BOOLEAN NOT NULL DEFAULT FALSE;',
                        'ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "niche" VARCHAR;',
                        'ALTER TABLE "SocialConnection" ADD COLUMN IF NOT EXISTS "twitterAccessToken" TEXT;',
                        'ALTER TABLE "SocialConnection" ADD COLUMN IF NOT EXISTS "twitterAccessSecret" TEXT;',
                        'ALTER TABLE "SocialConnection" ADD COLUMN IF NOT EXISTS "linkedinAccessToken" TEXT;',
                    ]
                    for q in migrations:
                        await conn.execute(text(q))
                logger.info("Schema migrations applied successfully")
            except Exception as e:
                logger.warning(f"Schema migration warning (may be first run): {e}")

            # 3. Run all database seeds (system user, superadmin, etc.)
            await run_all_seeds()

            # 4. Start the APScheduler for marketing automation
            scheduler = create_scheduler()
            scheduler.start()
            app.state.scheduler = scheduler
            logger.info("APScheduler started (marketing automation loop active)")

        except Exception as e:
            logger.error(f"Background bootstrap error: {e}")
            app.state.db_ready = False
            app.state.db_error = str(e)

    asyncio.create_task(bg_bootstrap())

    logger.info("Organic Marketing AI fast startup complete — listening on port")
    yield

    # Shutdown
    logger.info("Shutting down Organic Marketing AI...")
    if getattr(app.state, "scheduler", None):
        shutdown_scheduler(app.state.scheduler)
    await close_db()


# =============================================================================
# FastAPI Application Instance
# =============================================================================
app = FastAPI(
    title="Organic Marketing AI",
    description="AI-Powered Autonomous Organic Marketing Platform",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

Instrumentator().instrument(app).expose(app)


# =============================================================================
# Middleware Stack
# =============================================================================
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "https://organic-marketing-ai.vercel.app",
        "https://organicai.pro",
        "https://www.organicai.pro",
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request ID Middleware for tracing
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# =============================================================================
# Global Exception Handlers
# =============================================================================
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(
    request: Request, exc: HTTPException
) -> JSONResponse | RedirectResponse:
    if (
        exc.status_code == 401
        and (request.url.path.startswith("/admin") or request.url.path.startswith("/marketing"))
        and not request.url.path.startswith("/admin/login")
    ):
        return RedirectResponse(url="/admin/login", status_code=303)

    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "message": exc.detail},
    )


@app.exception_handler(Exception)
async def global_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    error_id = str(uuid.uuid4())
    logger.exception(f"Unhandled Exception on {request.method} {request.url.path} (Error ID: {error_id})")
    
    if settings.environment == "production":
        detail = "An internal server error occurred."
    else:
        detail = str(exc)
    
    response = JSONResponse(
        status_code=500,
        content={"success": False, "message": detail, "error_id": error_id},
    )
    
    # Ensure CORS headers are present even on 500 errors so the frontend can read the error message
    origin = request.headers.get("origin")
    if origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        
    return response


@app.exception_handler(OrganicMarketingException)
async def organic_marketing_exception_handler(
    request: Request, exc: OrganicMarketingException
) -> JSONResponse:
    error_id = str(uuid.uuid4())
    logger.error(f"Domain Exception [{exc.error_code}] on {request.method} {request.url.path} (Error ID: {error_id}): {exc.message}")
    
    response = JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "message": exc.message, "error_code": exc.error_code, "error_id": error_id},
    )
    
    origin = request.headers.get("origin")
    if origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        
    return response


# =============================================================================
# Instant Health Check Endpoint (Returns 200 OK immediately)
# =============================================================================
@app.get("/health", tags=["System"])
async def health_check(request: Request) -> JSONResponse:
    """Instant health check endpoint for Render/Docker monitoring."""
    db_ready = getattr(request.app.state, "db_ready", False)

    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "database": "connected" if db_ready else "connecting",
        },
    )

@app.get("/healthz", tags=["System"])
async def healthz_check() -> JSONResponse:
    """Standard Kubernetes liveness probe endpoint."""
    return JSONResponse(
        status_code=200,
        content={"status": "ok"}
    )


@app.get("/logo.png", tags=["System"])
async def serve_logo() -> FileResponse:
    return FileResponse("templates/logo.png")


# =============================================================================
# Static Files & Templates
# =============================================================================
app.mount("/static", StaticFiles(directory="templates"), name="static")
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
templates = Jinja2Templates(directory="templates")


# =============================================================================
# Router Registration
# =============================================================================
from routers import auth, marketing, api, user_api, paypal_webhook, video, ecommerce, creative_api  # noqa: E402
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(auth.router)
app.include_router(marketing.router)
app.include_router(api.router)
app.include_router(api.public_router)
app.include_router(user_api.router)
app.include_router(user_api.businesses_router)
app.include_router(paypal_webhook.router)
app.include_router(video.router)
app.include_router(ecommerce.router)
app.include_router(creative_api.router)


# =============================================================================
# Root Redirect
# =============================================================================
@app.get("/")
async def root() -> RedirectResponse:
    if settings.environment == "production":
        return RedirectResponse(url="/health", status_code=303)
    return RedirectResponse(url="/docs", status_code=303)


# =============================================================================
# Quick Stats API
# =============================================================================
@app.get("/api/v1/stats")
async def get_stats(request: Request) -> dict:
    """Return high-level platform statistics using SQLAlchemy session."""
    try:
        async with AsyncSessionLocal() as session:
            u_stmt = select(func.count(User.id))
            a_stmt = select(func.count(Audience.id))
            p_stmt = select(func.count(SocialPost.id))
            c_stmt = select(func.count(SocialCampaign.id))

            users = (await session.execute(u_stmt)).scalar() or 0
            audiences = (await session.execute(a_stmt)).scalar() or 0
            posts = (await session.execute(p_stmt)).scalar() or 0
            campaigns = (await session.execute(c_stmt)).scalar() or 0

        return {
            "success": True,
            "data": {
                "users": users,
                "audience": audiences,
                "posts": posts,
                "campaigns": campaigns,
            },
        }
    except Exception as e:
        return {
            "success": True,
            "data": {"users": 0, "audience": 0, "posts": 0, "campaigns": 0},
        }


# =============================================================================
# Public Stats API (No Auth — for Landing Page)
# =============================================================================
@app.get("/api/public/stats", tags=["Public"])
async def get_public_stats() -> dict:
    """Public stats for the landing page. Returns real platform numbers."""
    try:
        async with AsyncSessionLocal() as session:
            users = (await session.execute(select(func.count(User.id)))).scalar() or 0
            posts = (await session.execute(select(func.count(SocialPost.id)))).scalar() or 0
            campaigns = (await session.execute(select(func.count(SocialCampaign.id)))).scalar() or 0
            workspaces = (await session.execute(select(func.count(BusinessProfile.id)))).scalar() or 0

        return {
            "users": users,
            "posts": posts,
            "campaigns": campaigns,
            "workspaces": workspaces,
            "platforms": 4,
            "setupMinutes": 2,
        }
    except Exception:
        return {
            "users": 0,
            "posts": 0,
            "campaigns": 0,
            "workspaces": 0,
            "platforms": 4,
            "setupMinutes": 2,
        }


@app.get("/api/public/recent-activity", tags=["Public"])
async def get_public_recent_activity() -> dict:
    """Public recent activity feed for landing page social proof."""
    try:
        async with AsyncSessionLocal() as session:
            stmt = (
                select(SocialPost)
                .where(SocialPost.status == "POSTED")
                .order_by(SocialPost.postedAt.desc())
                .limit(5)
            )
            posts = (await session.execute(stmt)).scalars().all()

            return {
                "success": True,
                "data": [
                    {
                        "platform": p.platform,
                        "caption": (p.caption or "")[:80] + ("..." if len(p.caption or "") > 80 else ""),
                        "postedAt": p.postedAt.isoformat() if p.postedAt else None,
                    }
                    for p in posts
                ],
            }
    except Exception:
        return {"success": True, "data": []}


@app.get("/api/public/self-promotion", tags=["Public"])
async def get_public_self_promotion() -> dict:
    """Public self-promotion engine endpoint demonstrating platform self-marketing."""
    try:
        async with AsyncSessionLocal() as session:
            # Find system workspace
            sys_user = (await session.execute(select(User).where(User.email == "system@organicai.pro"))).scalar()
            if not sys_user:
                return {"active": False, "campaigns": [], "posts": []}

            c_stmt = (
                select(SocialCampaign)
                .where(SocialCampaign.userId == sys_user.id)
                .order_by(SocialCampaign.createdAt.desc())
                .limit(6)
            )
            campaigns = (await session.execute(c_stmt)).scalars().all()

            p_stmt = (
                select(SocialPost)
                .where(SocialPost.userId == sys_user.id)
                .order_by(SocialPost.scheduledAt.desc())
                .limit(6)
            )
            posts = (await session.execute(p_stmt)).scalars().all()

            return {
                "active": True,
                "botName": "OrganicAI Self-Growth Engine",
                "intervalHours": 2,
                "campaigns": [
                    {
                        "id": c.id,
                        "caption": c.baseCaption,
                        "mediaUrl": c.mediaUrl or "https://images.unsplash.com/photo-1611162617474-5b21e879e113?q=80&w=1000&auto=format&fit=crop",
                        "createdAt": c.createdAt.isoformat() if c.createdAt else None,
                    }
                    for c in campaigns if c.baseCaption
                ],
                "posts": [
                    {
                        "id": p.id,
                        "platform": p.platform,
                        "caption": p.caption,
                        "mediaUrls": p.mediaUrls,
                        "status": p.status,
                        "scheduledAt": p.scheduledAt.isoformat() if p.scheduledAt else None,
                    }
                    for p in posts
                ],
            }
    except Exception as e:
        return {"active": False, "error": str(e), "campaigns": [], "posts": []}

