"""One post, four platforms, each in the voice that platform is read in.

Three separate bugs lived in the block this replaces.

Every platform was attempted whether or not it was connected. The services
return None without a token, so a Meta-only workspace -- which is every
workspace today -- wrote "Twitter: ..." and "LinkedIn: ..." into its delivery
log on every post, forever. Two permanently red lines are how a log stops
being read.

The Instagram caption went out verbatim everywhere: chopped at 277 characters
mid-word for X, hashtag wall intact for LinkedIn.

And success was defined as `fb_post_id or ig_post_id`. A workspace connected
to X and LinkedIn only recorded every delivered post as FAILED and was never
charged a post against its plan.

These tests call the real functions. The tests that passed while `timedelta`
was unimported did so by reading source strings.
"""

import inspect

import pytest

from services import multi_publisher as mp


IG_CAPTION = (
    "Your competitors post daily and you post when you remember.\n\n"
    "Organiflo writes, schedules and publishes for you.\n\n"
    "#marketing #smallbusiness #socialmedia #contentcreator #growth #reels"
)


# =============================================================================
# Shaping one message for four places
# =============================================================================

def test_x_never_exceeds_the_limit_even_with_a_very_long_caption():
    text = mp.caption_for("x", "word " * 400 + "#alpha #beta #gamma")
    assert len(text) <= mp.X_LIMIT


def test_x_does_not_cut_a_word_in_half():
    """The old code sliced at 277 and appended an ellipsis, which routinely
    landed mid-word and mid-hashtag."""
    body = "supercalifragilistic " * 30
    text = mp.caption_for("x", body)
    trimmed = text.rstrip("…").strip()
    for word in trimmed.split():
        assert word == "supercalifragilistic", f"cut mid-word: {word!r}"


def test_x_keeps_at_most_two_hashtags():
    text = mp.caption_for("x", IG_CAPTION)
    assert text.count("#") <= 2


def test_linkedin_does_not_carry_a_wall_of_hashtags_in_the_paragraph():
    text = mp.caption_for("linkedin", IG_CAPTION)
    assert text.count("#") <= 3
    body = text.split("\n\n")[0]
    assert "#" not in body, "hashtags are still inside the message body"


def test_instagram_gets_the_caption_exactly_as_written():
    """It was written for Instagram. Nothing should touch it."""
    assert mp.caption_for("instagram", IG_CAPTION) == IG_CAPTION.strip()
    assert mp.caption_for("facebook", IG_CAPTION) == IG_CAPTION.strip()


def test_the_message_survives_the_shaping():
    """Shorter and re-ordered is fine. Losing the opening line is not."""
    for platform in ("x", "linkedin", "facebook", "instagram"):
        assert "competitors post daily" in mp.caption_for(platform, IG_CAPTION)


def test_an_empty_caption_does_not_explode():
    for platform in ("x", "linkedin", "facebook", "instagram"):
        assert mp.caption_for(platform, "") == ""
        assert mp.caption_for(platform, None) == ""


# =============================================================================
# Connected is not the same as configured
# =============================================================================

class _Conn:
    def __init__(self, **kw):
        self.fbPageId = self.fbAccessToken = self.igAccountId = None
        self.twitterAccessToken = self.twitterAccessSecret = None
        self.linkedinAccessToken = self.linkedinActorUrn = None
        for k, v in kw.items():
            setattr(self, k, v)


class _Session:
    """Enough of an AsyncSession for connected_platforms to run for real."""

    def __init__(self, conn):
        self._conn = conn

    async def execute(self, *_a, **_k):
        conn = self._conn

        class R:
            def scalars(self):
                class S:
                    def first(self_inner):
                        return conn

                return S()

        return R()


@pytest.mark.asyncio
async def test_a_workspace_with_no_connection_row_reports_nothing_connected():
    got = await mp.connected_platforms(_Session(None), "ws")
    assert got == {
        "facebook": False, "instagram": False, "x": False,
        "linkedin": False, "youtube": False,
    }


@pytest.mark.asyncio
async def test_meta_only_workspace_does_not_report_x_or_linkedin():
    conn = _Conn(fbPageId="1", fbAccessToken="t", igAccountId="2")
    got = await mp.connected_platforms(_Session(conn), "ws")
    assert got["facebook"] and got["instagram"]
    assert not got["x"] and not got["linkedin"]


@pytest.mark.asyncio
async def test_linkedin_needs_both_a_token_and_an_actor():
    """A token with no actor URN cannot name an author and LinkedIn rejects
    the post. Reporting it as connected would produce a failure per cycle."""
    half = _Conn(linkedinAccessToken="t")
    assert not (await mp.connected_platforms(_Session(half), "ws"))["linkedin"]

    whole = _Conn(linkedinAccessToken="t", linkedinActorUrn="urn:li:person:x")
    assert (await mp.connected_platforms(_Session(whole), "ws"))["linkedin"]


