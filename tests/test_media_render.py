"""Spending the key, not just storing it.

The connect flow shipped first: a customer could paste a Replicate token, see
"connected", and nothing would ever call Replicate. A stored credential that
is never spent is the same failure this codebase keeps producing — a working
setup screen attached to nothing.

The invariant worth guarding hardest is the last test in the first section:
every provider offered in the catalogue must be one the renderer can actually
spend. Otherwise somebody connects a key that renders nothing, and finds out
only when they press Generate.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from services import media_providers, media_render
from services.crypto_service import encrypt_token


# ---------------------------------------------------------------------------
# The catalogue and the renderer must not drift apart
# ---------------------------------------------------------------------------

def test_every_offered_provider_can_actually_be_rendered():
    """Runway and Kling were removed for exactly this reason.

    Runway's video endpoint needs an input image and Kling signs requests with
    a JWT; neither is prompt in, file out. Leaving them listed would let a
    customer connect a credential this cannot spend.
    """
    import inspect

    dispatch = inspect.getsource(media_render.render)
    for kind, entries in media_providers.PROVIDERS.items():
        for entry in entries:
            assert f'provider == "{entry["id"]}"' in dispatch, (
                f"{entry['id']} is offered for {kind} but the renderer has no branch for it"
            )


def test_the_removed_providers_are_really_gone():
    offered = {e["id"] for entries in media_providers.PROVIDERS.values() for e in entries}
    assert "runway" not in offered
    assert "kling" not in offered


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _session_with(provider, model, kind="image", key="r8_secret"):
    row = SimpleNamespace(provider=provider, model=model, apiKey=encrypt_token(key))

    class _Result:
        def scalars(self):
            return SimpleNamespace(first=lambda: row)

    class _Session:
        async def execute(self, *a, **k):
            return _Result()

    return _Session()


class _Resp:
    def __init__(self, status=200, body=None):
        self.status_code = status
        self._body = body or {}
        self.text = str(self._body)

    def json(self):
        return self._body


def _client(handler):
    class _Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, headers=None, json=None, **k):
            return handler("POST", url, headers, json)
        async def get(self, url, headers=None, **k):
            return handler("GET", url, headers, None)

    return lambda **k: _Client()


def test_replicate_returns_the_finished_file(monkeypatch):
    seen = {}

    def handler(method, url, headers, body):
        seen["url"] = url
        seen["auth"] = (headers or {}).get("Authorization")
        seen["input"] = (body or {}).get("input")
        return _Resp(201, {"status": "succeeded", "output": ["https://cdn/out.png"]})

    monkeypatch.setattr("services.media_render.httpx.AsyncClient", _client(handler))

    out = asyncio.run(media_render.render(
        _session_with("replicate", "black-forest-labs/flux-schnell"),
        "u1", "w1", kind="image", prompt="a cat",
    ))

    assert out["url"] == "https://cdn/out.png"
    assert "black-forest-labs/flux-schnell" in seen["url"]
    assert seen["auth"] == "Bearer r8_secret", "the decrypted key never reached the provider"
    # Instagram is the target, so vertical.
    assert seen["input"]["aspect_ratio"] == "9:16"


def test_replicate_polls_when_the_job_is_not_ready(monkeypatch):
    calls = {"n": 0}

    def handler(method, url, headers, body):
        if method == "POST":
            return _Resp(201, {"status": "starting", "urls": {"get": "https://api/p/1"}})
        calls["n"] += 1
        if calls["n"] < 2:
            return _Resp(200, {"status": "processing"})
        return _Resp(200, {"status": "succeeded", "output": "https://cdn/v.mp4"})

    monkeypatch.setattr("services.media_render.httpx.AsyncClient", _client(handler))
    monkeypatch.setattr("services.media_render.POLL_INTERVAL_SECONDS", 0)

    out = asyncio.run(media_render.render(
        _session_with("replicate", "minimax/video-01", kind="video"),
        "u1", "w1", kind="video", prompt="a clip",
    ))
    assert out["url"] == "https://cdn/v.mp4"


def test_a_failed_replicate_job_says_why(monkeypatch):
    def handler(method, url, headers, body):
        if method == "POST":
            return _Resp(201, {"status": "starting", "urls": {"get": "https://api/p/1"}})
        return _Resp(200, {"status": "failed", "error": "NSFW content detected"})

    monkeypatch.setattr("services.media_render.httpx.AsyncClient", _client(handler))
    monkeypatch.setattr("services.media_render.POLL_INTERVAL_SECONDS", 0)

    with pytest.raises(media_render.RenderError) as e:
        asyncio.run(media_render.render(
            _session_with("replicate", "a/b"), "u1", "w1", kind="image", prompt="x",
        ))
    assert "NSFW content detected" in str(e.value)


def test_a_stuck_job_gives_up_rather_than_billing_forever(monkeypatch):
    """It is the customer's account being charged, so polling has a ceiling."""
    def handler(method, url, headers, body):
        if method == "POST":
            return _Resp(201, {"status": "starting", "urls": {"get": "https://api/p/1"}})
        return _Resp(200, {"status": "processing"})

    monkeypatch.setattr("services.media_render.httpx.AsyncClient", _client(handler))
    monkeypatch.setattr("services.media_render.POLL_INTERVAL_SECONDS", 0)
    # A real duration, however small. The first version of this test set the
    # timeout against an accumulated counter that a zero interval never
    # advanced, and the suite hung -- which is how the deadline in _replicate
    # became wall-clock rather than a running total.
    monkeypatch.setattr("services.media_render.POLL_TIMEOUT_SECONDS", 0.05)

    with pytest.raises(media_render.RenderError) as e:
        asyncio.run(media_render.render(
            _session_with("replicate", "a/b"), "u1", "w1", kind="image", prompt="x",
        ))
    assert "still working" in str(e.value)


