"""Understand the business once, and keep understanding it the same way.

The bug this replaces was not a crash — the old path worked. It re-derived the
whole profile per prompt and threw it away, so the system had no stable view of
what a business was. These tests are about that stability.
"""

from datetime import datetime, timedelta, timezone

import pytest

from database import BusinessProfile
from services.brand_intelligence import (
    STALE_AFTER,
    _fingerprint,
    get_or_build,
    is_stale,
    substantiation_source,
    to_scene_context,
)

INTEL = {
    "product_intelligence": {
        "value_proposition": "Scans certificates for quantum-vulnerable encryption.",
        "key_features": ["CBOM export", "CI integration", "FIPS 205 checks", "extra"],
        "primary_pain_point_solved": "nobody knows which keys break first",
        "transformation_statement": "Before: guessing -> After: a ranked list",
        "product_type": "digital_saas",
        "data_confidence": "high",
    },
    "audience_intelligence": {
        "objection_to_overcome": "needs proof before showing the board",
        "aesthetic_preference": "clinical and precise",
    },
    "visual_identity": {
        "visual_tone": "dark_technical",
        "competitor_visual_world": "glowing padlocks over binary rain",
    },
    "creative_strategy": {"hero_marketing_hook": "your keys expire in four years"},
    "industry_visual_language": {
        "vertical": "enterprise_saas",
        "lighting_signature": "cold institutional",
    },
}


def _profile(**over):
    fields = dict(
        id="ws1", userId="u1", name="quantcai",
        description="post-quantum readiness scanning",
        websiteUrl="https://quantcai.example", industry="security",
        targetAudience="security leads", primaryOffer="Run a free scan",
    )
    fields.update(over)
    return BusinessProfile(**fields)


# ── staleness ────────────────────────────────────────────────────────────────

def test_never_built_is_stale():
    stale, reason = is_stale(_profile())
    assert stale and "never" in reason


def test_freshly_built_is_current():
    p = _profile()
    p.brandIntelligence = dict(INTEL, _fingerprint=_fingerprint(p))
    p.brandIntelligenceAt = datetime.now(timezone.utc)
    stale, reason = is_stale(p)
    assert not stale and reason == "current"


def test_changed_description_invalidates_it():
    """The understanding described a different business than the one now stored."""
    p = _profile()
    p.brandIntelligence = dict(INTEL, _fingerprint=_fingerprint(p))
    p.brandIntelligenceAt = datetime.now(timezone.utc)

    p.description = "we now sell artisanal sourdough"
    stale, reason = is_stale(p)
    assert stale and "changed" in reason


def test_cosmetic_change_does_not_invalidate_it():
    """A new logo is not a repositioning; rebuilding on it wastes three calls."""
    p = _profile()
    p.brandIntelligence = dict(INTEL, _fingerprint=_fingerprint(p))
    p.brandIntelligenceAt = datetime.now(timezone.utc)

    p.logoUrl = "https://cdn/new-logo.png"
    p.postIntervalHours = 6
    assert is_stale(p)[0] is False


def test_expires_after_the_window():
    p = _profile()
    p.brandIntelligence = dict(INTEL, _fingerprint=_fingerprint(p))
    p.brandIntelligenceAt = datetime.now(timezone.utc) - STALE_AFTER - timedelta(days=1)
    stale, reason = is_stale(p)
    assert stale and "older than" in reason


def test_naive_timestamp_does_not_crash():
    """Postgres returns tz-aware, SQLite does not."""
    p = _profile()
    p.brandIntelligence = dict(INTEL, _fingerprint=_fingerprint(p))
    p.brandIntelligenceAt = datetime.now()  # naive
    assert is_stale(p)[0] is False


# ── flattening ───────────────────────────────────────────────────────────────

def test_scene_context_pulls_the_fields_that_change_output():
    ctx = to_scene_context(INTEL)
    assert "quantum-vulnerable" in ctx["what_it_does"].lower()
    assert "CBOM export" in ctx["what_it_does"]
    assert ctx["audience_motivator"] == "needs proof before showing the board"
    assert ctx["transformation"].startswith("Before:")
    assert "padlocks" in ctx["avoid_visual_world"]


