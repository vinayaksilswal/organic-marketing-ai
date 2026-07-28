"""
=============================================================================
Live production smoke tests
=============================================================================
Verifies the deployed backend at BASE_URL, not a local instance.

    pytest tests/test_live_smoke.py -v

What this proves without credentials:
  - the service is up and reports which commit it is running
  - every route the frontend calls EXISTS (401/400, never 404)
  - no route 500s at the routing/auth layer
  - CORS is configured for the frontend origins
  - public endpoints return well-formed data

What it cannot prove: authenticated behaviour. Set LIVE_TEST_TOKEN to a valid
JWT to enable the authenticated block; it is skipped otherwise so the suite
never depends on a password living in CI.
=============================================================================
"""
import os

import httpx
import pytest

BASE_URL = os.getenv("LIVE_BASE_URL", "https://organic-marketing-ai1.onrender.com")
TOKEN = os.getenv("LIVE_TEST_TOKEN")
FRONTEND_ORIGIN = "https://organic-marketing-ai.vercel.app"

# Render free tier sleeps; the first request can take a while to wake it.
TIMEOUT = httpx.Timeout(90.0)

# Every authenticated route the dashboard calls. A 404 here means the deploy is
# stale or the router was dropped; a 500 means it is broken before auth runs.
AUTH_ROUTES = [
    ("GET", "/api/v1/businesses"),
    ("GET", "/api/v1/team"),
    ("GET", "/api/v1/stats"),
    ("GET", "/api/v1/social/scheduler-status"),
    ("GET", "/api/v1/social/recent-posts"),
    ("GET", "/api/v1/marketing/media"),
    ("GET", "/api/v1/marketing/posts"),
    ("GET", "/api/v1/marketing/settings"),
    ("GET", "/api/v1/marketing/emails"),
    ("GET", "/api/v1/marketing/audiences"),
    ("GET", "/api/v1/ecommerce/products"),
    ("GET", "/api/v1/video/config"),
    ("GET", "/api/v1/users/me"),
    ("GET", "/api/v1/admin/system-status"),
    ("GET", "/api/v1/meta/connect?workspace_id=probe"),
    ("POST", "/api/v1/creatives/auto-video"),
    ("POST", "/api/v1/marketing/run-automation"),
    ("POST", "/api/v1/users/me/subscribe"),
]

PUBLIC_ROUTES = [
    "/api/public/stats",
    "/api/public/recent-activity",
    "/api/public/self-promotion",
]


@pytest.fixture(scope="module")
def client():
    with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT, follow_redirects=False) as c:
        yield c


# --------------------------------------------------------------------------
# Service health
# --------------------------------------------------------------------------
def test_health_reports_running_commit(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "healthy"
    assert body["database"] == "connected"
    # Present only on builds that include the deploy-drift fix. Its absence
    # means the server is serving an older image than the repo.
    assert body.get("commit") not in (None, "", "unknown"), (
        "No commit reported — the deployed build is stale."
    )


def test_healthz_liveness(client):
    r = client.get("/healthz")
    assert r.status_code == 200


# --------------------------------------------------------------------------
# Routing: every route exists and nothing 500s before auth
# --------------------------------------------------------------------------
@pytest.mark.parametrize("method,path", AUTH_ROUTES)
def test_route_exists_and_is_auth_gated(client, method, path):
    r = client.request(method, path)

    assert r.status_code != 404, f"{method} {path} does not exist on the deployed build"
    assert r.status_code < 500, f"{method} {path} returned {r.status_code} before auth ran"
    # Unauthenticated callers must be rejected, never served.
    assert r.status_code in (400, 401, 403, 422), (
        f"{method} {path} returned {r.status_code} without a token — expected a rejection"
    )


@pytest.mark.parametrize("path", PUBLIC_ROUTES)
def test_public_route_returns_json(client, path):
    r = client.get(path)
    assert r.status_code == 200, f"{path} returned {r.status_code}"
    assert isinstance(r.json(), (dict, list))


def test_public_stats_shape(client):
    body = client.get("/api/public/stats").json()
    for key in ("users", "posts", "campaigns", "workspaces"):
        assert key in body, f"missing {key}"
        assert isinstance(body[key], int)


# --------------------------------------------------------------------------
# Security posture
# --------------------------------------------------------------------------
def test_stats_requires_authentication(client):
    """This endpoint once counted the whole database with no auth at all."""
    r = client.get("/api/v1/stats")
    assert r.status_code == 401


def test_subscribe_rejects_unauthenticated(client):
    r = client.post("/api/v1/users/me/subscribe", json={"order_id": "fake"})
    assert r.status_code in (401, 403, 422)


def test_docs_disabled_in_production(client):
    """docs_url is None when ENVIRONMENT=production."""
    r = client.get("/docs")
    assert r.status_code == 404, "API docs are exposed — ENVIRONMENT is not 'production'"


# --------------------------------------------------------------------------
# CORS
# --------------------------------------------------------------------------
@pytest.mark.parametrize("origin", [
    FRONTEND_ORIGIN,
    "http://localhost:5173",
])
def test_cors_preflight_allows_origin(client, origin):
    r = client.request(
        "OPTIONS",
        "/api/v1/businesses",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,x-workspace-id",
        },
    )
    assert r.status_code in (200, 204), f"preflight failed for {origin}"
    allowed = r.headers.get("access-control-allow-origin")
    assert allowed in (origin, "*"), f"{origin} not allowed by CORS (got {allowed!r})"


def test_cors_allows_workspace_header(client):
    """X-Workspace-Id must survive preflight or every scoped call breaks."""
    r = client.request(
        "OPTIONS",
        "/api/v1/marketing/media",
        headers={
            "Origin": FRONTEND_ORIGIN,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "x-workspace-id",
        },
    )
    allowed = (r.headers.get("access-control-allow-headers") or "").lower()
    assert "x-workspace-id" in allowed or "*" in allowed


# --------------------------------------------------------------------------
# Authenticated (opt-in via LIVE_TEST_TOKEN)
# --------------------------------------------------------------------------
requires_token = pytest.mark.skipif(not TOKEN, reason="set LIVE_TEST_TOKEN to run authenticated checks")


@requires_token
def test_authenticated_businesses_returns_list(client):
    r = client.get("/api/v1/businesses", headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@requires_token
def test_authenticated_routes_do_not_error(client):
    failures = []
    for method, path in AUTH_ROUTES:
        if method != "GET" or "meta/connect" in path:
            continue  # POSTs mutate; meta/connect 503s without FB_APP_ID
        r = client.request(method, path, headers={"Authorization": f"Bearer {TOKEN}"})
        if r.status_code >= 500:
            failures.append(f"{method} {path} -> {r.status_code}")
    assert not failures, "Authenticated routes returning 5xx:\n" + "\n".join(failures)
