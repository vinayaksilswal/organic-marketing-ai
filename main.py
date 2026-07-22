"""
=============================================================================
Organic Marketing AI — FastAPI Application Entry Point
=============================================================================
This is the control center for the entire autonomous marketing platform.
It hosts the AI chatbot, marketing automation scheduler, and all
API endpoints for social media, email, and Stripe integrations.

CRITICAL ARCHITECTURE DECISION:
  The Prisma client is instantiated and connected INSIDE the async lifespan
  context manager — NOT at module level. This ensures the client is bound
  to the active Uvicorn event loop, preventing asyncio.locks.Event errors
  that occur when Prisma is created before the loop starts.

Run locally:
  uvicorn main:app --reload --port 8000
=============================================================================
"""

from __future__ import annotations

import os
import sys
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from loguru import logger
from prisma import Prisma
from prometheus_fastapi_instrumentator import Instrumentator

from config import settings

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


def resolve_prisma_engine() -> str | None:
    """
    Locates and verifies an executable Prisma query engine binary, setting
    PRISMA_QUERY_ENGINE_BINARY.
    """
    existing = os.environ.get("PRISMA_QUERY_ENGINE_BINARY")
    if existing and os.path.isfile(existing):
        try:
            os.chmod(existing, 0o777)
        except Exception:
            pass
        logger.info(f"Using existing PRISMA_QUERY_ENGINE_BINARY: {existing}")
        return existing

    import subprocess
    import prisma

    prisma_dir = os.path.dirname(prisma.__file__)
    engine_name = "prisma-query-engine-debian-openssl-3.0.x"

    explicit_paths = [
        f"/opt/render/project/src/{engine_name}",
        f"/opt/render/.cache/prisma-python/binaries/5.17.0/393aa359c9ad4a4bb28630fb5613f9c281cde053/{engine_name}",
        engine_name,
        "query-engine-debian-openssl-3.0.x",
        os.path.join(prisma_dir, engine_name),
        os.path.join(prisma_dir, "bin", "query-engine"),
    ]

    for path in explicit_paths:
        abs_path = os.path.abspath(path)
        if os.path.isfile(abs_path):
            try:
                os.chmod(abs_path, 0o777)
                res = subprocess.run([abs_path, "--version"], capture_output=True, timeout=5)
                if res.returncode == 0:
                    os.environ["PRISMA_QUERY_ENGINE_BINARY"] = abs_path
                    logger.info(f"Verified executable Prisma engine at: {abs_path}")
                    return abs_path
            except Exception as e:
                logger.warning(f"Engine candidate at {abs_path} failed execution check: {e}")

    # Recursive fallback search
    search_roots = [
        "/opt/render",
        prisma_dir,
        os.path.expanduser("~/.cache"),
        "/root/.cache",
        "/tmp",
        ".",
    ]

    for root_dir in search_roots:
        if os.path.exists(root_dir):
            for root, _, files in os.walk(root_dir):
                for file in files:
                    if "query-engine" in file and not file.endswith((".gz", ".py", ".pyc", ".json", ".lock")):
                        full_path = os.path.join(root, file)
                        try:
                            os.chmod(full_path, 0o777)
                            res = subprocess.run([full_path, "--version"], capture_output=True, timeout=5)
                            if res.returncode == 0:
                                os.environ["PRISMA_QUERY_ENGINE_BINARY"] = full_path
                                logger.info(f"Verified executable Prisma engine binary at: {full_path}")
                                return full_path
                        except Exception:
                            pass

    logger.warning("Could not locate verified executable Prisma query engine binary")
    return None


