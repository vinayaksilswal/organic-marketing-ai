"""The hook competes separately from the angle.

Hooks used to arrive bundled with their angle — one call produced both, and
whatever line came back was used. But they are different problems. The angle
is what the creative argues; the hook is the two seconds that decide whether
anybody hears the argument. A model asked for both at once spends its
attention on the angle.

What matters most here is that the arithmetic stays in code. A model asked to
rank its own hooks ranks the one it wrote first, and a model asked whether its
hook is short enough says yes.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

import services.creative_strategist as cs


PROFILE = SimpleNamespace(
    name="Organiflo", industry="SaaS", businessModel="B2B SaaS",
    targetAudience="founders who post inconsistently",
    description="Posts for you.", website="https://organiflo.com",
    toneOfVoice="direct",
)

ANGLE = {
    "angle": "Posting is a second job", "category": "pain",
    "pain": "it never ends", "promise": "it happens without you",
    "hook": "Posting every day is a full-time job. You already have one.",
}


def _reply(hooks):
    return json.dumps({"hooks": hooks})


def _patch_model(monkeypatch, payload):
    async def _fake(prompt, **kw):
        return payload

    monkeypatch.setattr("services.ai_service._call_openrouter", _fake)


# ---------------------------------------------------------------------------
# Scoring is ours, not the model's
# ---------------------------------------------------------------------------

def test_length_is_measured_not_rated():
    """A model asked whether its own hook is short says yes.

    Spoken aloud, twelve words is about two seconds, and two seconds is the
    entire budget. So the penalty is applied here on a word count.
    """
    perfect = {k: 10 for k in cs.HOOK_WEIGHTS}

    short = cs.score_hook("Your posts write themselves.", perfect)
    long = cs.score_hook(
        "Your posts will write themselves and publish themselves entirely "
        "automatically while you are asleep in bed",
        perfect,
    )

    assert short == 100.0
    assert long < short, "a hook far past two seconds scored the same as one that fits"


def test_an_empty_hook_scores_nothing():
    assert cs.score_hook("", {k: 10 for k in cs.HOOK_WEIGHTS}) == 0.0


def test_stop_power_outweighs_the_rest():
    """A hook nobody stops for has no other qualities worth measuring."""
    stopping = cs.score_hook("Six words that stop the scroll",
                             {"stop_power": 10, "specificity": 0, "relevance": 0,
                              "curiosity_gap": 0, "clarity": 0})
    tidy = cs.score_hook("Six words that stop the scroll",
                         {"stop_power": 0, "specificity": 10, "relevance": 10,
                          "curiosity_gap": 0, "clarity": 10})
    assert stopping > 0
    assert cs.HOOK_WEIGHTS["stop_power"] > max(
        v for k, v in cs.HOOK_WEIGHTS.items() if k != "stop_power"
    )


def test_scores_are_clamped_to_a_real_range():
    """The model returns 11, or -3, or "high". None of those may leak out."""
    for junk in ({"stop_power": 99}, {"stop_power": -50}, {"stop_power": "high"}, {}):
        score = cs.score_hook("A perfectly reasonable hook", junk)
        assert 0.0 <= score <= 100.0, f"{junk} produced {score}"


# ---------------------------------------------------------------------------
# The competition
# ---------------------------------------------------------------------------

def test_the_best_scoring_hook_wins(monkeypatch):
    _patch_model(monkeypatch, _reply([
        {"archetype": "question", "hook": "Why post at midnight?",
         "dimensions": {"stop_power": 4, "specificity": 4, "relevance": 4,
                        "curiosity_gap": 4, "clarity": 4}},
        {"archetype": "number", "hook": "Ten hours a week, unpaid.",
         "dimensions": {"stop_power": 10, "specificity": 10, "relevance": 10,
                        "curiosity_gap": 9, "clarity": 10}},
    ]))

    out = asyncio.run(cs.best_hook(PROFILE, None, ANGLE))

    assert out["hook"] == "Ten hours a week, unpaid."
    assert out["archetype"] == "number"
    assert out["score"] > 80


def test_the_angles_own_hook_competes_too(monkeypatch):
    """Discarding it unseen would be a downgrade dressed up as an extra stage."""
    _patch_model(monkeypatch, _reply([
        {"archetype": "question", "hook": "Hmm?",
         "dimensions": {k: 1 for k in cs.HOOK_WEIGHTS}},
    ]))

    out = asyncio.run(cs.best_hook(PROFILE, None, ANGLE))

    assert out["hook"] == ANGLE["hook"], "a weak generated hook beat the angle's own line"
    assert out["archetype"] == "from_angle"


def test_a_model_failure_keeps_the_angles_hook(monkeypatch):
    """The pipeline continues with what it already had. Never raises."""
    async def _boom(*a, **k):
        raise RuntimeError("upstream 429")

    monkeypatch.setattr("services.ai_service._call_openrouter", _boom)

    out = asyncio.run(cs.best_hook(PROFILE, None, ANGLE))
    assert out["hook"] == ANGLE["hook"]


def test_runners_up_are_returned(monkeypatch):
    """So somebody who dislikes the winner is not made to regenerate the
    entire creative to see a second option."""
    _patch_model(monkeypatch, _reply([
        {"archetype": a, "hook": f"Hook number {i}",
         "dimensions": {k: 10 - i for k in cs.HOOK_WEIGHTS}}
        for i, (a, _) in enumerate(cs.HOOK_ARCHETYPES)
    ]))

    out = asyncio.run(cs.best_hook(PROFILE, None, ANGLE))

    assert len(out["alternatives"]) == 3
    scores = [a["score"] for a in out["alternatives"]]
    assert scores == sorted(scores, reverse=True)
    assert all(a["score"] <= out["score"] for a in out["alternatives"])


def test_blank_hooks_from_the_model_are_dropped(monkeypatch):
    _patch_model(monkeypatch, _reply([
        {"archetype": "question", "hook": "   ", "dimensions": {k: 10 for k in cs.HOOK_WEIGHTS}},
        {"archetype": "number", "hook": "Ten hours, unpaid.",
         "dimensions": {k: 8 for k in cs.HOOK_WEIGHTS}},
    ]))

    out = asyncio.run(cs.best_hook(PROFILE, None, ANGLE))
    assert out["hook"] == "Ten hours, unpaid."


# ---------------------------------------------------------------------------
# The winner has to actually reach the creative
# ---------------------------------------------------------------------------

def test_the_winning_hook_reaches_the_concept(monkeypatch):
    """Otherwise the stage runs, scores, picks — and nothing downstream uses it."""
    seen = {}

    async def _fake(prompt, **kw):
        seen["prompt"] = prompt
        raise RuntimeError("stop here, the prompt is what matters")

    monkeypatch.setattr("services.ai_service._call_openrouter", _fake)

    concept = asyncio.run(
        cs.build_concept(PROFILE, None, ANGLE, "Ten hours a week, unpaid.")
    )

    assert "Ten hours a week, unpaid." in seen["prompt"], "the concept was written to the old hook"
    assert concept["hook"] == "Ten hours a week, unpaid."


def test_the_fallback_concept_opens_on_the_winner_too(monkeypatch):
    """A failed concept call must not silently revert to the rejected line.

    This is the subtle one: the fallback builds scene 1 around the hook, so
    without the override the creative opens on the losing line while
    concept["hook"] claims otherwise.
    """
    async def _boom(*a, **k):
        raise RuntimeError("down")

    monkeypatch.setattr("services.ai_service._call_openrouter", _boom)

    concept = asyncio.run(cs.build_concept(PROFILE, None, ANGLE, "Ten hours, unpaid."))

    assert concept["hook"] == "Ten hours, unpaid."
    scene_one = json.dumps(concept["scenes"][0])
    assert "Ten hours, unpaid." in scene_one, "scene 1 opened on the hook that lost"
    assert ANGLE["hook"] not in scene_one


def test_build_concept_still_works_without_a_hook_argument():
    """It stays callable on its own; the angle's line is the default."""
    import inspect

    sig = inspect.signature(cs.build_concept)
    assert sig.parameters["hook"].default is None


def test_the_campaign_runs_the_hook_stage():
    import inspect

    src = inspect.getsource(cs.create_campaign)
    assert "best_hook" in src, "the engine exists but the pipeline never calls it"
    assert src.index("best_hook") < src.index("build_concept"), (
        "the hook must be chosen before the scenes are written around it"
    )
