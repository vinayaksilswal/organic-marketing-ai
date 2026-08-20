"""A model the provider is refusing gets benched, briefly.

The chain already falls through on a 429, so nothing breaks when the preferred
model is down. What it did not do was remember. Every request paid a full
failed round-trip to the same dead model before falling through, which with
the preferred model down is a fixed latency tax on every caption the product
writes -- measured at 3.5s versus 0.8s on the very next call.

Two properties matter more than the speed:

  A stale bench must never be the reason nothing gets written. If benching
  would empty the chain, the bench is ignored and everything is tried.

  Only capacity failures bench. A 400 or a 401 will fail identically on every
  model and benching them would hide a broken key behind a slow degrade.
"""

import time

import pytest

from services import ai_service as ai


@pytest.fixture(autouse=True)
def _clear_bench():
    ai._benched.clear()
    yield
    ai._benched.clear()


def test_a_benched_model_is_skipped():
    ai._bench("z-ai/glm-5.2:free")
    assert ai._is_benched("z-ai/glm-5.2:free")


def test_the_bench_expires_on_its_own():
    """A provider that has recovered must not stay benched for one bad minute."""
    ai._benched["m"] = time.time() - 1
    assert not ai._is_benched("m")
    assert "m" not in ai._benched, "an expired entry should be dropped, not kept"


def test_an_unbenched_model_is_never_skipped():
    assert not ai._is_benched("nvidia/nemotron-3-ultra-550b-a55b:free")


def test_the_bench_is_short():
    """Long enough to skip a dead provider, short enough that a recovery is
    picked up within one posting cycle."""
    assert 60 <= ai._BENCH_SECONDS <= 900


def test_benching_cannot_empty_the_chain():
    """If every model is benched the request must still be attempted, or a
    stale bench becomes the reason a workspace stops posting."""
    import inspect

    src = inspect.getsource(ai._call_openrouter)
    assert "if live:" in src, (
        "the chain is filtered without a guard for the empty case"
    )


def test_only_capacity_failures_bench():
    """400/401/403 fail identically everywhere. Benching them would hide a
    broken API key behind a slow degrade instead of surfacing it."""
    import inspect

    src = inspect.getsource(ai._call_openrouter)
    bench_call = src.index("_bench(candidate)")
    guard = src.rindex("status == 429", 0, bench_call)
    assert guard < bench_call
    assert ">= 500" in src[guard:bench_call]


def test_the_preferred_model_is_glm():
    """Text-only and 256K context. Vision paths deliberately keep a VL model:
    a text-only model handed an image does not fail, it invents."""
    assert ai.MARKETING_MODEL == "z-ai/glm-5.2:free"
    assert ai.FREE_MODEL_CHAIN[0] == "z-ai/glm-5.2:free"


def test_vision_paths_did_not_inherit_a_text_only_model():
    from services import bulk_ingest, video_pipeline_service

    assert "glm" not in video_pipeline_service.VISION_MODEL.lower()
    for m in bulk_ingest.VISION_MODELS:
        assert "glm" not in m.lower(), f"{m} is text-only but sits in a vision chain"
