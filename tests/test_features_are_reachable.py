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

    assert media_providers.is_supported("video", "replicate", "minimax/video-01") is None
    assert media_providers.is_supported("video", "not-a-provider", None)
    assert media_providers.is_supported("nonsense", "replicate", None)
    assert media_providers.is_supported("video", "replicate", "a-model-replicate-lacks")
    # Runway was offered until services/media_render.py made it clear nothing
    # could spend the key: its video endpoint takes an input image, not a
    # prompt. Offering it again would let somebody connect a dead credential.
    assert media_providers.is_supported("video", "runway", None)


# ---------------------------------------------------------------------------
# Disconnecting an account
#
# Meta had a disconnect button. X, LinkedIn and YouTube each had a working
# endpoint and nothing that called it, so an account linked here could only
# be revoked from the platform's own settings -- if the customer knew to look.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("platform", ["x", "linkedin", "youtube"])
def test_every_connectable_platform_can_also_be_disconnected(platform):
    assert f"{platform}/disconnect" in SOURCE or "disconnectPlatform" in SOURCE, (
        f"{platform} can be connected from the interface but never unlinked"
    )


def test_the_disconnect_button_uses_the_method_the_endpoint_accepts():
    """These three are POST. Meta's is DELETE. Calling the wrong one 405s."""
    import importlib

    src = (FRONTEND / "pages" / "dashboard" / "Workspaces.jsx").read_text(encoding="utf-8")
    block = src[src.index("const disconnectPlatform"):]
    block = block[: block.index("const handleConnectX")]
    assert "method: 'POST'" in block

    for mod in ("x_oauth", "linkedin_oauth", "youtube_oauth"):
        router = importlib.import_module(f"routers.{mod}").router
        route = next(r for r in router.routes if "disconnect" in r.path)
        assert "POST" in route.methods, f"{mod} disconnect is not POST"


@pytest.mark.parametrize("flag,platform", [
    ("hasTwitter", "X"), ("hasLinkedin", "LinkedIn"), ("hasYoutube", "YouTube"),
])
def test_a_connected_account_is_shown_as_connected(flag, platform):
    """All three panels used to render "Connect" forever, with no confirmation
    the link had worked and no hint that clicking again would redo it."""
    src = (FRONTEND / "pages" / "dashboard" / "Workspaces.jsx").read_text(encoding="utf-8")
    assert f"socialConnection?.{flag}" in src, f"{platform} never shows as connected"


def test_youtube_connection_state_is_actually_served():
    """The flag has to exist in the payload, or the panel reads undefined and
    shows a connected account as disconnected forever."""
    src = (ROOT / "routers" / "user_api.py").read_text(encoding="utf-8")
    assert src.count('"hasYoutube"') >= 2, "hasYoutube missing from one of the two payloads"
    # The refresh token is the durable one. An access token expires in an hour,
    # so keying off it would report a connection that dies the same morning.
    assert '"hasYoutube": bool(getattr(active_conn, "youtubeRefreshToken", None))' in src


# ---------------------------------------------------------------------------
# Post now
#
# /social/trigger runs one marketing loop on demand and nothing called it, so
# the only way to see the product work was to connect an account and wait for
# the next scheduled cycle -- four hours by default. That is the wrong first
# experience for somebody deciding whether to pay.
# ---------------------------------------------------------------------------

def test_a_posting_run_can_be_started_by_hand():
    assert "social/trigger" in SOURCE, (
        "the loop can only be triggered by waiting for the scheduler"
    )


def test_post_now_is_hidden_until_an_account_is_connected():
    """A loop with nowhere to post reports success and does nothing."""
    src = (FRONTEND / "pages" / "dashboard" / "Overview.jsx").read_text(encoding="utf-8")
    block = src[src.index("{live && ("):]
    block = block[: block.index("</button>")]
    assert "postNow" in block, "Post now is not behind the connected check"


def test_post_now_does_not_claim_the_post_went_out():
    """The loop runs in the background; there is nothing to report yet.

    Saying "posted" here would be the same lie the scheduler used to tell.
    """
    src = (FRONTEND / "pages" / "dashboard" / "Overview.jsx").read_text(encoding="utf-8")
    block = src[src.index("const postNow"):]
    block = block[: block.index("const load")]

    happy = [ln for ln in block.splitlines() if "showToast" in ln and "true)" not in ln]
    assert happy, "no success message found"
    for line in happy:
        low = line.lower()
        assert "posted to" not in low and "published" not in low, (
            f"claims a result the server has not produced yet: {line.strip()}"
        )


