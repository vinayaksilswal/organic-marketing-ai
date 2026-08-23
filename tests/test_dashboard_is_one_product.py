"""The dashboard should read as one product, not eight.

Every tool had picked its own palette. Brand Video Studio and the Viral
Validator were orange, the scheduler mixed orange with blue, PostShip was
violet, and the Viral Validator's own form controls were black with white text
inside an otherwise white page. Nothing was broken, and the whole thing looked
like four applications sharing a sidebar.

Orange was never a design token. It existed only as loose hex literals in four
files, which is precisely why it drifted: there was nothing to drift from.
These tests keep the dashboard on the tokens in index.css.

Media thumbnails stay black on purpose -- a video letterboxes against black,
and that is not a palette choice.
"""

import pathlib

import pytest


ROOT = pathlib.Path(__file__).resolve().parent.parent / "frontend" / "src"
DASHBOARD = sorted((ROOT / "pages" / "dashboard").glob("*.jsx"))
SHARED = [
    ROOT / "components" / "ViralValidator.jsx",
    ROOT / "components" / "PostShipStudio.jsx",
]

# The off-system accents. Each was a one-tool invention.
STRAY_COLOURS = [
    "#f97316", "#ea580c", "#fb923c",   # orange
    "249, 115, 22", "249,115,22",      # its tints
    "234, 88, 12", "234,88,12",
]


def test_the_files_were_actually_found():
    """Guards everything below: an empty glob passes every parametrised test."""
    assert len(DASHBOARD) >= 8, f"only found {len(DASHBOARD)} dashboard pages"
    for f in SHARED:
        assert f.exists(), f"{f.name} moved"


@pytest.mark.parametrize("page", DASHBOARD, ids=lambda p: p.name)
def test_no_page_invents_its_own_accent(page):
    src = page.read_text(encoding="utf-8")
    found = [c for c in STRAY_COLOURS if c in src]
    assert not found, (
        f"{page.name} uses off-system colour(s) {found}. The dashboard's "
        f"accents are var(--primary-color) and var(--secondary-color)."
    )


@pytest.mark.parametrize("page", DASHBOARD, ids=lambda p: p.name)
def test_no_page_hardcodes_the_brand_blue(page):
    """#3b82f6 and #2563eb are var(--secondary-color). Spelling them out is
    how one page ends up a different blue from the next."""
    src = page.read_text(encoding="utf-8")
    for literal in ("#3b82f6", "#2563eb"):
        assert literal not in src, f"{page.name} hardcodes {literal}"


def test_form_controls_are_not_dark_in_a_light_product():
    """A black select with white text inside a white card is the single most
    obvious sign of two designs in one screen."""
    src = (ROOT / "components" / "ViralValidator.jsx").read_text(encoding="utf-8")
    for dark in ("#1c1c24", "#181820"):
        assert dark not in src, f"a dark form control is back ({dark})"


def test_media_thumbnails_may_still_be_black():
    """The counter-test. A rule that also forbids letterboxing would be worse
    than the problem: it would make every video preview grey."""
    src = (ROOT / "pages" / "dashboard" / "MediaCatalog.jsx").read_text(encoding="utf-8")
    assert "background: '#000'" in src, (
        "media previews lost their black backing; video now letterboxes grey"
    )


def test_no_off_token_orange_anywhere_in_the_frontend():
    """The last five lived in the landing section advertising a tool that is
    violet in the product — the page promised one colour and the app delivered
    another. Orange is now defined nowhere, which is the point: a colour with
    no token is a colour that drifts."""
    stray = []
    for f in sorted(ROOT.rglob("*.jsx")):
        src = f.read_text(encoding="utf-8")
        hits = [c for c in STRAY_COLOURS if c in src]
        if hits:
            stray.append(f"{f.relative_to(ROOT)}: {hits}")
    assert not stray, "off-token colour reintroduced:\n" + "\n".join(stray)


def test_the_landing_defines_the_token_it_uses():
    """var(--violet) is the landing's own token. If the definition is ever
    removed, every use of it silently falls back to an inherited colour rather
    than failing loudly."""
    src = (ROOT / "pages" / "Landing.jsx").read_text(encoding="utf-8")
    assert "--violet:" in src, "the landing uses var(--violet) without defining it"


