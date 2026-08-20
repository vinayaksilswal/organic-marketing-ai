"""A post that worked is never deleted by automation. Any automation.

post_cleanup was written carefully: it refuses to judge a post it cannot
measure, it will not touch anything under a week old, and it caps its own
blast radius. None of that protected a reel that reached four thousand views,
because the thing that deleted it was not post_cleanup.

purge_url_captions removes posts whose captions contain a link. It matched on
caption text and nothing else -- no views read, no threshold, no exemption --
and it deleted fifty-four posts in one run. A post that performed and happened
to carry a link was indistinguishable to it from a post that did neither.

That is the hole this closes. The rule is not "delete underperformers
carefully"; it is that REACH OUTRANKS EVERY OTHER REASON TO DELETE. A caption
with a link on a reel that reached four thousand people is a caption problem,
and the answer to a caption problem is never to destroy the reach.

Meta's delete is irreversible. There is no undo, no trash and no export, so
the guard is deliberately generous: anything that cleared a few hundred views
stays, whatever else is wrong with it.
"""

from __future__ import annotations

import os
from typing import Optional

# Three times the underperformance threshold. A post at this level is not a
# borderline case -- it found an audience, and an account is ranked partly on
# the work that did.
PROTECT_ABOVE_VIEWS = int(os.getenv("POST_PROTECT_ABOVE_VIEWS", "300"))


def is_protected(views: Optional[int]) -> bool:
    """Whether reach alone forbids deleting this post.

    None means the numbers could not be read, and unknown is protected too. A
    post that cannot be measured cannot be shown to have failed, and the cost
    of keeping a bad post is a fraction of the cost of destroying a good one.
    """
    if views is None:
        return True
    return views >= PROTECT_ABOVE_VIEWS


def refusal_reason(views: Optional[int]) -> str:
    """Why this post was kept, for the log the operator actually reads."""
    if views is None:
        return "views could not be read, so it was kept"
    return f"{views} views is above the {PROTECT_ABOVE_VIEWS} protection floor"
