"""Folders publish as one carousel, not as N separate posts."""

import uuid

import pytest
from sqlalchemy import select

from database import Media, MediaFolder, SocialPost
from services.media_rotation import expand_to_group, select_next_media

WORKSPACE = "ws-folders"


def _media(url, folder_id=None, position=0, mime="image/jpeg"):
    return Media(
        id=str(uuid.uuid4()),
        filename=url.split("/")[-1],
        mimeType=mime,
        url=url,
        isActive=True,
        businessProfileId=WORKSPACE,
        folderId=folder_id,
        folderPosition=position,
    )


async def _folder(session, name="Set", active=True):
    f = MediaFolder(
        id=str(uuid.uuid4()), name=name, isActive=active, businessProfileId=WORKSPACE
    )
    session.add(f)
    await session.flush()
    return f


@pytest.mark.asyncio
async def test_a_folder_counts_as_one_candidate_not_one_per_slide(db_session):
    """Six slides in a folder must not get six times a loose file's turns."""
    folder = await _folder(db_session)
    for i in range(6):
        db_session.add(_media(f"https://cdn/slide{i}.jpg", folder.id, i))
    loose = _media("https://cdn/loose.jpg")
    db_session.add(loose)
    await db_session.commit()

    # Over many draws a fair coin between two candidates never lands on one
    # side every time; a 6-vs-1 candidate split would.
    seen = set()
    for _ in range(40):
        chosen = await select_next_media(db_session, WORKSPACE, alternate_kinds=False)
        seen.add(chosen.id)
    assert loose.id in seen, "the loose file never won against one folder"


@pytest.mark.asyncio
async def test_only_the_first_slide_can_be_selected(db_session):
    folder = await _folder(db_session)
    first = _media("https://cdn/a.jpg", folder.id, 0)
    db_session.add(first)
    db_session.add(_media("https://cdn/b.jpg", folder.id, 1))
    db_session.add(_media("https://cdn/c.jpg", folder.id, 2))
    await db_session.commit()

    for _ in range(12):
        chosen = await select_next_media(db_session, WORKSPACE, alternate_kinds=False)
        assert chosen.id == first.id


@pytest.mark.asyncio
async def test_expanding_returns_every_slide_in_order(db_session):
    folder = await _folder(db_session)
    # Inserted out of order on purpose: order must come from folderPosition.
    db_session.add(_media("https://cdn/third.jpg", folder.id, 2))
    first = _media("https://cdn/first.jpg", folder.id, 0)
    db_session.add(first)
    db_session.add(_media("https://cdn/second.jpg", folder.id, 1))
    await db_session.commit()

    slides = await expand_to_group(db_session, first)
    assert [s.url for s in slides] == [
        "https://cdn/first.jpg", "https://cdn/second.jpg", "https://cdn/third.jpg",
    ]


@pytest.mark.asyncio
async def test_a_loose_file_expands_to_itself(db_session):
    loose = _media("https://cdn/solo.jpg")
    db_session.add(loose)
    await db_session.commit()
    assert await expand_to_group(db_session, loose) == [loose]


@pytest.mark.asyncio
async def test_a_folder_above_the_carousel_limit_is_truncated_not_rejected(db_session):
    """Instagram rejects a container over ten children outright.

    Posting the first ten is worse than posting fourteen and better than
    posting nothing, which is what sending all fourteen would achieve.
    """
    folder = await _folder(db_session)
    for i in range(14):
        db_session.add(_media(f"https://cdn/s{i:02d}.jpg", folder.id, i))
    await db_session.commit()

    first = (await db_session.execute(
        select(Media).where(Media.folderId == folder.id, Media.folderPosition == 0)
    )).scalars().first()
    slides = await expand_to_group(db_session, first)
    assert len(slides) == 10
    assert slides[0].url == "https://cdn/s00.jpg"


@pytest.mark.asyncio
async def test_a_paused_folder_is_skipped_entirely(db_session):
    """Pausing must remove the folder, not scatter its slides as loose files."""
    folder = await _folder(db_session, active=False)
    for i in range(3):
        db_session.add(_media(f"https://cdn/paused{i}.jpg", folder.id, i))
    loose = _media("https://cdn/live.jpg")
    db_session.add(loose)
    await db_session.commit()

    for _ in range(10):
        chosen = await select_next_media(db_session, WORKSPACE, alternate_kinds=False)
        assert chosen.id == loose.id


@pytest.mark.asyncio
async def test_a_workspace_of_only_paused_folders_selects_nothing(db_session):
    folder = await _folder(db_session, active=False)
    db_session.add(_media("https://cdn/only.jpg", folder.id, 0))
    await db_session.commit()
    assert await select_next_media(db_session, WORKSPACE, alternate_kinds=False) is None


@pytest.mark.asyncio
async def test_the_folder_is_not_reselected_while_a_loose_file_is_unused(db_session):
    """Rotation's no-repeat guarantee still holds with folders in the mix."""
    folder = await _folder(db_session)
    first = _media("https://cdn/f0.jpg", folder.id, 0)
    db_session.add(first)
    db_session.add(_media("https://cdn/f1.jpg", folder.id, 1))
    loose = _media("https://cdn/only-loose.jpg")
    db_session.add(loose)
    await db_session.commit()

    # Publish the folder, recording its first slide the way the worker does.
    db_session.add(SocialPost(
        id=str(uuid.uuid4()),
        businessProfileId=WORKSPACE,
        platform="ALL",
        caption="carousel",
        mediaUrls=[first.url, "https://cdn/f1.jpg"],
        status="POSTED",
    ))
    await db_session.commit()

    chosen = await select_next_media(db_session, WORKSPACE, alternate_kinds=False)
    assert chosen.id == loose.id