# =============================================================================
# Width and legibility
# =============================================================================

def test_no_dashboard_panel_wears_the_login_card():
    """`.card` is the auth screen's login box: `max-width: 480px`. Three
    dashboard panels wore it, so the Video Studio form, the Viral Validator
    results and the PostShip composer each sat in a 480px column inside a
    1040px page with the rest of the screen empty."""
    css = (ROOT / "index.css").read_text(encoding="utf-8")
    assert ".card { padding: 3rem; width: 100%; max-width: 480px; }" in css, (
        "the login card changed shape; this test's premise needs rechecking"
    )
    for rel in ("components/PostShipStudio.jsx",
                "components/ViralValidator.jsx",
                "pages/dashboard/VideoStudio.jsx"):
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert 'className="card"' not in src, f"{rel} is capped at 480px again"


def test_no_page_is_narrower_than_its_neighbours_for_no_reason():
    """These three capped themselves below .container's own 1280, which is why
    they alone had a wide empty margin."""
    for rel in ("pages/dashboard/ViralValidatorPage.jsx",
                "pages/dashboard/VideoStudio.jsx",
                "pages/dashboard/AccountInsights.jsx"):
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert "maxWidth: 1080" not in src
        assert "maxWidth: 1040" not in src
        assert "maxWidth: 900" not in src


def test_no_white_text_survives_on_the_white_cards():
    """Left over from the dark theme. The Viral Validator's three value
    headings were white on a white card -- invisible, not merely low
    contrast -- and the Video Studio's active-business chip was a white smudge.
    """
    vv = (ROOT / "pages" / "dashboard" / "ViralValidatorPage.jsx").read_text(encoding="utf-8")
    assert "color: '#fff' }}>" not in vv, "a heading is white-on-white again"

    vs = (ROOT / "pages" / "dashboard" / "VideoStudio.jsx").read_text(encoding="utf-8")
    assert "background: 'rgba(255,255,255,0.06)'" not in vs


def test_the_reddit_preview_is_readable():
    """It was #12141a with var(--text-main) on top: near-black text on a
    near-black card. The post was there and could not be read."""
    src = (ROOT / "components" / "PostShipStudio.jsx").read_text(encoding="utf-8")
    assert "background: '#12141a'" not in src


def test_previews_do_not_invent_engagement():
    """These are previews of a post that has not been published. '310 likes'
    beneath one is a performance claim about something that does not exist,
    and it teaches the customer to disbelieve every other number here."""
    src = (ROOT / "components" / "PostShipStudio.jsx").read_text(encoding="utf-8")
    assert "metrics_estimate" not in src, "invented engagement is back"
    for invented in ("'310'", "'21K'", "'248'", "'47'"):
        assert invented not in src, f"a fabricated count survived: {invented}"


def test_previews_state_the_real_platform_limits_instead():
    """What replaced it has to be true and checkable, or the section is just
    emptier rather than better."""
    src = (ROOT / "components" / "PostShipStudio.jsx").read_text(encoding="utf-8")
    assert "/ 280 characters" in src, "X's real limit is not shown"
    assert "see more" in src, "LinkedIn's truncation point is not shown"
    assert "/ 300" in src, "Reddit's title limit is not shown"


def test_the_postship_previews_survive_an_empty_start():
    """The composer starts empty on purpose, so `bundle` is null until
    something is generated. The workspace-sync effect spread `...prev.x_post`
    unconditionally and threw "Cannot read properties of null" during render,
    white-screening the whole PostShip page in production.

    Any updater that reaches into `prev` has to tolerate there being no
    bundle yet.
    """
    src = (ROOT / "components" / "PostShipStudio.jsx").read_text(encoding="utf-8")

    assert "useState(null)" in src, "the composer no longer starts empty"

    # Every `...prev.<field>` must sit behind a null check on prev.
    if "...prev." in src:
        assert "if (!prev) return prev;" in src, (
            "an updater reaches into prev with no guard; null bundle will crash "
            "the page on first render"
        )
