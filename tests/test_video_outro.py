"""The composited end card.

The video model cannot draw a legible sentence, so the written call to action
is composited afterwards where the text is real. These cover the card itself
and, more importantly, that every failure path returns a still-postable clip —
a missing outro is cosmetic, a post that never goes out is not.
"""

import subprocess
from pathlib import Path

import pytest

from services.video_outro import (
    DEFAULT_OUTRO_SECONDS,
    _ffmpeg,
    append_outro,
    build_outro_card,
    outro_text_for,
)


class _Profile:
    def __init__(self, **kw):
        self.name = kw.get("name", "QuantCAI")
        self.primaryOffer = kw.get("primaryOffer", "Run a free scan")
        self.websiteUrl = kw.get("websiteUrl", "https://quantcai.info/")


# ── what the card says ───────────────────────────────────────────────────────

def test_outro_text_strips_the_url_scheme():
    """"https://quantcai.info/" is not how anyone reads a domain aloud or on
    screen; the bare host is what people can retype."""
    brand, cta, url = outro_text_for(_Profile())
    assert brand == "QuantCAI"
    assert cta == "Run a free scan"
    assert url == "quantcai.info"


@pytest.mark.parametrize("raw,expected", [
    ("https://acme.com", "acme.com"),
    ("http://acme.com/", "acme.com"),
    ("www.acme.com", "acme.com"),
    ("acme.com/pricing", "acme.com/pricing"),
    ("", ""),
])
def test_url_normalisation(raw, expected):
    _, _, url = outro_text_for(_Profile(websiteUrl=raw))
    assert url == expected


def test_long_offer_is_trimmed_to_fit_the_card():
    """A full sentence wraps badly at 1080 wide and reads as a paragraph."""
    _, cta, _ = outro_text_for(_Profile(
        primaryOffer="Head over to our website today and browse the entire collection"
    ))
    assert len(cta.split()) <= 6


def test_trailing_full_stop_removed():
    _, cta, _ = outro_text_for(_Profile(primaryOffer="Book a fitting."))
    assert cta == "Book a fitting"


# ── the card image ───────────────────────────────────────────────────────────

def test_card_renders_at_the_source_dimensions():
    card = build_outro_card("QuantCAI", "Run a free scan", "quantcai.info",
                            width=720, height=1280)
    assert card and card.exists()
    from PIL import Image
    with Image.open(card) as im:
        assert im.size == (720, 1280)


def test_card_renders_with_only_a_brand():
    """Workspaces without an offer or a website still get a branded end."""
    card = build_outro_card("Ridgeline", "", "", width=540, height=960)
    assert card and card.exists()


def test_card_is_not_blank():
    """A card that draws nothing is worse than no card — it is dead air."""
    from PIL import Image
    card = build_outro_card("QuantCAI", "Run a free scan", "quantcai.info",
                            width=540, height=960)
    with Image.open(card) as im:
        colours = im.convert("RGB").getcolors(maxcolors=1_000_000)
    assert colours and len(colours) > 1, "card rendered as a flat fill"


# ── failure paths must stay postable ─────────────────────────────────────────

def test_missing_source_returns_the_original_path():
    assert append_outro("/nope/missing.mp4", "QuantCAI") == "/nope/missing.mp4"


def test_unreadable_file_returns_the_original_path(tmp_path):
    """A truncated or non-video file must not raise into the posting path."""
    junk = tmp_path / "notavideo.mp4"
    junk.write_bytes(b"this is not a video")
    assert append_outro(junk, "QuantCAI") == str(junk)


def test_no_ffmpeg_returns_the_original_path(tmp_path, monkeypatch):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"\x00" * 32)
    monkeypatch.setattr("services.video_outro._ffmpeg", lambda: None)
    assert append_outro(clip, "QuantCAI") == str(clip)


def test_missing_brand_name_still_returns_a_path(tmp_path):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"\x00" * 32)
    assert isinstance(append_outro(clip, ""), str)


# ── end to end, when ffmpeg is present ───────────────────────────────────────

@pytest.mark.skipif(_ffmpeg() is None, reason="ffmpeg not available")
def test_outro_extends_the_clip_and_keeps_the_audio(tmp_path):
    """Concat drops the audio stream unless the card carries its own silence,
    which posts the clip mute."""
    ff = _ffmpeg()
    src = tmp_path / "src.mp4"
    subprocess.run([
        ff, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "testsrc=size=360x640:rate=24:duration=2",
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-t", "2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        str(src),
    ], capture_output=True, timeout=120)
    assert src.exists()

    out = Path(append_outro(src, "QuantCAI", "Run a free scan", "quantcai.info"))
    assert out != src, "outro was not appended"
    assert out.exists() and out.stat().st_size > 0

    probe = subprocess.run([ff, "-hide_banner", "-i", str(out)],
                           capture_output=True, text=True, errors="ignore",
                           timeout=60).stderr
    assert "Audio:" in probe, "audio stream was dropped"

    import re
    m = re.search(r"Duration: 00:00:(\d+\.\d+)", probe)
    assert m, probe[:400]
    # 2s source plus the card, allowing for keyframe rounding.
    assert float(m.group(1)) > 2.0 + DEFAULT_OUTRO_SECONDS - 0.4


@pytest.mark.skipif(_ffmpeg() is None, reason="ffmpeg not available")
def test_silent_source_does_not_break(tmp_path):
    """A clip with no audio track must not trip the audio concat branch."""
    ff = _ffmpeg()
    src = tmp_path / "silent.mp4"
    subprocess.run([
        ff, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "testsrc=size=360x640:rate=24:duration=1",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(src),
    ], capture_output=True, timeout=120)

    out = Path(append_outro(src, "QuantCAI"))
    assert out.exists() and out.stat().st_size > 0