# =============================================================================
# Application Lifespan — Async Context Manager
# =============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Manages the lifecycle of critical application resources:
    1. Prisma ORM client (PostgreSQL connection)
    2. APScheduler (marketing automation loop)

    CRUCIAL: Prisma MUST be instantiated inside this async context to bind
    to the active Uvicorn event loop.
    """
    from services.scheduler import create_scheduler, shutdown_scheduler

    logger.info("=" * 60)
    logger.info("Organic Marketing AI Platform — Starting Up")
    logger.info(f"Environment: {settings.environment}")
    logger.info("=" * 60)

    # Resolve engine binary before instantiating Prisma
    resolve_prisma_engine()

    # --- Step 1: Connect Prisma ORM ---
    prisma_client = None
    try:
        os.environ["DATABASE_URL"] = settings.database_url
        prisma_client = Prisma()
        await prisma_client.connect()
        app.state.prisma = prisma_client
        if hasattr(app.state, "prisma_error"):
            delattr(app.state, "prisma_error")
        logger.info("Prisma ORM connected to PostgreSQL successfully")
    except Exception as e:
        logger.error(f"Failed to connect Prisma engine: {e}")
        app.state.prisma_error = str(e)

    # --- Step 2: Initialize and start the marketing scheduler ---
    if prisma_client and prisma_client.is_connected():
        scheduler = create_scheduler(prisma_client)
        scheduler.start()
        app.state.scheduler = scheduler
        logger.info("APScheduler started (marketing automation loop active)")
    else:
        logger.warning("Prisma client not connected, skipping scheduler startup")
        app.state.scheduler = None

    logger.info("=" * 60)
    logger.info("Organic Marketing AI is ready to serve requests")
    logger.info("=" * 60)

    yield  # --- Application is running ---

    # --- Shutdown: Clean up resources in reverse order ---
    logger.info("Shutting down Organic Marketing AI...")

    if getattr(app.state, "scheduler", None):
        shutdown_scheduler(app.state.scheduler)
        logger.info("Scheduler stopped")

    if prisma_client and prisma_client.is_connected():
        await prisma_client.disconnect()
    logger.info("Prisma ORM disconnected")

    logger.info("Organic Marketing AI shutdown complete.")


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

# --- Prometheus metrics endpoint at /metrics ---
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
    """
    Custom HTTP exception handler:
    - If a 401 hits an /admin page (not /admin/login), redirect to login.
    - Otherwise, return a structured JSON error response.
    """
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
    """Catch-all handler to prevent 500 errors from leaking stack traces."""
    error_id = str(uuid.uuid4())
    logger.exception(f"Unhandled Exception on {request.method} {request.url.path} (Error ID: {error_id})")
    
    # Don't leak internal error details in production
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
    """
    Health check endpoint for Render/Docker monitoring.
    Returns HTTP 200 to keep the service healthy while reporting DB status.
    """
    db_status = "disconnected"
    prisma_err = getattr(request.app.state, "prisma_error", None)

    if not prisma_err:
        try:
            prisma: Prisma = getattr(request.app.state, "prisma", None)
            if prisma and prisma.is_connected():
                await prisma.query_raw("SELECT 1")
                db_status = "connected"
        except Exception as e:
            logger.error(f"Health check DB query failed: {e}")
            db_status = f"error: {str(e)}"

    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy" if db_status == "connected" else "degraded",
            "database": db_status,
            "error": prisma_err,
        },
    )


@app.get("/logo.png", tags=["System"])
async def serve_logo() -> FileResponse:
    """Serve the application logo."""
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
    """Redirect the root URL to the API docs (dev) or health check (prod)."""
    if settings.environment == "production":
        return RedirectResponse(url="/health", status_code=303)
    return RedirectResponse(url="/docs", status_code=303)


# =============================================================================
# Quick Stats API (used by the dashboard)
# =============================================================================
@app.get("/api/stats")
async def get_stats(request: Request) -> dict:
    """Return high-level platform statistics for the admin dashboard."""
    prisma: Prisma = request.app.state.prisma
    audience_count = await prisma.audience.count()
    user_count = await prisma.user.count()
    post_count = await prisma.socialpost.count()
    campaign_count = await prisma.socialcampaign.count()

    return {
        "success": True,
        "data": {
            "users": user_count,
            "audience": audience_count,
            "posts": post_count,
            "campaigns": campaign_count,
        },
    }
