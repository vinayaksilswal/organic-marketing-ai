"""A hashtag set per business, and the rotation that uses it.

Hashtags are one of the few distribution levers that work for an account with
no audience. A post from a page with 40 followers reaches almost nobody through
the follower graph; the hashtag and Explore surfaces are how a stranger sees it
at all. That makes this worth doing properly for a platform whose customers all
start from zero.

Two things decide whether a hashtag set earns anything.

SIZE TIERS. A tag with ten million posts buries a new post in seconds; a tag
with two hundred has nobody looking at it. The mix that works puts most of the
weight on tags small enough to rank in and large enough to have an audience,
with a few large ones for the chance of a spike. The tiers here are broad,
medium, niche and micro, and a caption draws from all four.

ROTATION. Instagram permits 30 tags and the same 30 on every post is the
clearest automation signal an account can send. Each caption gets a fresh
sample, seeded on the asset so a repost of the same clip keeps its tags.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
from typing import Any, Dict, List, Optional

from loguru import logger

# Instagram's hard limit is 30. Reach flattens well below that and a wall of
# tags reads as spam to a human, which is the audience that matters.
TAGS_PER_POST = 12

# How many of each tier a single caption carries. Weighted toward the tiers a
# new account can actually rank in.
TIER_MIX = {"broad": 2, "medium": 4, "niche": 4, "micro": 2}

TARGET_TOTAL = 100


def _clean(tag: str) -> Optional[str]:
    """Normalise one tag, or None if it cannot be used.

    Instagram silently drops a malformed tag rather than erroring, so a caption
    can lose half its reach without anything looking wrong.
    """
    if not tag:
        return None
    tag = tag.strip().lstrip("#").strip()
    tag = re.sub(r"[^0-9A-Za-z_]", "", tag)
    if not tag or len(tag) > 60:
        return None
    # A tag of only digits is not searchable.
    if tag.isdigit():
        return None
    return "#" + tag


def normalise(raw: Any) -> Dict[str, List[str]]:
    """Coerce whatever the model returned into clean, deduplicated tiers."""
    tiers: Dict[str, List[str]] = {k: [] for k in TIER_MIX}
    seen: set = set()

    if isinstance(raw, dict):
        for tier in tiers:
            for tag in raw.get(tier, []) or []:
                cleaned = _clean(tag if isinstance(tag, str) else "")
                if cleaned and cleaned.lower() not in seen:
                    seen.add(cleaned.lower())
                    tiers[tier].append(cleaned)
    elif isinstance(raw, list):
        # A flat list still beats nothing; spread it across the tiers so the
        # rotation below keeps working.
        cleaned_all = []
        for tag in raw:
            cleaned = _clean(tag if isinstance(tag, str) else "")
            if cleaned and cleaned.lower() not in seen:
                seen.add(cleaned.lower())
                cleaned_all.append(cleaned)
        names = list(tiers)
        for i, tag in enumerate(cleaned_all):
            tiers[names[i % len(names)]].append(tag)

    return tiers


def _prompt(profile: Any, intelligence: Optional[dict]) -> str:
    pillars = ", ".join(getattr(profile, "contentPillars", None) or [])
    intel = ""
    if intelligence:
        intel = json.dumps(
            {k: v for k, v in intelligence.items() if not str(k).startswith("_")}
        )[:1500]

    return f"""Build a hashtag set for this business's Instagram and Facebook posts.

BUSINESS
Name: {getattr(profile, 'name', '')}
What it is: {(getattr(profile, 'description', '') or '')[:900]}
Niche: {getattr(profile, 'niche', '') or 'unspecified'}
Audience: {(getattr(profile, 'targetAudience', '') or '')[:300]}
Content pillars: {pillars}
{f'Brand research: {intel}' if intel else ''}

Return exactly {TARGET_TOTAL} hashtags split into four tiers by how many posts
already exist under each tag:

  broad   (12 tags)  over 5 million posts. Big reach, buries a new post fast.
  medium  (28 tags)  500k to 5 million. Real audience, still competitive.
  niche   (40 tags)  50k to 500k. Where an account with no following can rank.
  micro   (20 tags)  under 50k. Small, specific, high intent.

