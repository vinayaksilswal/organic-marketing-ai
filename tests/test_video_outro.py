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
    # Derived from the configured cap rather than hardcoded — this assertion
    # was pinned to 9000 for a 7M ceiling and broke the moment the ceiling
    # moved, which is a test asserting a constant rather than a behaviour.
    from services.video_outro import MAX_BITRATE
    ceiling = int(MAX_BITRATE.rstrip("M")) * 1000 + 2000   # + audio and overhead
    assert int(m.group(1)) < ceiling, (
        f"bitrate cap not applied: {m.group(1)} kb/s against a {MAX_BITRATE} cap"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Music, for clips that have none
#
# Instagram's licensed catalogue is only reachable inside the app — the
# Content Publishing API has no field for a track — so a silent clip published
# through the API is silent forever. The bed is how a silent clip gets sound
# without a human opening the app. It must never touch a clip that already has
# audio of its own.
# ─────────────────────────────────────────────────────────────────────────────

def test_track_choice_is_stable_for_a_clip():
    """Re-running a repair must not swap the music under a clip that already
    went out with a different track."""
    from services.video_outro import stable_choice

    tracks = [("a", "1.mp3"), ("b", "2.mp3"), ("c", "3.mp3")]
    assert stable_choice(tracks, "media-42") == stable_choice(tracks, "media-42")


def test_track_choice_spreads_across_the_library():
    """One track on all 90 silent clips is a worse result than silence."""
    from services.video_outro import stable_choice

    tracks = [(str(i), f"{i}.mp3") for i in range(4)]
    picked = {stable_choice(tracks, f"clip-{i}")[0] for i in range(60)}
    assert len(picked) == 4, f"only used {len(picked)} of 4 tracks"


def test_no_tracks_is_not_an_error():
    from services.video_outro import stable_choice

    assert stable_choice([], "clip") is None


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _FakeSession:
    def __init__(self, rows):
        self._rows = rows
        self.committed = False

    async def execute(self, _stmt):
        return _FakeResult(self._rows)

    async def commit(self):
        self.committed = True


class _Clip:
    def __init__(self, has_audio, mime="video/mp4"):
        self.id = "clip-1"
        self.url = "https://cdn/clip.mp4"
        self.mimeType = mime
        self.hasAudio = has_audio


class _Track:
    def __init__(self, i):
        self.id = f"t{i}"
        self.url = f"https://cdn/{i}.mp3"


@pytest.mark.asyncio
@pytest.mark.parametrize("has_audio,reason", [
    (True, "clip already has its own sound"),
    (None, "nobody has probed it, so silence is not established"),
])
async def test_posting_leaves_a_clip_alone_unless_it_is_known_silent(
    has_audio, reason, monkeypatch
):
    import worker

    called = []
    monkeypatch.setattr(
        "services.video_outro.add_music_at_url",
        lambda *a, **k: called.append(a),
    )
    session = _FakeSession([_Track(0)])
    await worker._ensure_media_has_sound(session, _Clip(has_audio), "ws")
    assert not called, f"music was added when {reason}"
    assert not session.committed


@pytest.mark.asyncio
async def test_posting_skips_music_when_there_are_no_tracks(monkeypatch):
    """No library means the clip posts silent — not that posting breaks."""
    import worker

    called = []
    monkeypatch.setattr(
        "services.video_outro.add_music_at_url",
        lambda *a, **k: called.append(a),
    )
    session = _FakeSession([])
    await worker._ensure_media_has_sound(session, _Clip(False), "ws")
    assert not called
    assert not session.committed


@pytest.mark.asyncio
async def test_posting_lays_a_bed_on_a_silent_clip(monkeypatch):
    import worker

    async def _fake_add(video_url, bed_url, workspace_id, media_id):
        return "https://cdn/clip_branded_scored.mp4"

    monkeypatch.setattr("services.video_outro.add_music_at_url", _fake_add)
    session = _FakeSession([_Track(0), _Track(1)])
    clip = _Clip(False)
    await worker._ensure_media_has_sound(session, clip, "ws")

    assert clip.url.endswith("_branded_scored.mp4")
    assert clip.hasAudio is True, "the clip must not be scored twice"
    assert session.committed
    # The catalog decides whether a clip still needs branding by looking for
    # "_branded" in its URL. Losing it would send this back through a 311MB
    # encode it does not need.
    assert "_branded" in clip.url


@pytest.mark.asyncio
async def test_a_failed_mux_leaves_the_clip_postable(monkeypatch):
    import worker

    async def _fails(*a, **k):
        return None

    monkeypatch.setattr("services.video_outro.add_music_at_url", _fails)
    session = _FakeSession([_Track(0)])
    clip = _Clip(False)
    original = clip.url
    await worker._ensure_media_has_sound(session, clip, "ws")

    assert clip.url == original, "a failed mux must not corrupt the media row"
    assert not session.committed


@pytest.mark.skipif(_ffmpeg() is None, reason="ffmpeg not available")
def test_bed_fills_a_silent_clip(tmp_path):
    ff = _ffmpeg()
    src = tmp_path / "silent.mp4"
    subprocess.run([
        ff, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "testsrc=size=360x640:rate=24:duration=2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(src),
    ], capture_output=True, timeout=120)
    bed = tmp_path / "bed.m4a"
    subprocess.run([
        ff, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "sine=frequency=220:duration=5",
        "-c:a", "aac", str(bed),
    ], capture_output=True, timeout=120)

    out = Path(append_outro(src, "Acme", "Follow for more", "@acme", audio_bed=bed))
    probe = subprocess.run([ff, "-hide_banner", "-i", str(out)],
                           capture_output=True, text=True, errors="ignore",
                           timeout=60).stderr
    assert "Audio:" in probe, "a silent clip was left silent despite a bed"


@pytest.mark.skipif(_ffmpeg() is None, reason="ffmpeg not available")
def test_bed_never_overrides_existing_audio(tmp_path):
    """Music dropped over someone talking ruins both. A clip that already has
    sound keeps exactly the sound it had."""
    ff = _ffmpeg()
    src = tmp_path / "talking.mp4"
    subprocess.run([
        ff, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "testsrc=size=360x640:rate=24:duration=2",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
        "-t", "2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        str(src),
    ], capture_output=True, timeout=120)
    bed = tmp_path / "bed.m4a"
    subprocess.run([
        ff, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "sine=frequency=100:duration=5",
        "-c:a", "aac", str(bed),
    ], capture_output=True, timeout=120)

    # The source tone is 440Hz. If the 100Hz bed had replaced it the dominant
    # frequency would move, so compare the two encodes byte-for-byte instead:
    # offering a bed must change nothing at all.
    with_bed = Path(append_outro(src, "Acme", audio_bed=bed,
                                 output_path=tmp_path / "with.mp4"))
    without = Path(append_outro(src, "Acme",
                                output_path=tmp_path / "without.mp4"))
    assert with_bed.stat().st_size == without.stat().st_size, (
        "offering a bed changed a clip that already had audio"
    )


def test_music_files_are_recognised_but_never_posted():
    """Tracks live in the same catalog table. Media rotation must not pick one
    as if it were a post — a bare audio file is not a Reel."""
    from services.bulk_ingest import _mime_for
    from services.media_rotation import _is_postable

    assert _mime_for("luxury-loop.mp3") == "audio/mpeg"
    assert _mime_for("track.wav") == "audio/wav"

    class _M:
        url = "https://cdn/track.mp3"
        isActive = True
        mimeType = "audio/mpeg"

    assert not _is_postable(_M()), "a music track was offered up as a post"


# ─────────────────────────────────────────────────────────────────────────────
# Refusing to start beats being killed
#
# An encode needs ~310MB. Starting one without that free does not make it slow,
# it makes the container exit — which takes the web server down and fails every
# upload in flight. Render killed this service twice that way.
# ─────────────────────────────────────────────────────────────────────────────

def test_memory_reading_is_none_when_not_containerised():
    """No cgroup files means no limit to respect, not a limit of zero — a
    false reading here would refuse every encode on a developer machine."""
    from services.video_outro import container_memory, memory_headroom_mb

    reading = container_memory()
    assert reading is None or (reading[0] >= 0 and reading[1] > 0)
    if reading is None:
        assert memory_headroom_mb() is None


def _cgroup(tmp_path, limit, *, anon=0, cache=0, active=None, slab=0, sock=0,
            v2=True):
    """Write a fake cgroup and return it in container_memory's form."""
    names = ("memory.current", "memory.max") if v2 else (
        "memory.usage_in_bytes", "memory.limit_in_bytes")
    current = anon + cache + slab + sock
    (tmp_path / names[0]).write_text(str(current))
    (tmp_path / names[1]).write_text(str(limit))
    active = cache if active is None else active
    if v2:
        keys = ("anon", "slab", "sock")
        lines = [f"anon {anon}", f"file {cache}", f"slab {slab}", f"sock {sock}",
                 f"active_file {active}", f"inactive_file {cache - active}"]
    else:
        keys = ("total_rss",)
        lines = [f"total_rss {anon}", f"total_cache {cache}"]
    (tmp_path / "memory.stat").write_text("\n".join(lines) + "\n")
    return ((str(tmp_path / names[0]), str(tmp_path / names[1]),
             str(tmp_path / "memory.stat"), keys),)


def test_cgroup_v2_reports_irreclaimable_memory(tmp_path):
    from services.video_outro import container_memory

    used, limit = container_memory(
        _cgroup(tmp_path, 537_000_000, anon=140_000_000, cache=20_000_000))
    assert (used, limit) == pytest.approx((140.0, 537.0))


def test_cgroup_v1_reports_rss(tmp_path):
    from services.video_outro import container_memory

    used, limit = container_memory(
        _cgroup(tmp_path, 512_000_000, anon=300_000_000, cache=50_000_000, v2=False))
    assert (used, limit) == pytest.approx((300.0, 512.0))


def test_active_page_cache_is_not_counted_as_used(tmp_path):
    """The bug that cost two nights, in one assertion.

    Freshly written video sits in ACTIVE page cache, not inactive. A first fix
    subtracted only inactive_file, so the reading still said "6MB free" on a
    container with hundreds of megabytes genuinely available -- and the guard
    refused every encode after the first. Exactly one clip got branded.
    """
    from services.video_outro import container_memory

    used, limit = container_memory(_cgroup(
        tmp_path, 537_000_000,
        anon=145_000_000, cache=390_000_000, active=390_000_000))
    assert used == pytest.approx(145.0), "page cache counted as real usage"
    assert limit - used > 340, "an encode would still be wrongly refused"


def test_slab_and_socket_memory_count_as_used(tmp_path):
    """Not reclaimable on demand, so they are real headroom lost."""
    from services.video_outro import container_memory

    used, _ = container_memory(_cgroup(
        tmp_path, 537_000_000, anon=140_000_000, slab=20_000_000, sock=5_000_000))
    assert used == pytest.approx(165.0)


def test_used_never_exceeds_what_the_cgroup_reports(tmp_path):
    """A stat file disagreeing with the counter must not invent headroom."""
    from services.video_outro import container_memory

    (tmp_path / "memory.current").write_text("100000000")
    (tmp_path / "memory.max").write_text("537000000")
    (tmp_path / "memory.stat").write_text("anon 900000000")
    pair = ((str(tmp_path / "memory.current"), str(tmp_path / "memory.max"),
             str(tmp_path / "memory.stat"), ("anon", "slab", "sock")),)
    used, _ = container_memory(pair)
    assert used == pytest.approx(100.0)


def test_falls_back_to_current_minus_cache_without_anon(tmp_path):
    """A kernel without `anon` must still exclude page cache rather than
    reverting to the reading that caused the stall."""
    from services.video_outro import container_memory

    (tmp_path / "memory.current").write_text("500000000")
    (tmp_path / "memory.max").write_text("537000000")
    (tmp_path / "memory.stat").write_text("file 360000000")
    pair = ((str(tmp_path / "memory.current"), str(tmp_path / "memory.max"),
             str(tmp_path / "memory.stat"), ("anon", "slab", "sock")),)
    used, _ = container_memory(pair)
    assert used == pytest.approx(140.0)


def test_no_stat_file_degrades_to_the_raw_counter(tmp_path):
    """Conservative, not wrong: it may refuse an encode it could have run,
    which is a delay rather than an outage."""
    from services.video_outro import container_memory

    (tmp_path / "memory.current").write_text("500000000")
    (tmp_path / "memory.max").write_text("537000000")
    pair = ((str(tmp_path / "memory.current"), str(tmp_path / "memory.max"),
             str(tmp_path / "nostat"), ("anon", "slab", "sock")),)
    used, _ = container_memory(pair)
    assert used == pytest.approx(500.0)


@pytest.mark.parametrize("limit", ["max", str(1 << 63), "0"])
def test_unset_limit_is_not_treated_as_a_ceiling(tmp_path, limit):
    """cgroup v2 writes "max" when uncapped and v1 a huge sentinel. Reading
    either as a real ceiling would compute a nonsense headroom — and reading
    it as a *small* one would refuse every encode forever."""
    from services.video_outro import container_memory

    (tmp_path / "memory.current").write_text("200000000")
    (tmp_path / "memory.max").write_text(limit)
    (tmp_path / "memory.stat").write_text("anon 100000000")
    pair = ((str(tmp_path / "memory.current"), str(tmp_path / "memory.max"),
             str(tmp_path / "memory.stat"), ("anon", "slab", "sock")),)
    assert container_memory(pair) is None


def test_missing_cgroup_files_are_not_an_error(tmp_path):
    from services.video_outro import container_memory

    pair = ((str(tmp_path / "nope"), str(tmp_path / "alsonope"),
             str(tmp_path / "nostat"), ("anon",)),)
    assert container_memory(pair) is None


def test_encode_is_skipped_when_memory_is_tight(tmp_path, monkeypatch):
    """The clip comes back unbranded and postable, to be retried next pass."""
    import services.video_outro as vo

    if vo._ffmpeg() is None:
        pytest.skip("ffmpeg not available")

    src = tmp_path / "clip.mp4"
    subprocess.run([
        vo._ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "testsrc=size=360x640:rate=24:duration=1",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(src),
    ], capture_output=True, timeout=120)

    monkeypatch.setattr(vo, "container_memory", lambda: (480.0, 512.0))
    monkeypatch.setattr(vo, "memory_headroom_mb", lambda: 32.0)

    ran = []
    real_run = subprocess.run
    monkeypatch.setattr(
        vo.subprocess, "run",
        lambda *a, **k: (ran.append(a), real_run(*a, **k))[1],
    )

    out = vo.append_outro(src, "Acme", "Book now", "acme.com")
    assert out == str(src), "a tight instance must return the clip unbranded"
    # _probe runs before the check; the encode itself must not have started.
    assert not any("libx264" in " ".join(map(str, a[0])) for a in ran), (
        "an encode was started despite there being no room for it"
    )


def test_encode_proceeds_with_room(tmp_path, monkeypatch):
    import services.video_outro as vo

    if vo._ffmpeg() is None:
        pytest.skip("ffmpeg not available")

    src = tmp_path / "clip.mp4"
    subprocess.run([
        vo._ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "testsrc=size=360x640:rate=24:duration=1",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(src),
    ], capture_output=True, timeout=120)

    monkeypatch.setattr(vo, "container_memory", lambda: (100.0, 2048.0))
    monkeypatch.setattr(vo, "memory_headroom_mb", lambda: 1948.0)

    out = vo.append_outro(src, "Acme", "Book now", "acme.com")
    assert out != str(src) and Path(out).exists()


def test_no_intermediate_files_are_left_behind(tmp_path):
    """Three passes means two temporary files per clip. Left on disk they
    accumulate across a 240-file library on an ephemeral disk."""
    import services.video_outro as vo

    if vo._ffmpeg() is None:
        pytest.skip("ffmpeg not available")

    src = tmp_path / "clip.mp4"
    subprocess.run([
        vo._ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "testsrc=size=360x640:rate=24:duration=1",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(src),
    ], capture_output=True, timeout=120)

    vo.append_outro(src, "Acme", "Book now", "acme.com")
    leftovers = list(tmp_path.glob("*__main.mp4")) + \
        list(tmp_path.glob("*__card.mp4")) + list(tmp_path.glob("*__join.txt"))
    assert not leftovers, f"intermediates left on disk: {leftovers}"


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


# ─────────────────────────────────────────────────────────────────────────────
# Delivery size follows the room available
#
# A single 340MB threshold blocked branding on an instance holding 199MB of
# 537MB: 338MB free, short by two megabytes, while 199 + 308 would have fitted
# with 30MB to spare. Nothing branded and the dashboard gave no reason.
# ─────────────────────────────────────────────────────────────────────────────

def test_full_size_when_there_is_room():
    from services.video_outro import choose_encode_size
    assert choose_encode_size(500) == (1080, 1920)


def test_the_two_megabyte_miss_now_encodes():
    """The exact reading that blocked production: 338MB free."""
    from services.video_outro import choose_encode_size
    assert choose_encode_size(338) == (1080, 1920)


def test_degrades_rather_than_skipping():
    """300MB cannot hold a 1080p encode but comfortably holds 720p. Skipping
    delivers nothing; degrading delivers a clip the platform re-encodes anyway."""
    from services.video_outro import choose_encode_size
    assert choose_encode_size(300) == (720, 1280)


def test_skips_only_when_nothing_fits():
    from services.video_outro import choose_encode_size
    assert choose_encode_size(120) is None


def test_no_cgroup_means_no_limit_to_respect():
    """On a laptop there is no container ceiling; full size every time."""
    from services.video_outro import TARGET_H, TARGET_W, choose_encode_size
    assert choose_encode_size(None) == (TARGET_W, TARGET_H)


def test_never_chooses_a_size_above_the_delivery_target():
    """VIDEO_TARGET_HEIGHT can lower the target; the table must not override it."""
    from services.video_outro import TARGET_H, TARGET_W, choose_encode_size
    for headroom in (10_000, 500, 300):
        size = choose_encode_size(headroom)
        if size:
            assert size[0] <= TARGET_W and size[1] <= TARGET_H


@pytest.mark.skipif(_ffmpeg() is None, reason="ffmpeg not available")
def test_the_degraded_encode_still_produces_a_branded_clip(tmp_path, monkeypatch):
    """A fallback that produced a broken file would be worse than skipping."""
    import re

    import services.video_outro as vo

    ff = _ffmpeg()
    src = tmp_path / "clip.mp4"
    subprocess.run([
        ff, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "testsrc=size=720x1280:rate=24:duration=2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(src),
    ], capture_output=True, timeout=120)

    # Enough for 720p, not for 1080p.
    monkeypatch.setattr(vo, "memory_headroom_mb", lambda: 300.0)
    monkeypatch.setattr(vo, "container_memory", lambda: (237.0, 537.0))

    out = Path(vo.append_outro(src, "Acme", "Book now", "acme.com"))
    assert out != src, "degraded encode returned the original instead of branding"
    assert out.exists() and out.stat().st_size > 0

    probe = subprocess.run([ff, "-hide_banner", "-i", str(out)],
                           capture_output=True, text=True, errors="ignore",
                           timeout=60).stderr
    assert "720x1280" in probe, probe[:300]
    m = re.search(r"Duration: 00:00:(\d+\.\d+)", probe)
    assert m and float(m.group(1)) > 2.0 + DEFAULT_OUTRO_SECONDS - 0.4, (
        "the end card is missing from the degraded encode"
    )