@pytest.mark.asyncio
async def test_x_needs_both_halves_of_the_oauth1_pair():
    half = _Conn(twitterAccessToken="t")
    assert not (await mp.connected_platforms(_Session(half), "ws"))["x"]


# =============================================================================
# Publishing: skipped is not failed
# =============================================================================

@pytest.fixture
def stub(monkeypatch):
    """Stand in for every network call so nothing leaves the machine."""
    calls = {}

    async def fb(ws, caption, media_urls=None):
        calls["facebook"] = caption
        return "fb_1"

    async def ig(ws, caption, media_urls=None):
        calls["instagram"] = caption
        return "ig_1"

    async def tweet(ws, text, media_urls=None):
        calls["x"] = text
        calls["x_media"] = media_urls or []
        return "x_1"

    async def li(ws, text, media_urls=None):
        calls["linkedin"] = text
        # Recorded like the X double above. LinkedIn used to be handed
        # the caption with its images stripped, and a stub that ignored
        # media could not have noticed.
        calls["linkedin_media"] = media_urls or []
        return "li_1"

    import services.linkedin_service as ls
    import services.social_service as ss
    import services.twitter_service as ts

    monkeypatch.setattr(ss, "post_to_facebook", fb)
    monkeypatch.setattr(ss, "post_to_instagram", ig)
    monkeypatch.setattr(ts.twitter_service, "post_tweet", tweet)
    monkeypatch.setattr(ls.linkedin_service, "post_text", li)
    return calls


def _with_connections(monkeypatch, **available):
    base = {"facebook": False, "instagram": False, "x": False, "linkedin": False}
    base.update(available)

    async def fake(session, workspace_id):
        return base

    monkeypatch.setattr(mp, "connected_platforms", fake)

    class _CM:
        async def __aenter__(self):
            return None

        async def __aexit__(self, *a):
            return False

    import database

    monkeypatch.setattr(database, "AsyncSessionLocal", lambda: _CM())


@pytest.mark.asyncio
async def test_an_unconnected_platform_is_skipped_not_failed(monkeypatch, stub):
    """The whole point. A Meta-only workspace must produce an empty failure
    list, because nothing failed."""
    _with_connections(monkeypatch, facebook=True, instagram=True)

    out = await mp.publish_everywhere("ws", IG_CAPTION, media_urls=["https://x/v.mp4"])

    assert out["failed"] == [], f"nothing failed, yet: {out['failed']}"
    assert sorted(out["skipped"]) == ["linkedin", "x", "youtube"]
    assert {e["platform"] for e in out["published"]} == {"facebook", "instagram"}


@pytest.mark.asyncio
async def test_an_unconnected_platform_is_never_called(monkeypatch, stub):
    _with_connections(monkeypatch, facebook=True)
    await mp.publish_everywhere("ws", IG_CAPTION)
    assert "x" not in stub and "linkedin" not in stub


@pytest.mark.asyncio
async def test_instagram_without_media_is_a_skip_not_a_failure(monkeypatch, stub):
    """Instagram cannot publish without media. That is a platform rule."""
    _with_connections(monkeypatch, facebook=True, instagram=True)
    out = await mp.publish_everywhere("ws", IG_CAPTION, media_urls=[])
    assert "instagram" in out["skipped"]
    assert out["failed"] == []


@pytest.mark.asyncio
async def test_each_platform_receives_its_own_shaping(monkeypatch, stub):
    _with_connections(monkeypatch, facebook=True, instagram=True, x=True, linkedin=True)
    await mp.publish_everywhere("ws", IG_CAPTION, media_urls=["https://x/v.mp4"])

    assert len(stub["x"]) <= mp.X_LIMIT
    assert stub["instagram"] == IG_CAPTION.strip()
    assert stub["linkedin"] != stub["instagram"]


@pytest.mark.asyncio
async def test_one_platform_failing_does_not_stop_the_others(monkeypatch, stub):
    async def boom(ws, caption, media_urls=None):
        raise RuntimeError("Meta says no")

    import services.social_service as ss

    monkeypatch.setattr(ss, "post_to_facebook", boom)
    _with_connections(monkeypatch, facebook=True, x=True, linkedin=True)

    out = await mp.publish_everywhere("ws", IG_CAPTION)

    assert {e["platform"] for e in out["published"]} == {"x", "linkedin"}
    assert out["failed"][0]["platform"] == "facebook"
    assert "Meta says no" in out["failed"][0]["error"]


