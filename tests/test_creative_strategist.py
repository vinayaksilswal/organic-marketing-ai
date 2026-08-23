"""The creative pipeline: angles, concepts, and an output shape that holds.

Asking one prompt for "a video prompt" gives a generic video prompt, because
the model has to invent a strategy and execute it in one breath. This walks it
through stages, and these tests are mostly about the two properties that make
that worth doing:

1. The output format is produced in code, so it is byte-identical for every
   business on every run — including runs where the model returned three
   scenes, six scenes, prose instead of JSON, or nothing at all. Telling a
   model "do not change the headings" does not survive a rate-limited free
   tier; not letting it write the headings does.

2. The ranking is arithmetic we do, not a number the model reports. Left to
   itself a model justifies whichever angle it wrote first.
"""

import pytest

from services import creative_strategist as cs


class P:
    name = "Organiflo"
    websiteUrl = "https://organiflo.com"
    businessModel = "SaaS"
    industry = "Marketing software"
    niche = ""
    description = "An automated organic marketing workspace for small businesses."
    targetAudience = "Small business owners who post when they remember"
    toneOfVoice = "direct, concrete"
    primaryOffer = ""


# =============================================================================
# The output shape
# =============================================================================

def test_the_format_is_identical_even_when_the_model_returns_nothing():
    """The whole point of rendering in code. An empty concept still produces
    the full structure rather than a broken half of one."""
    out = cs.render_creative({}, "Organiflo")

    for heading in ("## ", "**Format:**", "**Video generation prompt:**",
                    "**Style:**", "**Audio:**", "**Final CTA:**"):
        assert heading in out, f"missing {heading}"
    for i in range(1, 5):
        assert f"### Scene {i} —" in out


@pytest.mark.parametrize("scene_count", [0, 1, 3, 4, 7])
def test_there_are_always_exactly_four_scenes(scene_count):
    """Models return three or six constantly. Four is the format."""
    concept = {"scenes": [{"visuals": f"s{i}"} for i in range(scene_count)]}
    out = cs.render_creative(concept, "Organiflo")
    assert out.count("### Scene ") == 4
    assert "### Scene 5" not in out


def test_every_scene_carries_all_four_fields():
    out = cs.render_creative({"scenes": [{}]}, "Organiflo")
    for field in ("**Visuals:**", "**On-screen text:**", "**Script / Dialogue:**", "**Camera:**"):
        assert out.count(field) == 4, f"{field} is not on every scene"


def test_the_business_is_named_in_the_prompt_line():
    out = cs.render_creative({}, "Bright Smile Dental")
    assert "vertical Instagram Reel for Bright Smile Dental." in out


def test_the_model_supplied_words_survive_intact():
    """The shape is ours; the content is the model's. Losing its words would
    make the whole pipeline pointless."""
    concept = {
        "title": "I Asked AI To Run My Social Media",
        "scenes": [{"time": "0–2 sec", "visuals": "Close on a founder mid-sigh",
                    "on_screen_text": "I asked AI to run it", "script": "Watch this",
                    "camera": "handheld, eye level"}],
        "style": "raw UGC", "audio": "one beat", "cta": "Start free",
    }
    out = cs.render_creative(concept, "Organiflo")
    for fragment in ("I Asked AI To Run My Social Media", "Close on a founder mid-sigh",
                     "I asked AI to run it", "Watch this", "handheld, eye level",
                     "raw UGC", "one beat", "Start free"):
        assert fragment in out


# =============================================================================
# Ranking is ours
# =============================================================================

def test_a_strong_angle_outranks_a_weak_one():
    strong = cs.score_angle({k: 9 for k in cs.WEIGHTS})
    weak = cs.score_angle({k: 2 for k in cs.WEIGHTS})
    assert strong > weak


def test_the_score_cannot_be_inflated_past_the_scale():
    """A model that returns 500 for every dimension must not win by cheating."""
    absurd = cs.score_angle({k: 500 for k in cs.WEIGHTS})
    honest = cs.score_angle({k: 10 for k in cs.WEIGHTS})
    assert absurd == honest == pytest.approx(cs.MAX_SCORE)


