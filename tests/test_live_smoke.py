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

# The default follows the service that is actually deployed. The previous
# host stopped serving after a migration and every endpoint on it returns 503,
# so a suite defaulting there fails 91 checks for a reason that has nothing to
# do with the code under test.
BASE_URL = os.getenv("LIVE_BASE_URL", "https://organic-marketing-ai-0abh.onrender.com")
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
    # Billing. Money moves through these, so a stale deploy here is revenue.
    ("GET", "/api/v1/billing/me"),
    ("POST", "/api/v1/billing/subscribe"),
    ("POST", "/api/v1/billing/sync"),
    ("POST", "/api/v1/billing/cancel"),
    # Per-workspace email sending credentials.
    ("GET", "/api/v1/marketing/email-config"),
    ("POST", "/api/v1/marketing/email-config"),
    # Media edit — the endpoint the catalog's Save button calls.
    ("PATCH", "/api/v1/marketing/media/probe"),
    ("DELETE", "/api/v1/marketing/media/probe"),
    # Prompt engine. These shipped completely unauthenticated; anyone could
    # burn paid AI credit and write into another tenant's data.
    ("POST", "/api/v1/prompt/video"),
    ("POST", "/api/v1/prompt/caption"),
    ("POST", "/api/v1/prompt/caption/validate"),
    ("POST", "/api/v1/prompt/eval/ci"),
    ("GET", "/api/v1/prompt/probe"),
]

PUBLIC_ROUTES = [
    "/api/public/stats",
    "/api/public/recent-activity",
    "/api/public/self-promotion",
]