def test_the_old_video_config_endpoint_no_longer_returns_the_key():
    """It used to send `config.apiKey` straight to the browser.

    That is the customer's stored credential leaving the server on an endpoint
    that never needed it. Nothing called the endpoint, which is the only reason
    it was not an incident.
    """
    src = (ROOT / "routers" / "video.py").read_text(encoding="utf-8")
    block = src[src.index('@router.get("/config")'):]
    block = block[: block.index('@router.post("/config")')]

    # Comments in that block discuss the old field by name, so only real
    # code counts here -- otherwise the guard trips on its own explanation.
    code = " ".join(
        ln for ln in block.splitlines() if not ln.strip().startswith("#")
    )
    assert '"apiKey"' not in code, "the stored key is still being returned"
    assert "config.apiKey" not in code
    assert "keyHint" in code


def test_there_is_only_one_writer_to_the_media_provider_table():
    """Two writers is how an image key gets clobbered by a video save.

    routers/video.py predates services/media_providers.py and wrote the same
    table without setting `kind`, so its .first() could pick up -- and
    overwrite -- the row the newer connect UI had written.
    """
    src = (ROOT / "routers" / "video.py").read_text(encoding="utf-8")
    block = src[src.index('@router.post("/config")'):]
    block = block[: block.index('@router.post("/generate-prompt")')]

    assert "media_providers.save" in block, "video.py still writes the table itself"
    assert "VideoApiConfig(" not in block, "video.py still constructs rows directly"
    assert 'kind="video"' in block, "a row written without a kind collides with the image row"


def test_a_partial_failure_is_visible_not_just_a_total_one():
    """One workspace had Facebook rejecting every post for two weeks.

    The post reached Instagram, so its status was POSTED, so the green badge
    showed and the error was never rendered -- it was only rendered when
    status was FAILED. The only way to discover it was to read the database.
    """
    src = (FRONTEND / "pages" / "dashboard" / "Overview.jsx").read_text(encoding="utf-8")

    assert "const partial = ok && !!p.errorLog" in src, (
        "a post that succeeded on one platform and failed on another is still silent"
    )
    assert "(failed || partial) && p.errorLog" in src, (
        "the error block still only renders for a total failure"
    )


def test_the_recent_posts_payload_carries_the_error():
    """The interface cannot show what the server does not send."""
    src = (ROOT / "routers" / "api.py").read_text(encoding="utf-8")
    block = src[src.index('"/social/recent-posts"'):]
    block = block[: block.index("return")]
    assert '"errorLog"' in block


# ---------------------------------------------------------------------------
# The dashboard as one product
#
# The sidebar grouped Overview, Businesses, two studios, the validator,
# insights and the media library under a single heading called "Core
# Platform", which tells somebody arriving for the first time nothing about
# where to start. Grouped by intent now, in the order the work happens.
# ---------------------------------------------------------------------------

def _sidebar_code() -> str:
    """The sidebar with its JSX comments removed.

    The comments explain what the old labels were and why they changed, so a
    naive substring search finds "Core Platform" in the note saying it was
    removed. Only what actually renders counts.
    """
    import re

    src = (FRONTEND / "components" / "Sidebar.jsx").read_text(encoding="utf-8")
    return re.sub(r"\{/\*.*?\*/\}", "", src, flags=re.DOTALL)


def test_the_sidebar_is_grouped_by_what_a_person_is_doing():
    src = _sidebar_code()

    for heading in ("Create", "Publish", "Results", "Setup"):
        assert f">\n          {heading}\n        <" in src or f">{heading}<" in src, (
            f"the '{heading}' group is missing from the sidebar"
        )
    assert "Core Platform" not in src, "the old catch-all grouping is still there"


def test_navigation_labels_are_plain_words():
    """"PostShip Multi-Platform" with an "X·LI·RD" badge means nothing to
    somebody who has just signed up."""
    src = _sidebar_code()
    assert "Write a post" in src
    assert "PostShip Multi-Platform" not in src
    assert "X·LI·RD" not in src


