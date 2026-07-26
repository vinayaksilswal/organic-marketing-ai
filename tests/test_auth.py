"""Tests for authentication endpoints."""
import pytest
import pytest_asyncio
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_new_user(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "test@example.com", "password": "StrongPass123!"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data or "id" in data or "success" in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    payload = {"email": "dupe@example.com", "password": "StrongPass123!"}
    await client.post("/api/v1/auth/register", json=payload)
    resp = await client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code in (400, 409, 422)


@pytest.mark.asyncio
async def test_login_valid_credentials(client: AsyncClient):
    payload = {"email": "login@example.com", "password": "StrongPass123!"}
    await client.post("/api/v1/auth/register", json=payload)
    resp = await client.post("/api/v1/auth/login", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    payload = {"email": "wrong@example.com", "password": "StrongPass123!"}
    await client.post("/api/v1/auth/register", json=payload)
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "wrong@example.com", "password": "BadPassword!"},
    )
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_protected_route_no_token(client: AsyncClient):
    resp = await client.get("/api/v1/users/me")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_protected_route_with_token(client: AsyncClient):
    payload = {"email": "authed@example.com", "password": "StrongPass123!"}
    reg = await client.post("/api/v1/auth/register", json=payload)
    login = await client.post("/api/v1/auth/login", json=payload)
    token = login.json().get("token", "")
    resp = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