def test_missing_or_junk_dimensions_score_zero_rather_than_crashing():
    assert cs.score_angle({}) == 0.0
    assert cs.score_angle({"hook_strength": "very good"}) == 0.0
    assert cs.score_angle({"hook_strength": None}) == 0.0


def test_hook_and_conversion_carry_the_most_weight():
    """A creative nobody watches converts nobody; one everybody watches that
    sells nothing is a hobby."""
    assert cs.WEIGHTS["hook_strength"] >= max(cs.WEIGHTS.values())
    assert cs.WEIGHTS["conversion_potential"] >= cs.WEIGHTS["shareability"]


# =============================================================================
# Layer 3 — the grammar changes, the structure does not
# =============================================================================

@pytest.mark.parametrize("model,expected", [
    ("SaaS", "saas"),
    ("E-commerce store", "ecommerce"),
    ("Restaurant", "restaurant"),
    ("Dental clinic", "local_service"),
    ("Creator", "creator"),
    ("Something unusual", "general"),
])
def test_a_business_is_shot_the_way_its_kind_is_shot(model, expected):
    class B(P):
        businessModel = model
        industry = model
        description = model
    assert cs.classify(B) == expected


def test_every_grammar_has_beats_and_a_camera_language():
    for kind, grammar in cs.GRAMMAR.items():
        assert grammar["beats"], kind
        assert grammar["camera"], kind
        assert grammar["format"], kind


def test_a_restaurant_and_a_saas_do_not_get_the_same_beats():
    assert cs.GRAMMAR["restaurant"]["beats"] != cs.GRAMMAR["saas"]["beats"]


# =============================================================================
# The stages, with the model stubbed
# =============================================================================

@pytest.fixture
def model(monkeypatch):
    def _set(reply):
        async def fake(*a, **kw):
            if callable(reply):
                return reply()
            return reply
        import services.ai_service as ai
        monkeypatch.setattr(ai, "_call_openrouter", fake)
    return _set


ANGLES_JSON = """[
 {"category":"curiosity","angle":"I asked AI to run it","hook":"I asked AI to handle my social media",
  "pain":"blank calendar","promise":"time back",
  "dimensions":{"hook_strength":9,"customer_relevance":9,"product_relevance":8,
   "visual_potential":8,"curiosity":10,"shareability":8,"conversion_potential":9,"instagram_fit":10}},
 {"category":"pain","angle":"Hours lost","hook":"Still spending your evening on captions?",
  "pain":"time","promise":"consistency",
  "dimensions":{"hook_strength":7,"customer_relevance":9,"product_relevance":8,
   "visual_potential":7,"curiosity":5,"shareability":5,"conversion_potential":8,"instagram_fit":8}},
 {"category":"curiosity","angle":"A second curiosity one","hook":"Another curiosity hook",
  "pain":"x","promise":"y",
  "dimensions":{"hook_strength":6,"customer_relevance":6,"product_relevance":6,
   "visual_potential":6,"curiosity":6,"shareability":6,"conversion_potential":6,"instagram_fit":6}}
]"""


@pytest.mark.asyncio
async def test_angles_come_back_ranked(model):
    model(ANGLES_JSON)
    out = await cs.propose_angles(P, None, wanted=2)
    assert out[0]["score"] >= out[1]["score"]
    assert out[0]["category"] == "curiosity"


@pytest.mark.asyncio
async def test_five_creatives_do_not_all_use_the_same_trigger(model):
    """Five rewordings of the strongest angle is one creative, not five."""
    model(ANGLES_JSON)
    out = await cs.propose_angles(P, None, wanted=2)
    assert len({a["category"] for a in out}) == 2


@pytest.mark.asyncio
async def test_a_dead_model_still_produces_usable_angles(model):
    def boom():
        raise RuntimeError("429 everywhere")
    model(boom)
    out = await cs.propose_angles(P, None, wanted=3)
    assert len(out) == 3
    assert all(a["hook"] for a in out)