def test_every_sidebar_link_points_at_a_real_route():
    """A nav item with no route is a dead end on the main navigation."""
    import re

    sidebar = (FRONTEND / "components" / "Sidebar.jsx").read_text(encoding="utf-8")
    layout = (FRONTEND / "pages" / "DashboardLayout.jsx").read_text(encoding="utf-8")

    dead = []
    for target in re.findall(r'NavLink to="(/dashboard[^"]*)"', sidebar):
        tail = target.replace("/dashboard", "") or "/"
        if f'path="{tail}"' not in layout:
            dead.append(target)

    assert not dead, "sidebar links with no route: " + ", ".join(dead)


# ---------------------------------------------------------------------------
# Getting to a first post
# ---------------------------------------------------------------------------

def test_the_onboarding_path_exists_and_is_ordered():
    src = (FRONTEND / "components" / "GetStarted.jsx").read_text(encoding="utf-8")

    for step in ("Add your business", "Connect a social account",
                 "Add something to post", "Choose your plan",
                 "Publish your first post"):
        assert step in src, f"the onboarding sequence is missing '{step}'"

    # The plan sits after setup and before the first post: asking on step one
    # is a closed tab, asking after the first post gives the product away.
    assert src.index("Choose your plan") < src.index("Publish your first post")
    assert src.index("Connect a social account") < src.index("Choose your plan")


def test_only_the_next_step_gets_a_button():
    """Five buttons at once is five decisions. One is a next action."""
    src = (FRONTEND / "components" / "GetStarted.jsx").read_text(encoding="utf-8")
    assert "const nextIndex = steps.findIndex((s) => !s.done)" in src
    assert "{isNext && (" in src


def test_the_checklist_disappears_when_setup_is_done():
    src = (FRONTEND / "components" / "GetStarted.jsx").read_text(encoding="utf-8")
    assert "if (doneCount === steps.length) return null;" in src


def test_overview_shows_the_checklist_instead_of_the_blocker_list():
    """Both at once would put two competing to-do lists at the top."""
    src = (FRONTEND / "pages" / "dashboard" / "Overview.jsx").read_text(encoding="utf-8")
    assert "<GetStarted" in src
    assert "setupDone && blockers.length > 0" in src


# ---------------------------------------------------------------------------
# Previews
# ---------------------------------------------------------------------------

def test_the_preview_knows_where_each_platform_cuts_the_caption():
    """The fold is the whole point: it decides whether the second sentence
    is ever read."""
    src = (FRONTEND / "components" / "PostPreview.jsx").read_text(encoding="utf-8")

    for platform in ("instagram", "facebook", "x", "linkedin", "youtube"):
        assert f"{platform}:" in src, f"no fold rule for {platform}"

    # X is a hard limit, not a fold — the post is refused, not collapsed.
    assert "at: 280" in src


def test_the_preview_warns_about_media_a_platform_cannot_accept():
    src = (FRONTEND / "components" / "PostPreview.jsx").read_text(encoding="utf-8")
    assert "Instagram cannot publish without" in src
    assert "YouTube needs a video" in src
    assert "over the 280 limit" in src


def test_the_preview_is_actually_used():
    assert "PostPreview" in SOURCE, "the component exists and no page renders it"


# ---------------------------------------------------------------------------
# The activity log
# ---------------------------------------------------------------------------

def test_the_activity_log_is_reachable():
    """/marketing/logs existed with nothing calling it."""
    assert "marketing/logs" in SOURCE, "the log endpoint still has no caller"

    layout = (FRONTEND / "pages" / "DashboardLayout.jsx").read_text(encoding="utf-8")
    assert 'path="/activity"' in layout

    sidebar = (FRONTEND / "components" / "Sidebar.jsx").read_text(encoding="utf-8")
    assert "/dashboard/activity" in sidebar, "routed but nothing links to it"


def test_the_log_merges_runs_and_posts():
    """A loop that ran and published nothing looks identical to a healthy one
    if you only read the run log."""
    src = (FRONTEND / "pages" / "dashboard" / "Activity.jsx").read_text(encoding="utf-8")
    assert "social/recent-posts" in src and "marketing/logs" in src
    assert "sort" in src, "two sources with independent clocks must be merged by time"


def test_the_log_distinguishes_a_partial_failure_from_a_success():
    src = (FRONTEND / "pages" / "dashboard" / "Activity.jsx").read_text(encoding="utf-8")
    assert "partial" in src
    assert "published && p.errorLog" in src
