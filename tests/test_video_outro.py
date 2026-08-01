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


# ─────────────────────────────────────────────────────────────────────────────
# Watermark and delivery quality
# ─────────────────────────────────────────────────────────────────────────────

def test_watermark_is_drawn_and_transparent():
    """It composites over footage, so everything but the text must be clear."""
    from PIL import Image
    from services.video_outro import build_watermark_png

    path = build_watermark_png("Billionaire Goal", 1080, 1920)
    assert path and path.exists()
    with Image.open(path) as im:
        assert im.mode == "RGBA"
        assert im.size == (1080, 1920)
        ink = im.getbbox()
        assert ink, "watermark drew nothing"
        # Corners must be fully transparent or it would tint the whole frame.
        assert im.getpixel((5, 5))[3] == 0


def test_watermark_clears_the_platform_ui():
    """Instagram overlays the bottom of a Reel with caption and buttons, so a
    mark sitting flush to the edge is covered."""
    from PIL import Image
    from services.video_outro import build_watermark_png

    with Image.open(build_watermark_png("Acme", 1080, 1920)) as im:
        top, bottom = im.getbbox()[1], im.getbbox()[3]
    assert bottom < 1920 * 0.93, "watermark sits under the platform UI"
    assert top > 1920 * 0.5, "watermark drifted into the middle of the frame"


@pytest.mark.skipif(_ffmpeg() is None, reason="ffmpeg not available")
def test_output_is_delivered_at_the_platform_spec(tmp_path):
    """A 720p source should leave at 1080x1920 rather than letting the
    platform upscale it with its own cheap scaler."""
    import re

    ff = _ffmpeg()
    src = tmp_path / "small.mp4"
    subprocess.run([
        ff, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "testsrc=size=720x1280:rate=24:duration=2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(src),
    ], capture_output=True, timeout=120)

    out = Path(append_outro(src, "Acme", "Book now", "acme.com"))
    assert out != src

    probe = subprocess.run([ff, "-hide_banner", "-i", str(out)],
                           capture_output=True, text=True, errors="ignore",
                           timeout=60).stderr
    assert "1080x1920" in probe, probe[:300]


@pytest.mark.skipif(_ffmpeg() is None, reason="ffmpeg not available")
def test_bitrate_is_capped(tmp_path):
    """Upscaling then sharpening manufactures detail that CRF spends bits on —
    a 1.8MB source came back at 44.8MB before the cap, for footage the platform
    re-encodes to about 4 Mbps anyway."""
    import re

    ff = _ffmpeg()
    src = tmp_path / "noisy.mp4"
    # Noise is the worst case for bitrate: nothing compresses.
    subprocess.run([
        ff, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "nullsrc=size=720x1280:rate=24:duration=3",
        "-vf", "geq=random(1)*255:128:128",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(src),
    ], capture_output=True, timeout=180)
    if not src.exists() or src.stat().st_size == 0:
        pytest.skip("could not synthesise a noise clip")

    out = Path(append_outro(src, "Acme"))
    probe = subprocess.run([ff, "-hide_banner", "-i", str(out)],
                           capture_output=True, text=True, errors="ignore",
                           timeout=60).stderr
    m = re.search(r"bitrate:\s*(\d+)\s*kb/s", probe)
    assert m, probe[:300]
    # 7M cap plus audio and container overhead.
    assert int(m.group(1)) < 9000, f"bitrate cap not applied: {m.group(1)} kb/s"


# ─────────────────────────────────────────────────────────────────────────────
# A page asks for a follow. It has nothing to sell.
# ─────────────────────────────────────────────────────────────────────────────

class _Page(_Profile):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.name = kw.get("name", "Billionaire Goal")
        self.primaryOffer = kw.get("primaryOffer", "")
        self.websiteUrl = kw.get("websiteUrl", "")
        self.businessModel = "Social Page"


def test_page_asks_for_a_follow_when_no_offer_is_set():
    brand, cta, url = outro_text_for(_Page())
    assert brand == "Billionaire Goal"
    assert cta.lower().startswith("follow")
    assert url == "@billionairegoal"


def test_page_never_shows_a_purchase_cta():
    """A themed page has nothing to sell, so "Start a subscription" describes a
    transaction that does not exist."""
    _, cta, _ = outro_text_for(_Page(primaryOffer="Start a subscription"))
    assert "subscription" not in cta.lower()
    assert cta.lower().startswith("follow")


def test_page_keeps_its_own_follow_wording():
    _, cta, _ = outro_text_for(_Page(primaryOffer="Follow for daily luxury"))
    assert cta == "Follow for daily luxury"


def test_page_with_a_website_shows_the_website():
    """The handle is the fallback for having no site, not a replacement."""
    _, _, url = outro_text_for(_Page(websiteUrl="https://bgoal.com"))
    assert url == "bgoal.com"


@pytest.mark.parametrize("model,offer,expected", [
    ("SaaS", "Run a free scan", "Run a free scan"),
    ("E-commerce", "Book a fitting", "Book a fitting"),
    ("Creator", "Join the newsletter", "Join the newsletter"),
])
def test_other_models_keep_their_offer(model, offer, expected):
    p = _Profile(primaryOffer=offer)
    p.businessModel = model
    _, cta, _ = outro_text_for(p)
    assert cta == expected