@pytest.mark.asyncio
async def test_junk_from_the_model_falls_back_rather_than_returning_nothing(model):
    model("I'm sorry, I can't help with that.")
    out = await cs.propose_angles(P, None, wanted=3)
    assert len(out) == 3


@pytest.mark.asyncio
async def test_a_concept_always_renders_the_full_format(model):
    model('{"title":"T","scenes":[{"visuals":"only one scene"}],"cta":"Go"}')
    concept = await cs.build_concept(P, None, {"category": "pain", "hook": "h", "score": 5})
    assert concept["markdown"].count("### Scene ") == 4
    assert "only one scene" in concept["markdown"]


@pytest.mark.asyncio
async def test_a_concept_survives_a_model_that_returns_prose(model):
    model("Here is a great idea for a reel! It should be fun and engaging.")
    concept = await cs.build_concept(P, None, {"category": "pain", "hook": "h", "score": 5})
    assert concept["markdown"].count("### Scene ") == 4
    assert "**Final CTA:**" in concept["markdown"]


@pytest.mark.asyncio
async def test_the_chosen_angle_is_reported_back(model):
    """The customer sees which angle was chosen, not the reasoning behind it."""
    model('{"title":"T","scenes":[{}],"cta":"Go"}')
    concept = await cs.build_concept(P, None, {"category": "fomo", "hook": "h", "score": 7})
    assert concept["creative_angle"] == "fomo"
    assert concept["hook"] == "h"


# =============================================================================
# The line this product does not cross
# =============================================================================

def test_the_model_is_told_not_to_invent_claims():
    assert "never invent" in cs._STRATEGIST.lower()
    assert "testimonials" in cs._STRATEGIST.lower()


def test_the_scene_brief_forbids_invented_figures():
    import inspect
    src = inspect.getsource(cs.build_concept)
    assert "Invent no statistics" in src


def test_the_score_is_not_presented_as_a_forecast():
    """An internal ranking heuristic. Showing it as "87% conversion
    probability" on an unpublished creative is precisely the invented figure
    the caption gates exist to prevent."""
    import inspect
    doc = inspect.getdoc(cs) or ""
    assert "never shown to the customer as a prediction" in doc


def test_a_wrapped_reply_is_not_thrown_away():
    """A bare array is requested. What arrives is regularly {"angles": [...]}.
    Demanding the exact shape discarded good angles and silently used canned
    seeds — the stage that makes this pipeline worth having never ran."""
    wrapped = {"angles": [{"hook": "h", "category": "pain", "dimensions": {}}]}
    assert len(cs._as_list(wrapped)) == 1


def test_a_single_object_reply_is_not_thrown_away():
    """This tier returns one angle however many are asked for."""
    single = {"hook": "h", "angle": "a", "category": "curiosity", "dimensions": {}}
    assert len(cs._as_list(single)) == 1


def test_junk_yields_nothing_rather_than_a_bogus_angle():
    assert cs._as_list("not json") == []
    assert cs._as_list({"unrelated": "value"}) == []
    assert cs._as_list(None) == []


@pytest.mark.asyncio
async def test_one_real_angle_is_kept_and_the_rest_topped_up(model):
    """Degrade by degrees, not by cliff. Throwing away the one good angle to
    use five canned ones is the worst of both."""
    model('{"category":"pain","angle":"a","hook":"a real hook",'
          '"dimensions":{"hook_strength":9,"conversion_potential":9}}')

    out = await cs.propose_angles(P, None, wanted=4)
    assert len(out) == 4
    assert out[0]["hook"] == "a real hook"
    assert out[0]["score"] > 0
    assert sum(1 for a in out if a["score"] == 0) == 3   # the top-ups
    assert len({a["category"] for a in out}) == 4        # still all different


# =============================================================================
# The critic
# =============================================================================

def test_a_creative_with_no_hook_is_caught():
    problems = cs.audit({"scenes": [{}, {}, {}, {}], "cta": ""})
    assert any("hook" in p.lower() for p in problems)