# Routes that must NOT exist. The prompt engine originally mounted at a bare
# /prompt prefix with no auth at all.
RETIRED_ROUTES = [
    ("POST", "/prompt/video"),
    ("POST", "/prompt/caption"),
    ("POST", "/prompt/eval/ci"),
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


def test_required_integrations_are_configured(client):
    """The env vars a paying customer's flow depends on are actually set.

    Reports booleans only. Meta gates all posting, so without it there is no
    product; PayPal gates revenue.
    """
    integrations = client.get("/health").json().get("integrations")
    if integrations is None:
        pytest.skip("deployed build predates integration reporting")

    required = {
        "meta": "Facebook/Instagram connect returns 503 — no posting is possible",
        "paypal": "subscriptions cannot be verified — no revenue",
        "paypal_webhook": "webhooks are unverified — renewals will not activate",
        "openrouter": "no AI generation at all",
        "cloudinary": "generated media cannot be stored",
    }
    unset = [f"{k}: {why}" for k, why in required.items() if not integrations.get(k)]
    assert not unset, "Unconfigured integrations:\n  " + "\n  ".join(unset)


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


@pytest.mark.parametrize("method,path", AUTH_ROUTES)
def test_route_does_not_demand_unexpected_params(client, method, path):
    """A 422 without a token means the route wants query params it should not.

    This caught a real defect: a helper function was inserted between a
    @router.post decorator and its handler, so the decorator bound to the
    helper and FastAPI demanded the helper's arguments as query parameters.
    The endpoint returned 422 for everyone.
    """
    r = client.request(method, path)
    assert r.status_code != 422, (
        f"{method} {path} returns 422 unauthenticated — it is likely bound to "
        f"the wrong function, or requires query params it should not"
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
# Billing — the pricing page and the biller must agree
# --------------------------------------------------------------------------
def test_plan_catalogue_is_public_and_complete(client):
    """The landing page renders from this. A 404 means nobody can subscribe."""
    r = client.get("/api/v1/billing/plans")
    assert r.status_code == 200, f"plan catalogue returned {r.status_code}"
    plans = r.json().get("plans")
    assert isinstance(plans, list) and plans, "no plans returned"

    codes = {p["code"] for p in plans}
    assert {"free", "starter"} <= codes, f"expected free and starter, got {codes}"

    for p in plans:
        for key in ("code", "name", "price", "tagline", "features", "limits"):
            assert key in p, f"plan {p.get('code')} missing {key}"
        assert isinstance(p["features"], list) and p["features"]
        assert isinstance(p["limits"], dict) and p["limits"]


def test_free_plan_is_actually_free_and_metered(client):
    """A free tier that grants unlimited paid AI calls is a cost leak."""
    plans = {p["code"]: p for p in client.get("/api/v1/billing/plans").json()["plans"]}
    free = plans["free"]
    assert free["price"] == 0
    limits = free["limits"]
    for metric in ("posts", "prompts", "businesses"):
        assert limits.get(metric) is not None, f"free plan has unlimited {metric}"
        assert limits[metric] > 0 if metric != "emails" else True


def test_advertised_entry_price_matches_the_biller(client):
    """The landing page promises $17. The biller must charge that."""
    plans = {p["code"]: p for p in client.get("/api/v1/billing/plans").json()["plans"]}
    assert plans["starter"]["price"] == 17.0, (
        f"starter is {plans['starter']['price']}, but the site advertises $17"
    )


# --------------------------------------------------------------------------
# Generation quality — the product's actual output
# --------------------------------------------------------------------------
# A deploying or cold-starting instance is not a defect in the commit under
# test. CI pushes to main, Render redeploys on that same push, and this suite
# then races the restart — which is exactly how runs #69 and #71 went red while
# every one of the 251 real tests passed. Gateway codes are retried, then
# skipped, never failed.
_GATEWAY_CODES = {502, 503, 504}


@pytest.fixture(scope="module")
def demo_caption(client):
    """One real caption from the public demo, generated by the live pipeline."""
    import time

    r = None
    for attempt in range(3):
        r = client.post(
            "/api/public/demo-caption",
            json={
                "businessName": "Ridgeline Bikes",
                "businessModel": "E-commerce",
                "description": "We build steel gravel bike frames by hand in Bristol, "
                               "made to measure and delivered in six weeks.",
            },
            timeout=httpx.Timeout(180.0),
        )
        if r.status_code not in _GATEWAY_CODES:
            break
        if attempt < 2:
            # Render's free tier takes tens of seconds to come back up.
            time.sleep(20)

    if r.status_code == 429:
        pytest.skip("demo rate limit reached for this IP")
    if r.status_code in _GATEWAY_CODES:
        pytest.skip(
            f"backend returned {r.status_code} after 3 attempts — deploying or "
            "cold-starting, not a fault in this commit"
        )
    assert r.status_code == 200, f"demo returned {r.status_code}: {r.text[:200]}"
    caption = r.json().get("caption")
    assert caption, "demo returned no caption"
    return caption


def test_generated_caption_carries_no_url(demo_caption):
    """Instagram does not linkify captions, so a raw link is dead text."""
    assert "http" not in demo_caption.lower()
    assert "www." not in demo_caption.lower()


def test_generated_caption_is_concrete_not_filler(demo_caption):
    """The register this codebase spent weeks eliminating."""
    banned = [
        "unlock", "elevate", "game-changer", "seamless", "cutting-edge",
        "leverage", "synergy", "supercharge", "in today's fast-paced",
        "revolutioni", "empower",
    ]
    hits = [b for b in banned if b in demo_caption.lower()]
    assert not hits, f"caption uses marketing filler: {hits}\n\n{demo_caption}"


def test_generated_caption_does_not_review_the_product(demo_caption):
    """A brand sells its product; it does not rate it."""
    reviewer = ["our team tested", "we tested", "solid pick", "top pick", "our verdict"]
    hits = [p for p in reviewer if p in demo_caption.lower()]
    assert not hits, f"caption is in reviewer voice: {hits}\n\n{demo_caption}"


def test_generated_caption_does_not_narrate_camera_work(demo_caption):
    """A caption is not a shot list."""
    shot = ["pan to", "cut to", "zoom in", "the camera", "watch the"]
    hits = [p for p in shot if p in demo_caption.lower()]
    assert not hits, f"caption narrates the visual: {hits}\n\n{demo_caption}"


def test_generated_caption_is_specific_to_the_business(demo_caption):
    """If a competitor's name could be swapped in, it says nothing."""
    low = demo_caption.lower()
    specifics = ["steel", "gravel", "frame", "bristol", "bike", "measure", "six weeks"]
    assert any(s in low for s in specifics), (
        "caption mentions nothing specific to the business it was written for:\n\n"
        + demo_caption
    )


def test_generated_caption_is_short_enough_to_read(demo_caption):
    body = demo_caption.split("#")[0]
    words = len(body.split())
    assert words <= 130, f"caption is {words} words before hashtags — too long to scan"


def test_demo_endpoint_is_rate_limited(client):
    """Unauthenticated and it costs an AI call, so it must be capped."""
    r = client.post(
        "/api/public/demo-caption",
        json={"businessName": "Rate Limit Probe"},
        timeout=httpx.Timeout(180.0),
    )
    assert r.status_code in (200, 429, 503), f"unexpected {r.status_code}"
    if r.status_code == 200:
        assert "remaining" in r.json(), "no remaining-quota signal returned"


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


@pytest.mark.parametrize("method,path", RETIRED_ROUTES)
def test_unauthenticated_prompt_engine_is_gone(client, method, path):
    """The engine shipped at a bare /prompt prefix with no auth.

    Anyone could name any workspace in a header, burn paid LLM calls and write
    rows into another tenant's data.
    """
    r = client.request(method, path, json={})
    assert r.status_code == 404, (
        f"{method} {path} still routes ({r.status_code}) — the unauthenticated "
        "prompt engine is exposed"
    )


def test_prompt_engine_requires_a_session(client):
    """Even with a workspace header, no session means no generation."""
    r = client.post(
        "/api/v1/prompt/video",
        json={"business_profile_id": "probe", "intent": "probe"},
        headers={"X-Workspace-Id": "probe"},
    )
    assert r.status_code in (401, 403), (
        f"prompt generation returned {r.status_code} to an anonymous caller"
    )


def test_billing_endpoints_reject_anonymous_callers(client):
    """Entitlement must never be grantable without a session."""
    for path, payload in (
        ("/api/v1/billing/subscribe", {"planCode": "starter"}),
        ("/api/v1/billing/cancel", {}),
        ("/api/v1/billing/sync", {}),
    ):
        r = client.post(path, json=payload)
        assert r.status_code in (401, 403), (
            f"{path} returned {r.status_code} without a token"
        )


def test_paypal_webhook_rejects_unsigned_payloads(client):
    """Without signature verification anyone could grant themselves a plan."""
    r = client.post(
        "/api/v1/paypal/webhook",
        json={
            "event_type": "BILLING.SUBSCRIPTION.ACTIVATED",
            "resource": {"id": "I-FAKE", "custom_id": "attacker"},
        },
    )
    assert r.status_code in (400, 403), (
        f"unsigned webhook returned {r.status_code} — subscriptions could be forged"
    )


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