@pytest.mark.asyncio
async def test_a_service_returning_none_counts_as_a_failure(monkeypatch, stub):
    """Silent None is how the old code failed without anyone noticing."""

    async def quiet(ws, text):
        return None

    import services.twitter_service as ts

    monkeypatch.setattr(ts.twitter_service, "post_tweet", quiet)
    _with_connections(monkeypatch, x=True)

    out = await mp.publish_everywhere("ws", IG_CAPTION)
    assert out["published"] == []
    assert out["failed"][0]["platform"] == "x"


# =============================================================================
# The worker end of it
# =============================================================================

def test_the_worker_records_a_post_that_only_reached_x_as_a_success():
    """`fb_post_id or ig_post_id` meant an X-and-LinkedIn-only workspace saw
    every delivered post stored as FAILED, and was never charged for it."""
    import worker

    src = inspect.getsource(worker.context_aggregation_task)
    assert "is_success = fb_post_id is not None or ig_post_id is not None" not in src
    assert "x_post_id, li_post_id" in src


def test_the_worker_stores_the_x_and_linkedin_post_ids():
    """Both columns have existed since the schema was written. Nothing ever
    wrote to them, so the dashboard could not show those deliveries."""
    import worker

    src = inspect.getsource(worker.context_aggregation_task)
    assert "twitterPostId=x_post_id" in src
    assert "linkedinPostId=li_post_id" in src


def test_the_actor_column_is_in_the_bootstrap_ddl():
    """The model declares it. If the bootstrap runs without Alembic, a missing
    column breaks every SELECT on SocialConnection -- not just LinkedIn."""
    import pathlib

    src = (pathlib.Path(__file__).resolve().parent.parent / "database.py").read_text(
        encoding="utf-8"
    )
    assert '"SocialConnection" ADD COLUMN IF NOT EXISTS "linkedinActorUrn"' in src


# =============================================================================
# The other publishing path, and whether anyone can see the result
# =============================================================================

def test_the_manual_publish_button_reaches_every_connected_platform():
    """The scheduled worker published everywhere; "publish now" called Meta
    only. A customer who connected X watched the automation post there and the
    button quietly not."""
    import routers.marketing as m

    src = inspect.getsource(m.run_automation_manually)
    assert "publish_everywhere" in src, "the manual path is still Meta-only"
    assert "x_post_id" in src and "li_post_id" in src


def test_the_manual_path_counts_a_non_meta_delivery_as_published():
    import routers.marketing as m

    src = inspect.getsource(m.run_automation_manually)
    assert "published = bool(fb_post_id or ig_post_id)" not in src
    assert "twitterPostId=x_post_id" in src
    assert "linkedinPostId=li_post_id" in src


def test_the_api_returns_the_platforms_that_carried_the_post():
    """Both columns were written on every publish and never returned, so a
    delivery to X and LinkedIn was invisible to the customer."""
    import pathlib

    src = (
        pathlib.Path(__file__).resolve().parent.parent / "routers" / "marketing.py"
    ).read_text(encoding="utf-8")
    assert '"twitterPostId": p.twitterPostId' in src
    assert '"linkedinPostId": p.linkedinPostId' in src


def test_the_interface_shows_all_four():
    import pathlib

    src = (
        pathlib.Path(__file__).resolve().parent.parent
        / "frontend" / "src" / "pages" / "dashboard" / "SocialScheduler.jsx"
    ).read_text(encoding="utf-8")
    assert "post.twitterPostId" in src
    assert "post.linkedinPostId" in src
    # The old form could only ever render two of them.
    assert "{post.fbPostId ? 'FB ✓' : ''} {post.igPostId ? 'IG ✓' : ''}" not in src


@pytest.mark.asyncio
async def test_youtube_is_skipped_when_there_is_no_video(monkeypatch, stub):
    """YouTube takes a video and nothing else. An image-only cycle is a skip,
    exactly as Instagram is when there is no media at all."""
    _with_connections(monkeypatch, youtube=True)
    out = await mp.publish_everywhere("ws", IG_CAPTION, media_urls=["https://x/photo.jpg"])
    assert "youtube" in out["skipped"]
    assert out["failed"] == []


def test_a_youtube_title_fits_the_platform_limit():
    """YouTube caps titles at 100 characters and rejects longer ones, so the
    caption cannot be handed over unshaped."""
    title = mp.caption_for("youtube", "word " * 200)
    assert len(title) <= 100


def test_the_youtube_title_is_one_line():
    """A title with a newline in it is refused by the API."""
    newline = chr(10)
    title = mp.caption_for("youtube", "First line here" + newline * 2 + "Second paragraph")
    assert newline not in title
    assert title.startswith("First line")


# =============================================================================
# "Link in bio" is right on exactly one platform
# =============================================================================

BIO_CAPTION = "Posting when you remember means posting never.\n\nStart free - link in bio\n\n#marketing"


