"""The system has to know what it already made, and refuse to repeat itself."""

from datetime import datetime, timedelta, timezone

import pytest

from database import BusinessProfile, Media
from services.prompt_history import (
    DUPLICATE_THRESHOLD,
    find_duplicate,
    generate_unique,
    recent_prompts,
    similarity,
)

WS = "ws-history"
USER = "u-history"

A = ('slow push-in 35mm: security lead in charcoal hoodie, cold coffee, in dim '
     'open-plan office. red alert banner reads "Vulnerable Keys Found"')
A_PARAPHRASE = ('slow push-in 35mm: security lead in a charcoal hoodie with cold '
                'coffee in a dim open-plan office. red banner reads "Vulnerable Keys Found"')
B = ('locked-off static: ceramic mug cooling on a workshop bench, morning light '
     'through sawdust. stamped maker mark reads "Ridgeline"')


def test_paraphrase_scores_high():
    assert similarity(A, A_PARAPHRASE) > DUPLICATE_THRESHOLD


def test_different_scenes_score_low():
    assert similarity(A, B) < DUPLICATE_THRESHOLD


def test_boilerplate_alone_is_not_similarity():
    """Every compiled prompt shares camera and framing vocabulary. If that
    counted, two unrelated scenes would look alike and nothing would pass."""
    x = "slow push-in 35mm, shallow depth of field, vertical 9:16 frame. a baker scoring sourdough"
    y = "slow push-in 35mm, shallow depth of field, vertical 9:16 frame. a welder lowering a visor"
    assert similarity(x, y) < DUPLICATE_THRESHOLD


def test_find_duplicate_returns_the_worst_match():
    hit = find_duplicate(A_PARAPHRASE, [B, A])
    assert hit is not None
    prior, score = hit
    assert prior == A and score > DUPLICATE_THRESHOLD


def test_find_duplicate_returns_none_when_distinct():
    assert find_duplicate(B, [A]) is None


def test_empty_history_never_flags():
    assert find_duplicate(A, []) is None


@pytest.mark.asyncio
async def test_recent_prompts_reads_only_this_workspace(db_session):
    db_session.add(BusinessProfile(id=WS, userId=USER, name="T"))
    db_session.add(BusinessProfile(id="other", userId="someone", name="O"))
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i, (ws, text) in enumerate([(WS, A), (WS, B), ("other", "not mine")]):
        db_session.add(Media(
            id=f"p{i}", userId=USER, businessProfileId=ws,
            filename="prompt.txt", mimeType="text/plain", url="",
            prompt=text, promptType="video",
            createdAt=base + timedelta(hours=i),
        ))
    await db_session.commit()

    got = await recent_prompts(db_session, WS)
    assert len(got) == 2
    assert "not mine" not in got
    assert got[0] == B  # newest first


@pytest.mark.asyncio
async def test_recent_prompts_ignores_non_video_rows(db_session):
    db_session.add(BusinessProfile(id=WS, userId=USER, name="T"))
    db_session.add(Media(
        id="img", userId=USER, businessProfileId=WS, filename="a.jpg",
        mimeType="image/jpeg", url="https://cdn/a.jpg",
        prompt="an image prompt", promptType="image",
    ))
    await db_session.commit()
    assert await recent_prompts(db_session, WS) == []


@pytest.mark.asyncio
async def test_generate_unique_retries_until_distinct():
    """The whole point: a repeat is regenerated, not published."""
    outputs = iter([A_PARAPHRASE, A_PARAPHRASE, B])

    async def gen(history):
        return next(outputs)

    prompt, report = await generate_unique(gen, [A])
    assert prompt == B
    assert report["unique"] is True
    assert report["attempts"] == 3
    assert len(report["rejected"]) == 2


@pytest.mark.asyncio
async def test_generate_unique_falls_back_rather_than_returning_nothing():
    """A slightly repetitive post beats a silent gap in the schedule, but the
    report must say it happened."""
    async def gen(history):
        return A_PARAPHRASE

    prompt, report = await generate_unique(gen, [A], attempts=2)
    assert prompt == A_PARAPHRASE
    assert report["unique"] is False
    assert report["attempts"] == 2


@pytest.mark.asyncio
async def test_generate_unique_accepts_first_when_already_distinct():
    calls = []

    async def gen(history):
        calls.append(1)
        return B

    prompt, report = await generate_unique(gen, [A])
    assert prompt == B and len(calls) == 1 and report["unique"] is True


@pytest.mark.asyncio
async def test_rejected_attempt_is_fed_back_so_it_is_not_repeated():
    seen = []

    async def gen(history):
        seen.append(list(history))
        return A_PARAPHRASE if len(seen) == 1 else B

    await generate_unique(gen, [A])
    assert A_PARAPHRASE in seen[1], "the rejected attempt was not fed back"
