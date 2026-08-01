"""
=============================================================================
Organic Marketing AI — FastAPI Application Entry Point
=============================================================================
This is the control center for the entire autonomous marketing platform.
It hosts the AI chatbot, marketing automation scheduler, and all
API endpoints for social media, email, and PayPal integrations.

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

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel
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
async def _fail_orphaned_generations() -> None:
    """Close out prompt generations that a restart interrupted.

    A row left on PENDING shows in the UI as an entry with no prompt and no
    explanation, which reads as "it generated nothing". Marking them FAILED
    tells the user plainly that the run died and they should try again.

    Defensive: this runs during bootstrap and must never prevent startup.
    """
    try:
        from sqlalchemy import update
        from database import AsyncSessionLocal, Media

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                update(Media)
                .where(Media.generationStatus == "PENDING")
                .values(
                    generationStatus="FAILED",
                    generationError=(
                        "Generation was interrupted by a server restart. "
                        "Please generate again."
                    ),
                )
            )
            await session.commit()
            if result.rowcount:
                logger.warning(
                    f"Marked {result.rowcount} interrupted prompt generation(s) as FAILED"
                )
    except Exception as e:
        logger.warning(f"Could not reconcile interrupted generations: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Manages application startup non-blockingly so Render web server boots in < 1 second.
    Database initialization, schema migration, seeding, and scheduler start happen
    in a background task so the HTTP server is available immediately.
    """
    from services.scheduler import create_scheduler, shutdown_scheduler
    from services.seed_service import run_all_seeds

    # Initialize Sentry error tracking if configured
    if settings.sentry_dsn:
        try:
            import sentry_sdk
            sentry_sdk.init(
                dsn=settings.sentry_dsn,
                environment=settings.environment,
                traces_sample_rate=0.1,
            )
            logger.info("Sentry error tracking initialized")
        except Exception as e:
            logger.warning(f"Sentry init failed: {e}")

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

            # 2. Run all database seeds (system user, superadmin, etc.)
            await run_all_seeds()

            # 3. Recover generations orphaned by a restart. Prompt writing runs
            #    in a background task; if the worker is replaced mid-flight the
            #    row is left PENDING forever with an empty prompt and no reason.
            await _fail_orphaned_generations()

            # 4. Start the APScheduler for marketing automation
            scheduler = create_scheduler()
            scheduler.start()
            app.state.scheduler = scheduler
            logger.info("APScheduler started (marketing automation loop active)")

        except Exception as e:
            logger.error(f"Background bootstrap error: {e}")
            app.state.db_ready = False
            app.state.db_error = str(e)

    # Held on app.state: asyncio keeps only a weak reference to tasks, so a
    # bare create_task() can be garbage collected before the DB and scheduler
    # finish initialising.
    app.state.bootstrap_task = asyncio.create_task(bg_bootstrap())

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
    allow_origins=settings.allowed_origins,
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
    """Instant health check endpoint for Render/Docker monitoring.

    Reports the running commit so deploy drift is detectable — a stale build
    silently serving old code is otherwise invisible until endpoints 404.
    """
    db_ready = getattr(request.app.state, "db_ready", False)

    # Booleans only — never the values. Lets an operator confirm which
    # integrations are actually wired up, instead of inferring it from a 503
    # that only appears after authentication. Wrapped because /health is the
    # liveness probe and must not fail for a reporting detail.
    try:
        integrations = {
            "meta": bool(settings.fb_app_id and settings.fb_app_secret),
            "paypal": bool(settings.paypal_client_id and settings.paypal_client_secret),
            "paypal_webhook": bool(settings.paypal_webhook_id),
            "openrouter": bool(settings.openrouter_api_key),
            "cloudinary": bool(settings.cloudinary_cloud_name and settings.cloudinary_api_secret),
            "resend": bool(
                settings.resend_api_key and "your_resend" not in (settings.resend_api_key or "")
            ),
            "json2video": bool(settings.json2video_api_key),
        }
    except Exception:
        integrations = {}

    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "database": "connected" if db_ready else "connecting",
            "version": app.version,
            "commit": os.getenv("RENDER_GIT_COMMIT", os.getenv("GIT_COMMIT", "unknown"))[:12],
            "integrations": integrations,
        },
    )