Rules:
- Tags a real person searching for THIS content would follow or browse.
- No banned or adult tags, nothing that would restrict the account.
- No spaces or punctuation; letters, numbers and underscores only.
- Do not include the leading #.
- Vary them: describe the subject, the aesthetic, the audience and the
  outcome, not fifty rewordings of the business name.

Return ONLY JSON: {{"broad": [...], "medium": [...], "niche": [...], "micro": [...]}}"""


async def generate_for(profile: Any, intelligence: Optional[dict] = None) -> Dict[str, List[str]]:
    """Ask the model for a tiered set. Returns empty tiers on failure.

    Never raises: a business that cannot get hashtags should still be created,
    and captions fall back to the profile's own suggestedHashtags.
    """
    from services.ai_service import _call_openrouter

    try:
        raw = await _call_openrouter(_prompt(profile, intelligence), json_response=True)
        data = json.loads(raw) if isinstance(raw, str) else raw
        tiers = normalise(data)
    except Exception as e:
        logger.warning(f"Hashtag generation failed for {getattr(profile, 'name', '?')}: {e}")
        return {k: [] for k in TIER_MIX}

    total = sum(len(v) for v in tiers.values())
    logger.info(
        f"Hashtags for {getattr(profile, 'name', '?')}: {total} across "
        + ", ".join(f"{k}={len(v)}" for k, v in tiers.items())
    )
    return tiers


def brand_tag(profile: Any) -> Optional[str]:
    """The business's own name as a hashtag, or None if it cannot be one.

    Every post carries this. A branded tag is the only hashtag on a post that
    is guaranteed to be uncontested -- nobody else is competing for
    #Lumively -- so it is the one place an account can reliably be found, and
    it collects the account's whole body of work in one tappable place.

    Derived from the name rather than stored, so renaming a business renames
    its tag and there is no second copy to fall out of step.
    """
    return _clean((getattr(profile, "name", "") or "").replace(" ", ""))


def ensure_brand_tag(caption: str, profile: Any) -> str:
    """Guarantee the brand tag is in this caption, appending it if absent.

    Applied to the finished text rather than asked of the model. The prompt
    can request it and usually gets it, but "usually" across thousands of
    automated posts means a steady trickle without it, and the whole value of
    a branded tag is that it is on everything.
    """
    tag = brand_tag(profile)
    if not tag:
        return caption
    if tag.lower() in (caption or "").lower():
        return caption

    body = (caption or "").rstrip()
    # Onto the existing hashtag line when there is one, so the caption does
    # not grow a second block of tags.
    lines = body.split("\n")
    if lines and lines[-1].lstrip().startswith("#"):
        lines[-1] = f"{lines[-1].rstrip()} {tag}"
        return "\n".join(lines)
    return f"{body}\n\n{tag}" if body else tag


def select(tiers: Dict[str, List[str]], seed: str = "", count: int = TAGS_PER_POST) -> List[str]:
    """A fresh mix for one caption.

    Seeded on the asset rather than random, so the same clip reposted later
    carries the same tags -- a set that changes under a repeat makes it
    impossible to tell whether the tags or the creative moved the numbers.
    """
    if not any(tiers.values()):
        return []

    rng = random.Random(
        int(hashlib.sha256((seed or "").encode("utf-8", "replace")).hexdigest(), 16)
    )
    chosen: List[str] = []
    for tier, want in TIER_MIX.items():
        available = list(tiers.get(tier) or [])
        if not available:
            continue
        rng.shuffle(available)
        chosen.extend(available[:want])

    # Top up from anything left if a tier was thin, so a sparse set still
    # produces a full caption.
    if len(chosen) < count:
        rest = [t for tier in tiers.values() for t in tier if t not in chosen]
        rng.shuffle(rest)
        chosen.extend(rest[: count - len(chosen)])

    rng.shuffle(chosen)
    return chosen[:count]