def test_scene_context_prefers_motivator_over_demographic():
    """Naming the segment makes the model write to the label. The objection is
    the barrier, which is what Meta's guidance and the caption gate both want."""
    ctx = to_scene_context(INTEL)
    assert "security leads" not in ctx["audience_motivator"]


def test_scene_context_survives_a_partial_profile():
    ctx = to_scene_context({"product_intelligence": {"product_category": "a CRM"}})
    assert ctx["what_it_does"] == "a CRM"
    assert ctx["audience_motivator"] == ""


@pytest.mark.parametrize("bad", [None, {}, "not a dict", []])
def test_scene_context_handles_junk(bad):
    assert to_scene_context(bad) == {} or isinstance(to_scene_context(bad), dict)


# ── claim substantiation ─────────────────────────────────────────────────────

def test_substantiation_includes_what_the_website_said():
    """A figure really published by the business must be usable on screen."""
    intel = {"product_intelligence": {"value_proposition": "Trusted by 400 teams."}}
    src = substantiation_source(intel, _profile())
    assert "400" in src


def test_substantiation_without_intelligence_still_uses_the_profile():
    src = substantiation_source(None, _profile())
    assert "quantcai" in src.lower()


def test_invented_figure_is_blocked_by_the_gate():
    from prompt_engine.validator import check_rendered_claims
    src = substantiation_source(INTEL, _profile())
    ok, msg = check_rendered_claims('the banner reads "47 Keys Exposed"', src)
    assert ok is False and "47" in msg


def test_real_figure_passes_the_gate():
    from prompt_engine.validator import check_rendered_claims
    intel = {"product_intelligence": {"value_proposition": "Plans start at $27 a month."}}
    src = substantiation_source(intel, _profile())
    ok, _ = check_rendered_claims('the card reads "$27 Pro Tier"', src)
    assert ok is True


# ── build and reuse ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_or_build_reuses_instead_of_rebuilding(db_session, monkeypatch):
    """The whole point: a second prompt must not re-scrape and re-synthesise."""
    p = _profile()
    p.brandIntelligence = dict(INTEL, _fingerprint=_fingerprint(p))
    p.brandIntelligenceAt = datetime.now(timezone.utc)
    db_session.add(p)
    await db_session.commit()

    calls = []

    async def _never(*a, **k):
        calls.append(1)
        return INTEL

    monkeypatch.setattr("services.brand_intelligence.build", _never)

    intel, built = await get_or_build(db_session, p)
    assert built is False and not calls
    assert intel["product_intelligence"]["product_type"] == "digital_saas"


@pytest.mark.asyncio
async def test_get_or_build_persists_a_new_build(db_session, monkeypatch):
    p = _profile()
    db_session.add(p)
    await db_session.commit()

    async def _build(profile, image_url=""):
        return dict(INTEL, _fingerprint=_fingerprint(profile))

    monkeypatch.setattr("services.brand_intelligence.build", _build)

    intel, built = await get_or_build(db_session, p)
    assert built is True and intel is not None

    stored = await db_session.get(BusinessProfile, "ws1")
    assert stored.brandIntelligence is not None
    assert stored.brandIntelligenceAt is not None
    assert is_stale(stored)[0] is False


@pytest.mark.asyncio
async def test_failed_rebuild_keeps_the_previous_understanding(db_session, monkeypatch):
    """A provider outage must degrade to stale understanding, not to none —
    losing it drops generation back to the generic template."""
    p = _profile()
    p.brandIntelligence = dict(INTEL, _fingerprint="stale-fingerprint")
    p.brandIntelligenceAt = datetime.now(timezone.utc)
    db_session.add(p)
    await db_session.commit()

    async def _fail(profile, image_url=""):
        return None

    monkeypatch.setattr("services.brand_intelligence.build", _fail)

    intel, built = await get_or_build(db_session, p)
    assert built is False
    assert intel is not None and "product_intelligence" in intel


@pytest.mark.asyncio
async def test_failed_first_build_returns_none_rather_than_junk(db_session, monkeypatch):
    p = _profile()
    db_session.add(p)
    await db_session.commit()

    async def _fail(profile, image_url=""):
        return None

    monkeypatch.setattr("services.brand_intelligence.build", _fail)
    intel, built = await get_or_build(db_session, p)
    assert intel is None and built is False