@app.get("/healthz", tags=["System"])
async def healthz_check() -> JSONResponse:
    """Standard Kubernetes liveness probe endpoint."""
    return JSONResponse(
        status_code=200,
        content={"status": "ok"}
    )


@app.get("/api/v1/admin/system-status", tags=["Admin"])
async def admin_system_status(request: Request):
    """Admin-only system status: scheduler, DB pool, Redis, latest posts."""
    from auth import verify_credentials
    verify_credentials(request)

    db_ready = getattr(request.app.state, "db_ready", False)
    scheduler = getattr(request.app.state, "scheduler", None)
    scheduler_running = scheduler.running if scheduler else False

    redis_ok = False
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.redis_url, socket_connect_timeout=2)
        await r.ping()
        redis_ok = True
        await r.aclose()
    except Exception:
        pass

    pool_status = {}
    engine = getattr(request.app.state, "db_engine", None)
    if engine:
        pool = engine.pool
        pool_status = {
            "size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
        }

    recent_posts = []
    if db_ready:
        try:
            async with AsyncSessionLocal() as session:
                stmt = select(SocialPost).order_by(SocialPost.createdAt.desc()).limit(5)
                posts = (await session.execute(stmt)).scalars().all()
                recent_posts = [
                    {
                        "id": p.id,
                        "platform": p.platform,
                        "status": p.status,
                        "postedAt": p.postedAt.isoformat() if p.postedAt else None,
                    }
                    for p in posts
                ]
        except Exception:
            pass

    return {
        "database": "connected" if db_ready else "disconnected",
        "db_pool": pool_status,
        "scheduler": "running" if scheduler_running else "stopped",
        "redis": "connected" if redis_ok else "unavailable",
        "recent_posts": recent_posts,
    }


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
from routers import auth, marketing, api, user_api, paypal_webhook, video, ecommerce, creative_api, team, meta_oauth, billing, data_deletion  # noqa: E402
from routers.auth import verify_user  # noqa: E402
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
# Prompt Engine router import
from prompt_engine.router import router as prompt_engine_router  # noqa: E402


def _get_rate_limit_key(request: Request) -> str:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            import jwt as pyjwt
            payload = pyjwt.decode(auth_header.split(" ")[1], options={"verify_signature": False})
            uid = payload.get("sub")
            if uid:
                return f"user:{uid}"
        except Exception:
            pass
    return get_remote_address(request)


