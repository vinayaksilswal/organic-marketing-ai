"""Media rotation must cover the whole catalog before repeating anything.

These run against a real database rather than mocks, because both bugs they
cover were ordering bugs — a mock returning a canned list would have passed
while production republished one asset forever.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from database import BusinessProfile, Media, SocialPost
from services.media_rotation import select_next_media

WORKSPACE = "ws-rotation"
USER = "user-rotation"


async def _seed(session, *, count=5, ai_flags=None):
    session.add(
        BusinessProfile(
            id=WORKSPACE,
            userId=USER,
            name="Rotation Test",
        )
    )
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    media = []
    for i in range(count):
        m = Media(
            id=f"media-{i}",
            userId=USER,
            businessProfileId=WORKSPACE,
            filename=f"asset-{i}.jpg",
            mimeType="image/jpeg",
            url=f"https://cdn.example.com/asset-{i}.jpg",
            aiGenerated=bool(ai_flags[i]) if ai_flags else True,
            isActive=True,
            createdAt=base + timedelta(hours=i),
        )
        media.append(m)
        session.add(m)
    await session.commit()
    return media


async def _record_post(session, media, when):
    session.add(
        SocialPost(
            id=str(uuid.uuid4()),
            userId=USER,
            businessProfileId=WORKSPACE,
            platform="BOTH",
            type="IMAGE",
            status="POSTED",
            caption="test",
            mediaUrls=[media.url],
            scheduledAt=when,
            postedAt=when,
            createdAt=when,
        )
    )
    await session.commit()


@pytest.mark.asyncio
async def test_full_catalog_covered_before_any_repeat(db_session):
    """The reported bug: the same asset published over and over."""
    await _seed(db_session, count=5)

    when = datetime(2026, 2, 1, tzinfo=timezone.utc)
    published = []
    for i in range(5):
        chosen = await select_next_media(db_session, WORKSPACE)
        assert chosen is not None
        published.append(chosen.url)
        await _record_post(db_session, chosen, when + timedelta(hours=i))

    assert len(set(published)) == 5, (
        f"Expected all 5 assets before any repeat, got {published}"
    )


@pytest.mark.asyncio
async def test_second_pass_recycles_least_recently_used_first(db_session):
    """After a full pass, the next pick is the one that has waited longest.

    The order of the first pass is random, so the asset idle the longest is
    whichever went out first -- not index 0. Asserting on index 0 only worked
    while the pass ran in catalog order.
    """
    await _seed(db_session, count=3)

    when = datetime(2026, 2, 1, tzinfo=timezone.utc)
    published = []
    for i in range(3):
        chosen = await select_next_media(db_session, WORKSPACE)
        published.append(chosen.url)
        await _record_post(db_session, chosen, when + timedelta(hours=i))

    nxt = await select_next_media(db_session, WORKSPACE)
    assert nxt.url == published[0], (
        "recycling did not start with the asset that has waited longest"
    )


@pytest.mark.asyncio
async def test_assets_beyond_the_old_twenty_row_window_are_reachable(db_session):
    """The old worker capped candidates at 20 rows, stranding older assets."""
    await _seed(db_session, count=25)

    when = datetime(2026, 2, 1, tzinfo=timezone.utc)
    published = set()
    for i in range(25):
        chosen = await select_next_media(db_session, WORKSPACE)
        published.add(chosen.url)
        await _record_post(db_session, chosen, when + timedelta(hours=i))

    assert len(published) == 25


@pytest.mark.asyncio
async def test_queued_post_consumes_the_asset(db_session):
    """A scheduled-but-unpublished post must still block reselection.

    Otherwise a tick that queues a post is immediately followed by another
    tick queuing the same asset.
    """
    await _seed(db_session, count=3)
    chosen = await select_next_media(db_session, WORKSPACE)

    session_when = datetime(2026, 2, 1, tzinfo=timezone.utc)
    db_session.add(
        SocialPost(
            id=str(uuid.uuid4()),
            userId=USER,
            businessProfileId=WORKSPACE,
            platform="BOTH",
            type="IMAGE",
            status="SCHEDULED",
            caption="queued",
            mediaUrls=[chosen.url],
            scheduledAt=session_when,
            postedAt=None,
            createdAt=session_when,
        )
    )
    await db_session.commit()

    nxt = await select_next_media(db_session, WORKSPACE)
    assert nxt.url != chosen.url


@pytest.mark.asyncio
async def test_ai_preference_never_strands_unpublished_assets(db_session):
    """prefer_ai_generated may reorder, but must not exclude.

    The old worker preferred AI media so hard that a workspace of uploaded
    assets could never be rotated once one AI asset existed.
    """
    await _seed(db_session, count=4, ai_flags=[False, False, True, False])

    when = datetime(2026, 2, 1, tzinfo=timezone.utc)
    published = set()
    for i in range(4):
        chosen = await select_next_media(db_session, WORKSPACE, prefer_ai_generated=True)
        published.add(chosen.url)
        await _record_post(db_session, chosen, when + timedelta(hours=i))

    assert len(published) == 4


@pytest.mark.asyncio
async def test_prompt_notes_and_deactivated_assets_are_skipped(db_session):
    await _seed(db_session, count=2)
    db_session.add(
        Media(
            id="note", userId=USER, businessProfileId=WORKSPACE,
            filename="note.txt", mimeType="text/plain", url="",
            isActive=True, createdAt=datetime(2025, 12, 1, tzinfo=timezone.utc),
        )
    )
    db_session.add(
        Media(
            id="off", userId=USER, businessProfileId=WORKSPACE,
            filename="off.jpg", mimeType="image/jpeg",
            url="https://cdn.example.com/off.jpg",
            isActive=False, createdAt=datetime(2025, 12, 2, tzinfo=timezone.utc),
        )
    )
    await db_session.commit()

    when = datetime(2026, 2, 1, tzinfo=timezone.utc)
    for i in range(4):
        chosen = await select_next_media(db_session, WORKSPACE)
        assert chosen.id not in ("note", "off")
        await _record_post(db_session, chosen, when + timedelta(hours=i))


@pytest.mark.asyncio
async def test_other_workspace_media_is_not_selected(db_session):
    await _seed(db_session, count=2)
    session_add = Media(
        id="foreign", userId="someone-else", businessProfileId="other-ws",
        filename="x.jpg", mimeType="image/jpeg",
        url="https://cdn.example.com/foreign.jpg",
        isActive=True, createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    db_session.add(session_add)
    await db_session.commit()

    for _ in range(3):
        chosen = await select_next_media(db_session, WORKSPACE)
        assert chosen.id != "foreign"
        await _record_post(db_session, chosen, datetime.now(timezone.utc))


@pytest.mark.asyncio
async def test_empty_catalog_returns_none(db_session):
    session_profile = BusinessProfile(
        id=WORKSPACE, userId=USER, name="Empty"
    )
    db_session.add(session_profile)
    await db_session.commit()
    assert await select_next_media(db_session, WORKSPACE) is None


# ─────────────────────────────────────────────────────────────────────────────
# Random order, without reintroducing the repeats that random.choice caused
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_the_feed_order_is_not_the_upload_order(db_session):
    """A bulk-imported folder posted strictly oldest-first goes out in
    filename order, which reads as mechanical. Over a full pass the sequence
    should differ from the catalog order at least sometimes."""
    await _seed(db_session, count=12)

    when = datetime(2026, 3, 1, tzinfo=timezone.utc)
    order = []
    for i in range(12):
        chosen = await select_next_media(db_session, WORKSPACE)
        order.append(chosen.url)
        await _record_post(db_session, chosen, when + timedelta(hours=i))

    from database import Media
    from sqlalchemy import select as _select
    catalog = [
        m.url for m in (await db_session.execute(
            _select(Media).where(Media.businessProfileId == WORKSPACE)
            .order_by(Media.createdAt.asc())
        )).scalars().all()
    ]
    # 12! orders exist; matching the catalog exactly is a 1-in-479-million
    # coincidence, so this is a real signal rather than a flaky one.
    assert order != catalog, "the pass ran in catalog order"


@pytest.mark.asyncio
async def test_random_order_still_never_repeats_within_a_pass(db_session):
    """The guarantee that made this module necessary. Naive random.choice
    repeats by birthday collision -- with six assets, better than even odds of
    a repeat inside four posts. Shuffling within the rotation must not bring
    that back."""
    await _seed(db_session, count=8)

    when = datetime(2026, 4, 1, tzinfo=timezone.utc)
    seen = []
    for i in range(8):
        chosen = await select_next_media(db_session, WORKSPACE)
        seen.append(chosen.url)
        await _record_post(db_session, chosen, when + timedelta(hours=i))

    assert len(set(seen)) == 8, f"an asset repeated before the pass finished: {seen}"


@pytest.mark.asyncio
async def test_recycling_never_picks_something_just_posted(db_session):
    """Randomness is drawn from the most-overdue band only, so the clip that
    went out last cannot come round again immediately."""
    await _seed(db_session, count=12)

    when = datetime(2026, 5, 1, tzinfo=timezone.utc)
    order = []
    for i in range(12):
        chosen = await select_next_media(db_session, WORKSPACE)
        order.append(chosen.url)
        await _record_post(db_session, chosen, when + timedelta(hours=i))

    most_recent = order[-1]
    for _ in range(5):
        nxt = await select_next_media(db_session, WORKSPACE)
        assert nxt.url != most_recent, "recycled the asset posted most recently"
