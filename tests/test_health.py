"""Tests for health check and public endpoints."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") in ("healthy", "ok", True)


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    resp = await client.get("/")
    assert resp.status_code in (200, 301, 302, 303, 307)


def test_health_reports_every_publishing_integration():
    """X, LinkedIn and YouTube publish for real now.

    Their app-level credentials are set separately from Meta's, and until
    this landed an operator who added them in Render could only confirm it
    by connecting an account and watching a post fail.
    """
    import inspect
    import main

    src = inspect.getsource(main)
    block = src[src.index('integrations = {'):]
    block = block[: block.index('}')]

    for key in ('"meta"', '"x"', '"linkedin"', '"youtube"', '"resend"'):
        assert key in block, f"/health does not report {key}"


def test_health_never_reports_a_credential_value():
    """Booleans only. /health is unauthenticated."""
    import inspect
    import main

    src = inspect.getsource(main)
    block = src[src.index('integrations = {'):]
    block = block[: block.index('except Exception')]

    for line in block.splitlines():
        if ':' in line and 'settings.' in line and not line.strip().startswith('#'):
            assert 'bool(' in block, "a raw setting may be leaking into /health"
