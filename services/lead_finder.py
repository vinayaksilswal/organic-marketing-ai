"""Finding the people in your comments who were trying to buy something.

Organic marketing is judged on customers, not reach, and the shortest path
from a post to a customer is somebody who already asked a question in public
and never got an answer. Those are sitting in the comments of accounts this
platform posts to, and nothing was reading them.

WHY THIS IS PATTERN MATCHING AND NOT A MODEL
--------------------------------------------
A model could classify intent more subtly. It would also cost a call per
comment, take seconds per account, fail open on a rate-limited free tier, and
give a different answer on Tuesday than it gave on Monday for the same text.

Worse, it would be unexplainable. "We think this person wants to buy" is worth
nothing to somebody deciding whether to spend ten minutes replying. "They
asked 'how much', and nobody answered" is worth acting on immediately, and the
customer can check it in one click.

So every lead here carries the exact phrase that flagged it. If the match is
wrong, it is visibly wrong, which is the property that matters most in a
feature whose whole job is to be trusted enough to act on.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
It does not read direct messages. That needs instagram_manage_messages, which
is a different permission and a much larger consent for a customer to give,
and a tool that quietly read someone's DMs after they connected an account for
publishing would deserve to lose them.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# Ordered by how close the person is to buying. The first pattern that matches
# decides the lead's kind, so price beats a generic question.
SIGNALS: List[tuple] = [
    (
        "price",
        "asked what it costs",
        [
            r"\bhow much\b", r"\bprice\b", r"\bpricing\b", r"\bcost[s]?\b",
            r"\bcharge[s]?\b", r"\brate[s]?\b", r"\bkitna\b", r"\bkitne\b",
            r"\bfees?\b", r"\bquote\b", r"₹", r"\$\d",
        ],
    ),
    (
        "buy",
        "asked how to buy",
        [
            r"\bhow (?:do|can) i (?:buy|order|get|book)\b", r"\bwhere (?:can|do) i (?:buy|get)\b",
            r"\border\b", r"\bbuy\b", r"\bpurchase\b", r"\bbook(?:ing)?\b",
            r"\bsign ?up\b", r"\bsubscribe\b", r"\bcheckout\b",
        ],
    ),
    (
        "availability",
        "asked whether it is available",
        [
            r"\bin stock\b", r"\bavailable\b", r"\bavailability\b", r"\bdo you have\b",
            r"\bstill (?:have|selling|open)\b", r"\bdelivery\b", r"\bship(?:ping)? to\b",
        ],
    ),
    (
        "contact",
        "asked to be contacted",
        [
            r"\bdm\b", r"\bdm'?d\b", r"\bmessage[d]? you\b", r"\bwhat'?s ?app\b",
            r"\bwhatsapp\b", r"\bemail\b", r"\bcontact\b", r"\bcall me\b",
            r"\bnumber\b", r"\breach you\b", r"\binbox\b",
        ],
    ),
    (
        "interest",
        "said they want it",
        [
            r"\binterested\b", r"\bi want\b", r"\bi need\b", r"\bwhere\b.*\bfind\b",
            r"\bcan you (?:do|make|help)\b", r"\blooking for\b", r"\bneed this\b",
        ],
    ),
]

_COMPILED = [
    (kind, why, [re.compile(p, re.I) for p in patterns])
    for kind, why, patterns in SIGNALS
]

# A bare question mark is weak on its own, but a question nobody answered is
# still worth showing once the stronger kinds are exhausted.
_QUESTION = re.compile(r"\?")


def classify(text: str) -> Optional[Dict[str, str]]:
    """What this comment appears to want, and the phrase that says so.

    Returns None for ordinary appreciation. "🔥🔥" and "love this" are nice
    and are not leads, and a tool that called them leads would waste the
    customer's afternoon and stop being opened.
    """
    body = (text or "").strip()
    if not body:
        return None

    for kind, why, patterns in _COMPILED:
        for pattern in patterns:
            found = pattern.search(body)
            if found:
                return {
                    "kind": kind,
                    "why": why,
                    # The exact phrase, so a wrong match is obviously wrong.
                    "matched": found.group(0),
                }

    if _QUESTION.search(body) and len(body) > 8:
        return {"kind": "question", "why": "asked a question", "matched": "?"}

    return None


# Sort order: how much money is plausibly on the other end of a reply.
_PRIORITY = {"price": 0, "buy": 1, "availability": 2, "contact": 3, "interest": 4, "question": 5}


def from_accounts(accounts: List[dict]) -> Dict[str, Any]:
    """Read every comment already fetched for these accounts and pick out the
    ones that were trying to start a transaction."""
    leads: List[dict] = []
    comments_seen = 0

    for account in accounts or []:
        handle = (account.get("handle") or "").lower()

        for post in (account.get("posts") or []):
            for comment in (post.get("comments_list") or []):
                text = comment.get("text") or ""
                author = (comment.get("username") or "").lower()

                # Our own replies are not leads.
                if author and handle and author == handle:
                    continue

                comments_seen += 1
                verdict = classify(text)
                if not verdict:
                    continue

                # A question the business already answered is handled. The one
                # nobody replied to is the whole point of this screen.
                # Graph nests replies as {"data": [...]}, not a bare list.
                # Reading it as a list would mark every lead unanswered and
                # send the customer to re-reply to people they already helped.
                replies = (comment.get("replies") or {})
                replies = replies.get("data", []) if isinstance(replies, dict) else replies
                replied = any(
                    (r.get("username") or "").lower() == handle for r in replies
                ) if handle else bool(replies)

                leads.append({
                    "platform": account.get("platform"),
                    "account": account.get("handle"),
                    "who": comment.get("username"),
                    "text": text[:300],
                    "kind": verdict["kind"],
                    "why": verdict["why"],
                    "matched": verdict["matched"],
                    "answered": replied,
                    "postPermalink": post.get("permalink"),
                    "postCaption": (post.get("caption") or "")[:90],
                    "at": comment.get("timestamp"),
                })

    # Unanswered first, then by how close to buying, then newest.
    leads.sort(key=lambda l: (
        l["answered"],
        _PRIORITY.get(l["kind"], 9),
        -(len(l.get("at") or "")),
        l.get("at") or "",
    ))

    unanswered = [l for l in leads if not l["answered"]]

    return {
        "leads": leads,
        "total": len(leads),
        "unanswered": len(unanswered),
        "commentsScanned": comments_seen,
        # Stated so an empty result reads as "we looked" rather than "this is
        # broken" -- which for a young account is the common and correct case.
        "summary": _summary(len(leads), len(unanswered), comments_seen),
    }


def _summary(total: int, unanswered: int, scanned: int) -> str:
    if scanned == 0:
        return (
            "No comments to read yet. Leads show up here the moment somebody "
            "asks a question under one of your posts."
        )
    if total == 0:
        return (
            f"Read {scanned} comments. None of them asked about price, "
            f"availability or how to buy — so there is nothing waiting on you."
        )
    if unanswered == 0:
        return f"{total} people asked about buying, and you answered all of them."
    return (
        f"{unanswered} of {total} people who asked about buying are still "
        f"waiting for a reply."
    )