limiter = Limiter(key_func=_get_rate_limit_key, default_limits=["200/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(auth.router)
app.include_router(marketing.router)
app.include_router(api.router)
app.include_router(api.public_router)
app.include_router(user_api.router)
app.include_router(user_api.businesses_router)
app.include_router(paypal_webhook.router)
app.include_router(billing.router)
app.include_router(video.router)
app.include_router(ecommerce.router)
app.include_router(creative_api.router)
app.include_router(team.router)
app.include_router(meta_oauth.router)
# Meta App Review requires a Data Deletion Callback; GDPR Arts. 17 and 20
# require the self-serve erase and export on the same router.
app.include_router(data_deletion.router)
# Prompt Engine router inclusion
app.include_router(prompt_engine_router)


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
async def get_stats(request: Request, user_id: str = Depends(verify_user)) -> dict:
    """Stats for the caller's active workspace.

    This previously counted every row in the database — all users, all posts,
    all campaigns, platform-wide — with no authentication. Every customer saw
    identical totals that included other customers' data, and the numbers never
    changed when switching business. Now scoped to the caller, and to the
    active workspace when one is supplied.
    """
    workspace_id = request.headers.get("x-workspace-id") or request.headers.get("X-Workspace-Id")

    try:
        async with AsyncSessionLocal() as session:
            # Confirm the workspace belongs to the caller before counting by it,
            # so a forged header cannot read another tenant's numbers.
            if workspace_id:
                owned = (await session.execute(
                    select(BusinessProfile.id).where(
                        BusinessProfile.id == workspace_id,
                        BusinessProfile.userId == user_id,
                    )
                )).scalar_one_or_none()
                if not owned:
                    workspace_id = None

            def scoped(model):
                stmt = select(func.count(model.id))
                if workspace_id:
                    return stmt.where(model.businessProfileId == workspace_id)
                # No workspace selected: everything this user owns
                return stmt.where(model.businessProfileId.in_(
                    select(BusinessProfile.id).where(BusinessProfile.userId == user_id)
                ))

            audiences = (await session.execute(scoped(Audience))).scalar() or 0
            posts = (await session.execute(scoped(SocialPost))).scalar() or 0
            campaigns = (await session.execute(scoped(SocialCampaign))).scalar() or 0
            workspaces = (await session.execute(
                select(func.count(BusinessProfile.id)).where(BusinessProfile.userId == user_id)
            )).scalar() or 0

        return {
            "success": True,
            "data": {
                "posts": posts,
                "campaigns": campaigns,
                "audience": audiences,
                "workspaces": workspaces,
                # Retained for the existing card; now means "your businesses",
                # not "every account on the platform".
                "users": workspaces,
            },
        }
    except Exception:
        logger.exception(f"Stats query failed for user {user_id}")
        return {
            "success": False,
            "data": {"posts": 0, "campaigns": 0, "audience": 0, "workspaces": 0, "users": 0},
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


# The landing page demo used to be a setTimeout over a hardcoded template
# string, presented as "see what our AI can generate for your brand". This runs
# the real caption writer so the demo is the product.
#
# Rate limited per IP because it is unauthenticated and every call costs an AI
# request. In-memory is adequate: the service runs one worker, and the worst
# case of a reset is a visitor getting a few extra tries.
_DEMO_CALLS: dict[str, list[float]] = {}
_DEMO_LIMIT = 3
_DEMO_WINDOW_SECONDS = 3600


class DemoCaptionRequest(BaseModel):
    businessName: str
    businessModel: str = "SaaS"
    description: str = ""


@app.post("/api/public/demo-caption", tags=["Public"])
async def public_demo_caption(data: DemoCaptionRequest, request: Request) -> dict:
    """Write one real caption for an unregistered visitor's business."""
    import time

    name = (data.businessName or "").strip()[:80]
    if not name:
        raise HTTPException(status_code=400, detail="Enter your business name.")

    client_ip = (
        (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
        or (request.client.host if request.client else "unknown")
    )
    now = time.time()
    hits = [t for t in _DEMO_CALLS.get(client_ip, []) if now - t < _DEMO_WINDOW_SECONDS]
    if len(hits) >= _DEMO_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="You have used the free preview a few times. Create an account to keep going — it is free.",
        )
    hits.append(now)
    _DEMO_CALLS[client_ip] = hits

    # A throwaway profile so the real writer runs against real inputs.
    class _DemoProfile:
        id = None
        name = data.businessName.strip()[:80]
        description = (data.description or "").strip()[:400]
        websiteUrl = ""
        industry = (data.businessModel or "SaaS")[:60]
        businessModel = (data.businessModel or "SaaS")[:60]
        niche = ""
        targetAudience = ""
        toneOfVoice = "clear, specific, no hype"
        contentPillars = []
        suggestedHashtags = []
        primaryOffer = None

    try:
        from routers.marketing import _generate_post_caption

        caption = await _generate_post_caption(_DemoProfile(), None)
        return {"success": True, "caption": caption, "remaining": _DEMO_LIMIT - len(hits)}
    except Exception:
        logger.exception("Public demo caption failed")
        raise HTTPException(
            status_code=503,
            detail="The AI is busy right now. Please try again in a moment.",
        )


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