def test_instagram_keeps_link_in_bio():
    """Correct there and nowhere else: IG captions are not clickable and a raw
    URL gets the post demoted, which is why the writer is told to say it."""
    out = mp.caption_for("instagram", BIO_CAPTION, website="https://organiflo.com")
    assert "link in bio" in out
    assert "organiflo.com" not in out


@pytest.mark.parametrize("platform", ["facebook", "linkedin", "x"])
def test_linkable_platforms_get_the_real_address(platform):
    """The same caption goes everywhere. On Facebook and LinkedIn a bio link
    is something the reader cannot see, so every one of those posts ended with
    a call to action that led nowhere."""
    out = mp.caption_for(platform, BIO_CAPTION, website="https://organiflo.com")
    assert "link in bio" not in out.lower(), f"{platform} still points at a bio"
    assert "organiflo.com" in out


def test_a_business_with_no_website_does_not_get_a_dangling_phrase():
    """Nowhere to point. Dropping the phrase beats sending a Facebook reader
    to a bio Facebook does not have."""
    out = mp.caption_for("facebook", BIO_CAPTION, website="")
    assert "link in bio" not in out.lower()


def test_a_caption_without_the_phrase_is_untouched():
    plain = "Just a post about the work.\n\n#marketing"
    assert mp.caption_for("facebook", plain, website="https://organiflo.com") == plain.strip()


@pytest.mark.parametrize("phrasing", [
    "link in bio", "Link In Bio", "the link in my bio", "link in our bio",
])
def test_the_usual_phrasings_are_all_caught(phrasing):
    out = mp.caption_for("facebook", f"Start today - {phrasing}", website="https://organiflo.com")
    assert "bio" not in out.lower(), f"missed: {phrasing}"


# =============================================================================
# What goes where, by what kind of post it is
# =============================================================================

def _everything_connected(monkeypatch):
    _with_connections(
        monkeypatch,
        facebook=True, instagram=True, x=True, linkedin=True, youtube=True,
    )


@pytest.fixture
def yt_stub(monkeypatch, stub):
    async def upload(ws, url, title, description="", privacy="public"):
        stub["youtube"] = title
        return "yt_1"

    import services.youtube_service as ys
    monkeypatch.setattr(ys, "upload_video", upload)
    return stub


@pytest.mark.asyncio
async def test_a_text_post_skips_the_platforms_that_require_media(monkeypatch, yt_stub):
    """Instagram cannot publish without media and YouTube needs a video.
    Neither is a failure — it is what those platforms are."""
    _everything_connected(monkeypatch)
    out = await mp.publish_everywhere("ws", "A text-only update", media_urls=[])

    went = sorted(e["platform"] for e in out["published"])
    assert went == ["facebook", "linkedin", "x"], went
    assert sorted(out["skipped"]) == ["instagram", "youtube"]
    assert out["failed"] == []


@pytest.mark.asyncio
async def test_an_image_post_goes_everywhere_except_youtube(monkeypatch, yt_stub):
    """YouTube takes video. An image post is a skip there and a real post
    everywhere else."""
    _everything_connected(monkeypatch)
    out = await mp.publish_everywhere("ws", "With a picture", media_urls=["https://x/p.jpg"])

    went = sorted(e["platform"] for e in out["published"])
    assert went == ["facebook", "instagram", "linkedin", "x"], went
    assert out["skipped"] == ["youtube"]


@pytest.mark.asyncio
async def test_a_video_post_reaches_every_connected_platform(monkeypatch, yt_stub):
    _everything_connected(monkeypatch)
    out = await mp.publish_everywhere("ws", "With a clip", media_urls=["https://x/c.mp4"])

    went = sorted(e["platform"] for e in out["published"])
    assert went == ["facebook", "instagram", "linkedin", "x", "youtube"], went
    assert out["skipped"] == []


@pytest.mark.asyncio
async def test_the_picture_actually_reaches_x(monkeypatch, yt_stub):
    """X received text only, so an image post arrived there as a bare line and
    the customer believed their picture had gone out."""
    _everything_connected(monkeypatch)
    await mp.publish_everywhere("ws", "With a picture", media_urls=["https://x/p.jpg"])
    assert yt_stub.get("x_media") == ["https://x/p.jpg"]


@pytest.mark.asyncio
async def test_the_picture_actually_reaches_linkedin(monkeypatch, yt_stub):
    """The same bug as X, found later and on the platform where it costs most.

    post_text had no media parameter at all, so multi_publisher handed
    LinkedIn the caption and dropped the image on the floor without an error.
    """
    _everything_connected(monkeypatch)
    await mp.publish_everywhere("ws", "With a picture", media_urls=["https://x/p.jpg"])
    assert yt_stub.get("linkedin_media") == ["https://x/p.jpg"]
