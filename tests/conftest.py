"""
Shared test fixtures for Organic Marketing AI test suite.
Uses an in-memory SQLite database so tests run without PostgreSQL.
"""
import os
import sys
from unittest.mock import AsyncMock, patch

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Ensure the project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

os.environ.setdefault("JWT_SECRET", "test-secret-key-for-testing-only-32chars!!")
os.environ.setdefault("ENCRYPTION_KEY", "dGVzdC1lbmNyeXB0aW9uLWtleS0zMmNoYXJzISE=")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")

from database import Base

# database.py deliberately does not import prompt_engine — a forward reference
# from the data layer to an application package pulled the FastAPI router into
# the Alembic migration process and broke deploys. The consequence here is that
# the prompt-engine tables are only in Base.metadata once their module is
# imported, so create_all() below would silently omit them. Production gets
# them from migration 016; tests import them explicitly.
from prompt_engine import db_models  # noqa: E402,F401


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    session_factory = async_sessionmaker(
        bind=db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_engine):
    """Provide an async test client with the SQLite test DB patched in."""
    import database

    session_factory = async_sessionmaker(
        bind=db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    original_sessionmaker = database._sessionmaker
    original_engine = database.engine
    database._sessionmaker = session_factory
    database.engine = db_engine

    with patch("services.scheduler.create_scheduler") as mock_sched:
        mock_scheduler = AsyncMock()
        mock_scheduler.start = lambda: None
        mock_scheduler.running = False
        mock_sched.return_value = mock_scheduler

        from main import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    database._sessionmaker = original_sessionmaker
    database.engine = original_engine


@pytest_asyncio.fixture
async def authed_client(db_engine):
    """A client whose requests are already authenticated.

    Yields (client, login) where login(user_id) sets which user the API sees.
    Endpoints that verify workspace ownership need the caller identity to match
    the BusinessProfile.userId under test, so the identity has to be settable
    per test rather than fixed.
    """
    import database
    from routers.auth import verify_user

    session_factory = async_sessionmaker(
        bind=db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    original_sessionmaker = database._sessionmaker
    original_engine = database.engine
    database._sessionmaker = session_factory
    database.engine = db_engine

    state = {"user_id": "test-user"}

    with patch("services.scheduler.create_scheduler") as mock_sched:
        mock_scheduler = AsyncMock()
        mock_scheduler.start = lambda: None
        mock_scheduler.running = False
        mock_sched.return_value = mock_scheduler

        from main import app

        app.dependency_overrides[verify_user] = lambda: state["user_id"]
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac, (lambda uid: state.__setitem__("user_id", uid))
        app.dependency_overrides.pop(verify_user, None)

    database._sessionmaker = original_sessionmaker
    database.engine = original_engine
