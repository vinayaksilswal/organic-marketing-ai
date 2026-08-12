"""After Instagram flags images as spam, post video instead of retrying."""

import uuid

import pytest

from database import Media, SocialPost
from services.media_rotation import select_next_media
from services.publish_cooldown import SPAM_FLAG, image_publishing_blocked

WORKSPACE = "ws-cooldown"

SPAM_ERROR = (
    "IG: Image upload failed: Application request limit reached — We restrict "
    f"certain activity to protect our community. [code 4/{SPAM_FLAG}]"
)


def _media(url, mime="image/jpeg"):
    return Media(
        id=str(uuid.uuid4()),
        filename=url.split("/")[-1],
        mimeType=mime,
        url=url,
        isActive=True,
        businessProfileId=WORKSPACE,
    )


def _post(urls, error=None, ig_id=None):
    return SocialPost(
        id=str(uuid.uuid4()),
        businessProfileId=WORKSPACE,
        platform="ALL",
        caption="x",
        mediaUrls=urls,
        status="POSTED" if ig_id else "FAILED",
        igPostId=ig_id,
        errorLog=error,
    )


class TestDetection:
    @pytest.mark.asyncio
    async def test_quiet_workspace_is_not_blocked(self, db_session):
        assert not await image_publishing_blocked(db_session, WORKSPACE)

    @pytest.mark.asyncio
    async def test_one_refusal_is_not_enough(self, db_session):
        # A single failure can be a blip; switching formats on it would be an
        # overreaction to noise.
        db_session.add(_post(["https://cdn/a.jpg"], SPAM_ERROR))
        await db_session.commit()
        assert not await image_publishing_blocked(db_session, WORKSPACE)

    @pytest.mark.asyncio
    async def test_two_refusals_trip_it(self, db_session):
        for _ in range(2):
            db_session.add(_post(["https://cdn/a.jpg"], SPAM_ERROR))
        await db_session.commit()
        assert await image_publishing_blocked(db_session, WORKSPACE)

    @pytest.mark.asyncio
    async def test_unrelated_failures_do_not_trip_it(self, db_session):
        # Only Meta's spam marker counts. A caption or network failure means
        # something else entirely and must not switch the account to video.
        for _ in range(4):
            db_session.add(_post(["https://cdn/a.jpg"], "IG: something else broke"))
        await db_session.commit()
        assert not await image_publishing_blocked(db_session, WORKSPACE)

    @pytest.mark.asyncio
    async def test_video_refusals_do_not_block_images(self, db_session):
        for _ in range(3):
            db_session.add(_post(["https://cdn/clip.mp4"], SPAM_ERROR))
        await db_session.commit()
        assert not await image_publishing_blocked(db_session, WORKSPACE)

    @pytest.mark.asyncio
    async def test_a_successful_image_clears_it(self, db_session):
        """If Instagram is taking images again, stop suppressing them."""
        for _ in range(3):
            db_session.add(_post(["https://cdn/a.jpg"], SPAM_ERROR))
        db_session.add(_post(["https://cdn/b.jpg"], ig_id="17999"))
        await db_session.commit()
        assert not await image_publishing_blocked(db_session, WORKSPACE)

    @pytest.mark.asyncio
    async def test_a_successful_video_does_not_clear_it(self, db_session):
        # Video was never blocked, so a video publishing proves nothing about
        # whether images are accepted again.
        for _ in range(3):
            db_session.add(_post(["https://cdn/a.jpg"], SPAM_ERROR))
        db_session.add(_post(["https://cdn/clip.mp4"], ig_id="17999"))
        await db_session.commit()
        assert await image_publishing_blocked(db_session, WORKSPACE)


class TestRotation:
    @pytest.mark.asyncio
    async def test_a_blocked_workspace_is_offered_video(self, db_session):
        db_session.add(_media("https://cdn/one.jpg"))
        db_session.add(_media("https://cdn/two.jpg"))
        db_session.add(_media("https://cdn/clip.mp4", "video/mp4"))
        for _ in range(2):
            db_session.add(_post(["https://cdn/one.jpg"], SPAM_ERROR))
        await db_session.commit()

        for _ in range(6):
            chosen = await select_next_media(db_session, WORKSPACE)
            assert chosen.mimeType.startswith("video/")

    @pytest.mark.asyncio
    async def test_an_unblocked_workspace_still_gets_images(self, db_session):
        db_session.add(_media("https://cdn/only.jpg"))
        await db_session.commit()
        chosen = await select_next_media(db_session, WORKSPACE)
        assert chosen.mimeType.startswith("image/")

    @pytest.mark.asyncio
    async def test_image_only_catalog_still_posts_rather_than_stalling(self, db_session):
        """No video to fall back to must not mean no post at all.

        A workspace whose whole catalog is images would otherwise go silent
        for the duration of the block, which is worse than attempting.
        """
        db_session.add(_media("https://cdn/only.jpg"))
        for _ in range(2):
            db_session.add(_post(["https://cdn/only.jpg"], SPAM_ERROR))
        await db_session.commit()

        chosen = await select_next_media(db_session, WORKSPACE)
        assert chosen is not None
        assert chosen.mimeType.startswith("image/")