# --- The HTTP surface the dashboard actually calls -------------------------


async def _workspace(session, user_id="test-user", name="Folder Co"):
    from database import BusinessProfile

    ws = BusinessProfile(id=str(uuid.uuid4()), userId=user_id, name=name)
    session.add(ws)
    await session.commit()
    return ws


@pytest.mark.asyncio
async def test_create_move_and_read_back_a_folder(authed_client, db_session):
    client, _ = authed_client
    ws = await _workspace(db_session)
    headers = {"X-Workspace-Id": ws.id}

    a = _media("https://cdn/one.jpg")
    b = _media("https://cdn/two.jpg")
    for m in (a, b):
        m.businessProfileId = ws.id
        db_session.add(m)
    await db_session.commit()

    created = await client.post(
        "/api/v1/marketing/media/folders", json={"name": "Diwali set"}, headers=headers
    )
    assert created.status_code == 200, created.text
    folder_id = created.json()["id"]

    moved = await client.post(
        f"/api/v1/marketing/media/folders/{folder_id}/items",
        json={"mediaIds": [a.id, b.id]}, headers=headers,
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["moved"] == 2

    listed = await client.get("/api/v1/marketing/media/folders", headers=headers)
    body = listed.json()
    assert len(body) == 1
    assert body[0]["name"] == "Diwali set"
    assert body[0]["count"] == 2
    # Two slides is a valid carousel, so nothing to warn about.
    assert body[0]["warning"] is None
    assert [i["url"] for i in body[0]["items"]] == ["https://cdn/one.jpg", "https://cdn/two.jpg"]


@pytest.mark.asyncio
async def test_a_folder_of_one_says_it_will_not_be_a_carousel(authed_client, db_session):
    client, _ = authed_client
    ws = await _workspace(db_session, name="Single Co")
    headers = {"X-Workspace-Id": ws.id}

    solo = _media("https://cdn/solo.jpg")
    solo.businessProfileId = ws.id
    db_session.add(solo)
    await db_session.commit()

    folder_id = (await client.post(
        "/api/v1/marketing/media/folders", json={"name": "One"}, headers=headers
    )).json()["id"]
    moved = await client.post(
        f"/api/v1/marketing/media/folders/{folder_id}/items",
        json={"mediaIds": [solo.id]}, headers=headers,
    )
    assert "not a carousel" in moved.json()["warning"]


@pytest.mark.asyncio
async def test_deleting_a_folder_keeps_every_file(authed_client, db_session):
    """The destructive-sounding action must never destroy a business's media."""
    client, _ = authed_client
    ws = await _workspace(db_session, name="Keep Co")
    headers = {"X-Workspace-Id": ws.id}

    kept = _media("https://cdn/keep.jpg")
    kept.businessProfileId = ws.id
    db_session.add(kept)
    await db_session.commit()

    folder_id = (await client.post(
        "/api/v1/marketing/media/folders", json={"name": "Temp"}, headers=headers
    )).json()["id"]
    await client.post(
        f"/api/v1/marketing/media/folders/{folder_id}/items",
        json={"mediaIds": [kept.id]}, headers=headers,
    )

    deleted = await client.delete(
        f"/api/v1/marketing/media/folders/{folder_id}", headers=headers
    )
    assert deleted.status_code == 200
    assert deleted.json()["released"] == 1

    still_there = (await db_session.execute(
        select(Media).where(Media.id == kept.id)
    )).scalars().first()
    assert still_there is not None
    assert still_there.folderId is None


@pytest.mark.asyncio
async def test_a_folder_from_another_business_is_refused(authed_client, db_session):
    """A folder id alone must never be proof of ownership."""
    client, set_user = authed_client
    mine = await _workspace(db_session, user_id="test-user", name="Mine")
    theirs = await _workspace(db_session, user_id="other-user", name="Theirs")

    set_user("other-user")
    other_folder = (await client.post(
        "/api/v1/marketing/media/folders", json={"name": "Private"},
        headers={"X-Workspace-Id": theirs.id},
    )).json()["id"]

    set_user("test-user")
    refused = await client.delete(
        f"/api/v1/marketing/media/folders/{other_folder}",
        headers={"X-Workspace-Id": mine.id},
    )
    assert refused.status_code == 403

    survived = (await db_session.execute(
        select(MediaFolder).where(MediaFolder.id == other_folder)
    )).scalars().first()
    assert survived is not None


@pytest.mark.asyncio
async def test_a_folder_needs_a_name(authed_client, db_session):
    client, _ = authed_client
    ws = await _workspace(db_session, name="Nameless Co")
    res = await client.post(
        "/api/v1/marketing/media/folders", json={"name": "   "},
        headers={"X-Workspace-Id": ws.id},
    )
    assert res.status_code == 400
