"""A feature nobody can open is not a feature.

This has been the recurring failure in this codebase: keyframes generated and
dropped, insights read and discarded, X and LinkedIn able to publish with no
way to store a token, columns written that nothing ever displayed.

Faceless Shorts was the largest instance. The service, its presets, its quota
metering and its own test file all existed, the landing page sold it by name,
Workspaces offered "Faceless Channel" as a business model with dedicated
settings — and no line of the interface ever called the endpoints. Somebody
could pick it as their business model and find nothing to press.

test_frontend_calls_real_routes.py checks the other direction: that the
interface only calls endpoints that exist. This checks that endpoints a
customer is sold can be reached from the interface.
"""

import json
import pathlib

import pytest


ROOT = pathlib.Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend" / "src"


def _all_frontend_source() -> str:
    parts = []
    for pattern in ("*.jsx", "*.js"):
        for f in FRONTEND.rglob(pattern):
            parts.append(f.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(parts)


SOURCE = _all_frontend_source()


def test_the_frontend_was_actually_read():
    """Without this, an empty read makes every assertion below vacuous."""
    assert len(SOURCE) > 100_000, f"only read {len(SOURCE)} characters"
    assert "authFetch" in SOURCE


# Endpoints a customer is sold, and the interface that has to reach them.
# Deliberately not every route: OAuth callbacks are called by the provider,
# and admin tools are not customer features.
SOLD_FEATURES = [
    ("creatives/faceless-generate", "Faceless Shorts"),
    ("creatives/faceless-presets", "Faceless Shorts presets"),
    ("creatives/faceless-autopilot", "Faceless Auto-Pilot"),
    ("creatives/proven-offers", "Proven Meta Ad Angles"),
    ("marketing/account-insights", "Account Insights"),
    ("marketing/leads", "Leads"),
    ("creatives/postship-generate", "PostShip"),
    ("creatives/analyze-algorithm", "Viral Validator"),
    ("marketing/posts/schedule-recurring", "Repeating posts"),
]


@pytest.mark.parametrize("path,feature", SOLD_FEATURES, ids=[f for _, f in SOLD_FEATURES])
def test_a_sold_feature_can_be_reached_from_the_interface(path, feature):
    assert path in SOURCE, (
        f"{feature} is built and billed for, and nothing in the interface calls "
        f"{path}. A customer cannot use it."
    )


def test_the_landing_page_does_not_sell_what_the_product_cannot_do():
    """The landing page names Faceless Shorts in its own showcase section. If
    the page sells it, the dashboard has to have it — that is the difference
    between marketing and a false claim on a page taking paid traffic."""
    landing = (FRONTEND / "pages" / "Landing.jsx").read_text(encoding="utf-8")
    if "Faceless Short Videos" in landing:
        assert "faceless-generate" in SOURCE, (
            "the landing page advertises Faceless Shorts and the dashboard "
            "cannot generate one"
        )


def test_every_dashboard_page_has_a_route_and_a_way_in():
    """A page with a route but no link is reachable only by typing the URL."""
    layout = (FRONTEND / "pages" / "DashboardLayout.jsx").read_text(encoding="utf-8")
    sidebar = (FRONTEND / "components" / "Sidebar.jsx").read_text(encoding="utf-8")

    unreachable = []
    for page in sorted((FRONTEND / "pages" / "dashboard").glob("*.jsx")):
        name = page.stem
        if name not in layout:
            continue  # not routed at all; that is a different problem
        # Derive the route path from the layout and check something links to it.
        import re
        m = re.search(rf'path="(/[^"]+)"[^>]*element=\{{<{name}\b', layout)
        if not m:
            continue
        route = m.group(1)
        if route not in sidebar and route not in SOURCE.replace(layout, ""):
            unreachable.append(f"{name} ({route})")

    assert not unreachable, (
        "routed but nothing links to them:\n  " + "\n  ".join(unreachable)
    )


def test_the_campaign_builder_can_be_reached():
    """The strategist pipeline is the most expensive thing in this codebase to
    build and the easiest to leave unreachable — a strategist nobody can run
    is worth nothing."""
    assert "creatives/strategist-campaign" in SOURCE


# ---------------------------------------------------------------------------
# Bring-your-own rendering account
#
# The schema for this shipped long before anything could set it: VideoApiConfig
# was read at render time and there was no way for a customer to fill it in.
# These pin the whole path — endpoints exist, the interface calls them, and the
# button sits on the pages that need it.
# ---------------------------------------------------------------------------

def test_the_media_provider_endpoints_exist():
    from routers.creative_api import router

    paths = {r.path for r in router.routes}
    assert "/api/v1/creatives/media-providers" in paths
    assert "/api/v1/creatives/media-providers/{kind}" in paths


def test_the_interface_calls_the_media_provider_endpoints():
    assert "creatives/media-providers" in SOURCE, (
        "the endpoints exist but nothing in the interface calls them — "
        "that is the VideoApiConfig situation all over again"
    )


@pytest.mark.parametrize("page", [
    "pages/dashboard/VideoStudio.jsx",
    "pages/dashboard/FacelessStudio.jsx",
])
def test_the_connect_button_sits_on_the_prompt_generators(page):
    """Asked for explicitly: a connect button on every prompt generator."""
    text = (FRONTEND / page).read_text(encoding="utf-8")
    assert "MediaProviderConnect" in text, f"{page} generates prompts with no way to connect a renderer"


def test_the_api_key_never_comes_back_to_the_browser():
    """A key returned in a response ends up in logs, caches and error reports.

    Mutation-checked: removing the mask() call from connections() fails this.
    """
    import asyncio
    from types import SimpleNamespace
    from services import media_providers
    from services.crypto_service import encrypt_token

    secret = "r8_this_is_the_real_key_do_not_leak"

    class _Result:
        def scalars(self):
            return SimpleNamespace(all=lambda: [SimpleNamespace(
                kind="video", provider="runway", model="gen4_turbo",
                apiKey=encrypt_token(secret),
            )])

    class _Session:
        async def execute(self, *_a, **_k):
            return _Result()

    out = asyncio.run(media_providers.connections(_Session(), "u1", "w1"))

    assert out["video"]["connected"] is True
    assert secret not in json.dumps(out), "the plaintext key was returned to the caller"
    assert out["video"]["keyHint"] and len(out["video"]["keyHint"]) < len(secret)


def test_an_unsupported_provider_is_refused_before_it_is_stored():
    """Otherwise it saves, reports 'connected', and fails only at render time."""
    from services import media_providers

    assert media_providers.is_supported("video", "runway", "gen4_turbo") is None
    assert media_providers.is_supported("video", "not-a-provider", None)
    assert media_providers.is_supported("nonsense", "runway", None)
    assert media_providers.is_supported("video", "runway", "some-model-runway-lacks")
