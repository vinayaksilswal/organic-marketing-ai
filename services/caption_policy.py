"""Refuse to publish a caption that would put the Meta app at risk.

Seventy-eight published captions on this account described the pages as adult
content in plain text -- "We generate fully licensed Bollywood NSFW via AI",
hashtagged #NSFWContent and #AdultAI. Meta's sexual solicitation policy acts on
text alone; it does not need to assess the imagery to restrict an account.

The brand profiles that produced those captions have been rewritten, which
removes the cause. This is the backstop, and it exists because the cause can
come back in ways the profile does not control: a customer types their own
business description, a model free-associates from a suggestive asset caption,
or someone restores an old profile from a backup.

The consequence is not confined to one account. Meta scores an app on the
aggregate behaviour of everything published through it, so one workspace's
captions can cost API access for every customer on the platform.

Deliberately narrow. This is not a content moderator and it is not trying to
judge whether imagery is appropriate -- it matches terms that unambiguously
declare adult content in a caption, which is the specific thing that gets an
app actioned. Anything broader would start rejecting legitimate copy, and a
filter that mangles real captions gets switched off.
"""

from __future__ import annotations

import os
import re
from typing import List, Tuple

from loguru import logger

# Terms that assert adult content rather than merely appearing near it.
# Matched on word boundaries, so "adulthood" and "explicitly" do not trip it.
_PROHIBITED = [
    "nsfw", "porn", "porno", "xxx", "onlyfans", "nudes", "nude", "erotic",
    "erotica", "explicit content", "18+", "sexual", "sexy", "seductive",
    "lingerie", "fetish",
    # "adult" is only a problem in company. Listing the compounds rather than
    # the bare word is what lets "adult education" and "adulthood" through --
    # a filter that blocks those gets turned off, and then it protects nothing.
    # Every one of these appeared in a caption this platform actually published.
    "adult content", "adult ai", "adult film", "adult industry",
    "adult entertainment", "adult media", "adult tech", "adult platform",
]

# Extendable per deployment without a code change, because the list that keeps
# an app alive is not the same in every market.
_EXTRA = [t.strip().lower() for t in os.getenv("CAPTION_BLOCKED_TERMS", "").split(",") if t.strip()]

_PATTERNS = [
    (t, re.compile(rf"(?<![a-z0-9]){re.escape(t)}(?![a-z0-9])", re.IGNORECASE))
    for t in _PROHIBITED + _EXTRA
]


def find_violations(caption: str) -> List[str]:
    """Prohibited terms present in this caption, hashtags included."""
    if not caption:
        return []
    # "#NSFWContent" has no word boundary before NSFW, so hashtags are split
    # into their words before matching or the most common case slips through.
    #
    # Two splits are needed, not one. The obvious rule -- lowercase followed by
    # uppercase -- handles "#AdultContent" but not "#NSFWContent", where the
    # boundary sits between two capitals (W then C). That was the exact form in
    # the captions this was written for, so the single rule caught nothing that
    # mattered.
    searchable = re.sub(r"[#_]", " ", caption)
    searchable = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", searchable)
    searchable = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", searchable)
    return sorted({term for term, pat in _PATTERNS if pat.search(searchable)})


def is_publishable(caption: str) -> bool:
    return not find_violations(caption)


def enforce(caption: str, fallback: str = "", *, workspace: str = "") -> Tuple[str, List[str]]:
    """Return a caption safe to publish, and what was wrong with the original.

    Falls back to the asset's own description, which is written by the vision
    model from the picture itself and carries none of the positioning language
    that causes this. If the fallback is also unusable the caller gets an empty
    string and should not publish -- posting nothing costs one slot in a
    schedule, and posting this costs the app.
    """
    violations = find_violations(caption)
    if not violations:
        return caption, []

    logger.warning(
        f"Caption blocked before publishing"
        + (f" for {workspace}" if workspace else "")
        + f": contains {violations}. Meta's sexual solicitation policy acts on "
        f"caption text alone, and the app's standing is shared by every "
        f"workspace on it."
    )

    if fallback and not find_violations(fallback):
        return fallback, violations

    return "", violations
