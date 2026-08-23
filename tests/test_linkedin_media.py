"""LinkedIn was dropping every image without saying so.

multi_publisher handed image posts to linkedin_service.post_text, which had
no parameter for media. Python accepted the call, the caption went out, and
the picture was silently discarded — on the one platform in the set where a
post is mostly its image.

These cover the upload dance (initialize, PUT the bytes, reference the URN)
and, just as importantly, the failure path: a post that loses its image is
still worth publishing as text.
"""

from __future__ import annotations

import asyncio

import pytest

from services.linkedin_service import linkedin_service


@pytest.fixture
def creds(monkeypatch):
    async def _creds(_workspace_id):
        return "tok", "urn:li:person:abc"

    monkeypatch.setattr(linkedin_service, "_get_credentials", _creds)


class _Resp:
    def __init__(self, status=200, body=None, headers=None):
        self.status_code = status
        self._body = body or {}
        self.headers = headers or {}
        self.text = str(self._body)

    def json(self):
        return self._body


def test_post_text_still_works_with_no_media(creds, monkeypatch):
    """The change must not disturb the path that was already publishing."""
    seen = {}

    class _Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, headers=None, json=None):
            seen["payload"] = json
            return _Resp(201, headers={"x-restli-id": "urn:li:share:1"})

    monkeypatch.setattr("services.linkedin_service.httpx.AsyncClient", lambda **k: _Client())

    out = asyncio.run(linkedin_service.post_text("w1", "hello"))

    assert out == "urn:li:share:1"
    assert "content" not in seen["payload"], "a text post must not carry an empty media block"


def test_one_image_is_uploaded_and_attached(creds, monkeypatch):
    calls = []

    class _Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

        async def post(self, url, headers=None, json=None):
            calls.append(("POST", url))
            if "images?action=initializeUpload" in url:
                return _Resp(200, {"value": {
                    "uploadUrl": "https://upload.linkedin/x",
                    "image": "urn:li:image:IMG1",
                }})
            calls.append(("payload", json))
            return _Resp(201, headers={"x-restli-id": "urn:li:share:2"})

        async def get(self, url, **k):
            calls.append(("GET", url))
            return _Resp(200, headers={})

        async def put(self, url, content=None, headers=None):
            calls.append(("PUT", url, len(content or b"")))
            return _Resp(201)

    # The fetched bytes come back through .content, which _Resp lacks by default.
    _Resp.content = b"\x89PNG fake bytes"

    monkeypatch.setattr("services.linkedin_service.httpx.AsyncClient", lambda **k: _Client())

    out = asyncio.run(linkedin_service.post_text("w1", "hi", media_urls=["https://cdn/a.jpg"]))

    assert out == "urn:li:share:2"
    assert ("POST", "https://api.linkedin.com/rest/images?action=initializeUpload") in [
        (c[0], c[1]) for c in calls if c[0] == "POST"
    ] or any("initializeUpload" in c[1] for c in calls if c[0] == "POST")
    assert any(c[0] == "PUT" for c in calls), "the bytes were never uploaded"

    payload = next(c[1] for c in calls if c[0] == "payload")
    assert payload["content"] == {"media": {"id": "urn:li:image:IMG1"}}


def test_several_images_use_the_multiImage_shape(creds, monkeypatch):
    """Sending a list under the single-image key is rejected by LinkedIn."""
    seen = {}
    n = {"i": 0}

    class _Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

        async def post(self, url, headers=None, json=None):
            if "initializeUpload" in url:
                n["i"] += 1
                return _Resp(200, {"value": {
                    "uploadUrl": "https://upload/x",
                    "image": f"urn:li:image:IMG{n['i']}",
                }})
            seen["payload"] = json
            return _Resp(201, headers={"x-restli-id": "urn:li:share:3"})

        async def get(self, url, **k):
            return _Resp(200)

        async def put(self, url, content=None, headers=None):
            return _Resp(201)

    _Resp.content = b"bytes"
    monkeypatch.setattr("services.linkedin_service.httpx.AsyncClient", lambda **k: _Client())

    asyncio.run(linkedin_service.post_text("w1", "hi", media_urls=["a.jpg", "b.jpg"]))

    assert "multiImage" in seen["payload"]["content"]
    assert seen["payload"]["content"]["multiImage"]["images"] == [
        {"id": "urn:li:image:IMG1"}, {"id": "urn:li:image:IMG2"}
    ]


def test_a_failed_upload_still_publishes_the_text(creds, monkeypatch):
    """A post that loses its picture beats no post at all."""
    seen = {}

    class _Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

        async def post(self, url, headers=None, json=None):
            if "initializeUpload" in url:
                return _Resp(500, {"error": "upstream"})
            seen["payload"] = json
            return _Resp(201, headers={"x-restli-id": "urn:li:share:4"})

        async def get(self, url, **k): return _Resp(200)
        async def put(self, url, **k): return _Resp(201)

    _Resp.content = b"bytes"
    monkeypatch.setattr("services.linkedin_service.httpx.AsyncClient", lambda **k: _Client())

    out = asyncio.run(linkedin_service.post_text("w1", "hi", media_urls=["a.jpg"]))

    assert out == "urn:li:share:4", "the upload failed and took the whole post with it"
    assert "content" not in seen["payload"]


def test_video_is_left_off_rather_than_half_uploaded(creds, monkeypatch):
    """LinkedIn video needs chunked upload and a finalize call. Guessing at it
    would fail after the customer believed it had worked."""
    seen = {}
    touched = {"init": False}

    class _Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

        async def post(self, url, headers=None, json=None):
            if "initializeUpload" in url:
                touched["init"] = True
                return _Resp(200, {"value": {"uploadUrl": "u", "image": "urn:li:image:X"}})
            seen["payload"] = json
            return _Resp(201, headers={"x-restli-id": "urn:li:share:5"})

        async def get(self, url, **k): return _Resp(200)
        async def put(self, url, **k): return _Resp(201)

    _Resp.content = b"bytes"
    monkeypatch.setattr("services.linkedin_service.httpx.AsyncClient", lambda **k: _Client())

    out = asyncio.run(linkedin_service.post_text("w1", "hi", media_urls=["https://cdn/clip.mp4"]))

    assert out == "urn:li:share:5"
    assert touched["init"] is False, "a video was pushed through the image endpoint"
    assert "content" not in seen["payload"]


def test_multi_publisher_hands_linkedin_the_media():
    """The bug was at the call site: media_urls never reached this method."""
    import inspect
    from services import multi_publisher

    src = inspect.getsource(multi_publisher.publish_everywhere)
    call = src[src.index("linkedin_service.post_text"):]
    call = call[: call.index("))") + 2]
    assert "media_urls" in call, "LinkedIn is still being called without its media"
