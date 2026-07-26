"""Tests for campaign CRUD endpoints."""
import pytest
from httpx import AsyncClient


async def _register_and_login(client: AsyncClient, email: str = "camp@example.com") -> str:
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "StrongPass123!"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "StrongPass123!"},
    )
    return resp.json().get("token", "")


@pytest.mark.asyncio
async def test_list_campaigns_empty(client: AsyncClient):
    token = await _register_and_login(client)
    resp = await client.get(
        "/api/v1/campaigns",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_create_campaign(client: AsyncClient):
    token = await _register_and_login(client, "create_camp@example.com")

    me = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    profile = me.json().get("businessProfile")
    if not profile:
        pytest.skip("No default business profile created")

    workspace_id = profile["id"]
    resp = await client.post(
        "/api/v1/campaigns",
        json={
            "baseCaption": "Test campaign caption",
            "mediaUrl": "https://example.com/image.jpg",
            "mediaType": "image",
        },
        headers={
            "Authorization": f"Bearer {token}",
            "X-Workspace-Id": workspace_id,
        },
    )
    assert resp.status_code in (200, 201)