def test_an_opening_line_too_long_to_land_is_caught():
    """Two seconds is roughly ten words spoken. Fifteen is a hook nobody
    reaches the end of before the thumb moves."""
    long_hook = " ".join(["word"] * 20)
    problems = cs.audit({"scenes": [{"on_screen_text": long_hook, "visuals": "v"}],
                         "cta": "Go"})
    assert any("too long" in p.lower() for p in problems)


def test_a_silent_creative_is_caught():
    """Most of Instagram watches muted. No on-screen text anywhere means the
    story does not exist for most viewers."""
    problems = cs.audit({"scenes": [{"visuals": "v", "script": "spoken only"}],
                         "cta": "Go"})
    assert any("muted" in p.lower() for p in problems)


def test_a_missing_cta_is_caught():
    assert any("call to action" in p.lower()
               for p in cs.audit({"scenes": [{"on_screen_text": "hi", "visuals": "v"}]}))


def test_scenes_with_no_visual_direction_are_named():
    problems = cs.audit({
        "scenes": [{"on_screen_text": "hi", "visuals": "v"}, {}, {"visuals": "v"}, {}],
        "cta": "Go",
    })
    assert any("2, 4" in p for p in problems), problems


def test_a_sound_creative_reports_nothing():
    """A critic that always complains is a critic nobody reads."""
    good = {
        "scenes": [
            {"on_screen_text": "When did you last post?", "visuals": "a"},
            {"on_screen_text": "x", "visuals": "b"},
            {"visuals": "c"}, {"visuals": "d"},
        ],
        "cta": "Start free",
    }
    assert cs.audit(good) == []


@pytest.mark.asyncio
async def test_the_structural_audit_still_runs_when_the_model_is_dead(model):
    """The checkable failures are checked in code, so a rate-limited tier
    costs the second opinion rather than the whole review."""
    def boom():
        raise RuntimeError("429")
    model(boom)

    out = await cs.critique({"scenes": [{}, {}, {}, {}], "cta": ""}, "Organiflo")
    assert out["problems"], "the audit did not run without the model"


@pytest.mark.asyncio
async def test_the_model_can_add_to_the_findings(model):
    model('{"problems": ["The product never appears on screen."]}')
    out = await cs.critique({"scenes": [{"on_screen_text": "hi", "visuals": "v"}],
                             "cta": "Go"}, "Organiflo")
    assert any("never appears" in p for p in out["problems"])


# =============================================================================
# Two configuration bugs that read as "the model is too weak"
# =============================================================================

def test_a_token_ceiling_is_set_explicitly():
    """With none set the provider applies its own, and on the free tier that
    default starves a reasoning model: it spends the budget thinking and
    returns finish_reason None with an empty body. Measured — at 900 the
    request comes back empty, at 2000 the same one completes with room."""
    from services import ai_service

    assert ai_service.DEFAULT_MAX_TOKENS >= 2000, (
        "below this a reasoning model returns nothing and it looks like a "
        "weak model rather than a starved one"
    )

    import inspect
    src = inspect.getsource(ai_service._call_openrouter_once)
    assert '"max_tokens"' in src


def test_the_json_shape_asked_for_matches_the_shape_enforced():
    """json_response sets response_format to json_object, which requires the
    reply to BE an object. Asking for a bare array inside that constraint is a
    contradiction, and the model resolves it by returning a single object —
    which is exactly what it did, so the angle stage silently used seeds."""
    import inspect

    src = inspect.getsource(cs.propose_angles)
    assert '"angles"' in src, "the prompt no longer asks for the wrapper object"
    assert "Return ONLY a JSON array" not in src, (
        "asking for a bare array under json_object mode returns one object"
    )


def test_the_angle_request_is_sized_to_the_budget():
    """Fifteen angles with eight dimensions overflows the reply and comes back
    empty. That looked like model weakness and was an oversized request."""
    import inspect

    src = inspect.getsource(cs.propose_angles)
    assert "max(12, wanted * 3)" not in src
    assert "wanted + 3" in src