@pytest.mark.parametrize("status,expected", [
    (401, "rejected the key"),
    (402, "no credit"),
])
def test_provider_errors_become_something_a_person_can_act_on(monkeypatch, status, expected):
    monkeypatch.setattr("services.media_render.httpx.AsyncClient",
                        _client(lambda *a: _Resp(status, {"detail": "..."})))

    with pytest.raises(media_render.RenderError) as e:
        asyncio.run(media_render.render(
            _session_with("replicate", "a/b"), "u1", "w1", kind="image", prompt="x",
        ))
    assert expected in str(e.value)


def test_openai_base64_is_returned_as_a_usable_source(monkeypatch):
    monkeypatch.setattr("services.media_render.httpx.AsyncClient",
                        _client(lambda *a: _Resp(200, {"data": [{"b64_json": "aGVsbG8="}]})))

    out = asyncio.run(media_render.render(
        _session_with("openai", "gpt-image-1", key="sk-x"),
        "u1", "w1", kind="image", prompt="x",
    ))
    assert out["url"].startswith("data:image/png;base64,")


def test_fal_returns_the_first_image(monkeypatch):
    monkeypatch.setattr("services.media_render.httpx.AsyncClient",
                        _client(lambda *a: _Resp(200, {"images": [{"url": "https://fal/i.png"}]})))

    out = asyncio.run(media_render.render(
        _session_with("fal", "fal-ai/flux/dev", key="fal-x"),
        "u1", "w1", kind="image", prompt="x",
    ))
    assert out["url"] == "https://fal/i.png"


# ---------------------------------------------------------------------------
# Refusals that must happen before any money is spent
# ---------------------------------------------------------------------------

def test_no_connected_account_is_refused_before_any_call():
    class _Empty:
        async def execute(self, *a, **k):
            return SimpleNamespace(scalars=lambda: SimpleNamespace(first=lambda: None))

    with pytest.raises(media_render.RenderError) as e:
        asyncio.run(media_render.render(_Empty(), "u1", "w1", kind="image", prompt="x"))
    assert "Connect one first" in str(e.value)


def test_an_empty_prompt_is_refused():
    with pytest.raises(media_render.RenderError):
        asyncio.run(media_render.render(
            _session_with("replicate", "a/b"), "u1", "w1", kind="image", prompt="   ",
        ))


def test_a_provider_stored_before_the_catalogue_was_trimmed_fails_clearly():
    """A key connected when Runway was still listed must not silently no-op."""
    with pytest.raises(media_render.RenderError) as e:
        asyncio.run(media_render.render(
            _session_with("runway", "gen4_turbo"), "u1", "w1", kind="video", prompt="x",
        ))
    assert "cannot be rendered" in str(e.value)
    assert "replicate" in str(e.value), "the message has to name what does work"


def test_the_key_is_never_logged_or_returned(monkeypatch):
    monkeypatch.setattr("services.media_render.httpx.AsyncClient",
                        _client(lambda *a: _Resp(200, {"status": "succeeded", "output": "u"})))

    out = asyncio.run(media_render.render(
        _session_with("replicate", "a/b", key="r8_TOPSECRET"),
        "u1", "w1", kind="image", prompt="x",
    ))
    assert "r8_TOPSECRET" not in str(out)


# ---------------------------------------------------------------------------
# The endpoint
# ---------------------------------------------------------------------------

def test_the_render_endpoint_exists_and_is_called_by_the_interface():
    import pathlib

    from routers.creative_api import router

    assert "/api/v1/creatives/media-render" in {r.path for r in router.routes}

    front = pathlib.Path("frontend/src")
    src = "\n".join(
        f.read_text(encoding="utf-8", errors="ignore")
        for f in front.rglob("*.jsx")
    )
    assert "creatives/media-render" in src, "the endpoint exists and nothing calls it"


def test_the_render_is_backgrounded():
    """A video model takes minutes; Render's proxy closes the request first.

    Waiting inline would turn every video render into a gateway timeout the
    customer reads as failure, while their provider account is billed for a
    file that did render.
    """
    import inspect

    import routers.creative_api as mod

    src = inspect.getsource(mod.render_media)
    assert "spawn_background" in src
    # And the refusals must happen before detaching, or there is nowhere left
    # to report them.
    assert src.index("connected") < src.index("spawn_background")


def test_the_endpoint_does_not_claim_the_file_exists_yet():
    import inspect

    import routers.creative_api as mod

    src = inspect.getsource(mod.render_media)
    returned = src[src.index("return {"):]
    assert "started" in returned.lower()
    for lie in ("generated.", "your image is ready", "done"):
        assert lie not in returned.lower()
