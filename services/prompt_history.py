"""What this business has already been shown, so the next one is different.

Every video prompt is persisted to the Media catalog with promptType="video",
but nothing ever read them back: execute_video_pipeline was called without
`recent_prompts` on every path, so each run began with no memory. Combined with
a deterministic format pick, that produced a feed of near-identical scenes —
the same camera move, the same room, the same beat, over and over.

This module closes the loop. It reads the history, hands it to the writer as
material to avoid, and then refuses a result that came back too similar anyway.

Similarity is Jaccard over content words rather than embeddings. It needs no
model call, no API budget and no network hop on the generation path, and the
failure being caught is blunt — two prompts sharing most of their nouns — which
overlap catches perfectly well.
"""

from __future__ import annotations

import re
from typing import Any, List, Optional, Sequence, Tuple

from loguru import logger
from sqlalchemy import select

from database import Media

# Structural vocabulary every compiled prompt contains. Left in, two unrelated
# scenes look 40% alike purely from the scaffolding and nothing is ever novel.
_BOILERPLATE = {
    "slow", "push", "pull", "pan", "static", "locked", "off", "handheld",
    "gentle", "sway", "overhead", "descent", "shot", "lens", "mm", "camera",
    "frame", "vertical", "shallow", "depth", "field", "focus", "out", "soft",
    "large", "high", "contrast", "type", "reads", "holds", "single", "word",
    "final", "spoken", "aloud", "natural", "unhurried", "delivery", "the",
    "and", "with", "into", "onto", "from", "that", "this", "a", "an", "of",
    "in", "on", "at", "as", "is", "it", "its", "to", "for", "by", "one",
    "background", "signage", "product", "labels", "remain", "blank",
    "surrounding", "interface", "copy", "light", "lighting", "only",
}

# Above this, two prompts are the same idea in different words. Tuned against
# real output: genuinely distinct scenes from the live model land at 0.10-0.25,
# while a paraphrase of the previous run lands above 0.45.
DUPLICATE_THRESHOLD = 0.45

# How far back to look. Long enough to cover a fortnight of posting at the
# default two-hour interval, short enough that a brand can eventually revisit a
# setting it used months ago.
HISTORY_DEPTH = 25


def _content_words(text: str) -> set:
    words = re.findall(r"[a-z]{3,}", (text or "").lower())
    return {w for w in words if w not in _BOILERPLATE}


def similarity(a: str, b: str) -> float:
    """Jaccard overlap of content words. 0.0 unrelated, 1.0 identical."""
    wa, wb = _content_words(a), _content_words(b)
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


async def recent_prompts(
    session: Any, workspace_id: str, limit: int = HISTORY_DEPTH
) -> List[str]:
    """The video prompts this workspace has already generated, newest first."""
    stmt = (
        select(Media.prompt)
        .where(
            Media.businessProfileId == workspace_id,
            Media.promptType == "video",
            Media.prompt.isnot(None),
        )
        .order_by(Media.createdAt.desc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [r for r in rows if r and r.strip()]


def find_duplicate(
    candidate: str,
    history: Sequence[str],
    threshold: float = DUPLICATE_THRESHOLD,
) -> Optional[Tuple[str, float]]:
    """The most similar prior prompt, if any exceeds the threshold."""
    worst: Optional[Tuple[str, float]] = None
    for prior in history:
        score = similarity(candidate, prior)
        if score >= threshold and (worst is None or score > worst[1]):
            worst = (prior, score)
    return worst


async def generate_unique(
    generate,
    history: Sequence[str],
    attempts: int = 3,
    threshold: float = DUPLICATE_THRESHOLD,
) -> Tuple[Optional[str], dict]:
    """Call `generate` until it returns something unlike the history.

    `generate` is an async callable taking the history and returning a prompt
    string. Returns (prompt, report). On exhaustion the least-similar attempt
    is returned rather than nothing — a slightly repetitive post still beats a
    silent gap in the schedule, and the report says which happened so the
    caller can surface it.
    """
    report = {"attempts": 0, "rejected": [], "unique": False}
    best: Optional[Tuple[str, float]] = None

    for attempt in range(1, attempts + 1):
        report["attempts"] = attempt
        candidate = await generate(list(history))
        if not candidate:
            continue

        dup = find_duplicate(candidate, history, threshold)
        if not dup:
            report["unique"] = True
            return candidate, report

        prior, score = dup
        report["rejected"].append({"similarity": round(score, 3),
                                   "matched": prior[:120]})
        logger.info(
            f"Prompt attempt {attempt} was {score:.0%} similar to an earlier "
            f"one, regenerating"
        )
        if best is None or score < best[1]:
            best = (candidate, score)
        # Feed the rejected attempt back so the next try avoids it too.
        history = list(history) + [candidate]

    if best:
        logger.warning(
            f"Could not produce a distinct prompt in {attempts} attempts; "
            f"using the least similar at {best[1]:.0%}"
        )
        return best[0], report
    return None, report
