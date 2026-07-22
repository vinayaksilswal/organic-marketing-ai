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
from database import init_db, close_db, AsyncSessionLocal, User, Audience, SocialPost, SocialCampaign

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
# Application Lifespan — Async Context Manager
# =============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Manages the lifecycle of application resources:
    1. SQLAlchemy 2.0 Async ORM engine & pool
    2. APScheduler (marketing automation loop)
    """
    from services.scheduler import create_scheduler, shutdown_scheduler

    logger.info("=" * 60)
    logger.info("Organic Marketing AI Platform — Starting Up")
    logger.info(f"Environment: {settings.environment}")
    logger.info("=" * 60)

    # --- Step 1: Initialize SQLAlchemy Database Engine & Tables ---
    engine = None
    try:
        engine = await init_db()
        app.state.db_engine = engine
        app.state.db_ready = True
        logger.info("SQLAlchemy ORM connected to PostgreSQL successfully")
    except Exception as e:
        logger.error(f"Failed to connect SQLAlchemy database engine: {e}")
        app.state.db_ready = False
        app.state.db_error = str(e)

    # --- Step 2: Initialize and start the marketing scheduler ---
    if getattr(app.state, "db_ready", False):
        scheduler = create_scheduler()
        scheduler.start()
        app.state.scheduler = scheduler
        logger.info("APScheduler started (marketing automation loop active)")
    else:
        logger.warning("Database not ready, skipping scheduler startup")
        app.state.scheduler = None

    logger.info("=" * 60)
    logger.info("Organic Marketing AI is ready to serve requests")
    logger.info("=" * 60)

    yield  # --- Application is running ---

    # --- Shutdown ---
    logger.info("Shutting down Organic Marketing AI...")

    if getattr(app.state, "scheduler", None):
        shutdown_scheduler(app.state.scheduler)
        logger.info("Scheduler stopped")

    await close_db()
    logger.info("SQLAlchemy ORM shutdown complete.")


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

# Prometheus metrics
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
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    
    detail = "An internal error occurred. Please try again later."
    if settings.environment != "production":
        detail = str(exc)
    
    return JSONResponse(
        status_code=500,
        content={"success": False, "message": detail, "error_id": error_id},
    )


# =============================================================================
# Health Check Endpoint
# =============================================================================
@app.get("/health", tags=["System"])
async def health_check(request: Request) -> JSONResponse:
    """Health check endpoint for Render/Docker monitoring."""
    db_status = "disconnected"
    db_err = getattr(request.app.state, "db_error", None)

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            db_status = "connected"
    except Exception as e:
        logger.error(f"Health check DB query failed: {e}")
        db_status = f"error: {str(e)}"

    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy" if db_status == "connected" else "degraded",
            "database": db_status,
            "error": db_err,
        },
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
from routers import api, auth, marketing, user_api, stripe_webhook  # noqa: E402
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
app.include_router(stripe_webhook.router)


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
@app.get("/api/stats")
async def get_stats(request: Request) -> dict:
    """Return high-level platform statistics using SQLAlchemy session."""
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
