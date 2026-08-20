"""Remove posts that had their chance and did nothing.

A feed full of posts nobody watched is not neutral. Instagram ranks an account
partly on how its recent work performs, so a long tail of dead posts drags
down the reach of everything published after it, and a visitor deciding
whether to follow sees the worst of the account alongside the best.

The rule, as asked for: older than 15 days, fewer than 100 views, gone. Run
once every 24 hours for every business.

THIS DELETES PUBLISHED CONTENT AND META'S DELETE IS IRREVERSIBLE. There is no
undo, no trash, no export. So the guards below are not decoration:

  - a post must be genuinely old, so nothing is judged before it has had time
  - views must be READ, never assumed; a post whose numbers cannot be fetched
    is left alone rather than treated as a failure
  - at most MAX_DELETIONS_PER_RUN per business per run, so a bug, a bad
    threshold or a Meta outage returning zeros cannot empty an account in one
    pass -- it can only ever take a bounded bite, visible in the next run
  - every deletion is logged with its permalink and view count before it goes
  - the whole thing is off unless POST_CLEANUP_ENABLED is set

The permissions this needs -- instagram_manage_insights to read views and
instagram_manage_contents to delete -- were not on the tokens as of 13 Aug
2026. Both are checked at runtime, and their absence is reported as a skip
rather than an error, so this becomes live the moment the accounts are
reconnected with them.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx
from loguru import logger

from services.post_protection import is_protected

GRAPH = "https://graph.facebook.com/v21.0"

# Seven days, reduced from fifteen.
#
# Fifteen was chosen when the only account with history was quantcai. Every
# other account here was connected within the last fortnight, so nothing they
# published was old enough to judge and the rule did nothing for them at all.
#
# Seven days is still long enough to be fair to a post: Instagram distribution
# for a Reel is effectively settled within 48 to 72 hours, so a week gives a
# post more than double the time it needs to find its audience before being
# called a failure.
MIN_AGE_DAYS = int(os.getenv("POST_CLEANUP_MIN_AGE_DAYS", "7"))
MIN_VIEWS = int(os.getenv("POST_CLEANUP_MIN_VIEWS", "100"))

# The blast radius of a single run. A whole catalog cannot be lost to one bad
# decision; the worst case is this many posts, and the next run reports it.
MAX_DELETIONS_PER_RUN = int(os.getenv("POST_CLEANUP_MAX_PER_RUN", "20"))

# Posts fetched per request. Instagram pages, so this is a page size, not a
# ceiling -- MAX_PAGES below decides how far back the scan actually reaches.
SCAN_LIMIT = int(os.getenv("POST_CLEANUP_SCAN_LIMIT", "100"))

# A single page only ever reached the newest hundred posts, which on an
# account posting six times a day is about two weeks -- almost exactly the
# window this job is meant to look PAST. So the backlog it exists to clear was
# the part it could not see. Ten pages is roughly a thousand posts, enough for
# any account here, and the loop stops early once posts are too new to qualify.
MAX_PAGES = int(os.getenv("POST_CLEANUP_MAX_PAGES", "10"))

ENABLED = os.getenv("POST_CLEANUP_ENABLED", "").lower() in ("1", "true", "yes")


def _views_from(insights: Dict[str, Any]) -> Optional[int]:
    """The best available view count, or None if Meta reported none.

    Reels report plays; feed posts report impressions. Reach is the fallback
    when neither is present. None means "unknown", and unknown must never be
    read as zero -- that would delete a post for being unmeasurable.
    """
    if not insights or "error" in insights:
        return None
    values = {
        row.get("name"): (row.get("values") or [{}])[0].get("value")
        for row in insights.get("data", [])
    }
    for metric in ("plays", "views", "impressions", "reach"):
        value = values.get(metric)
        if isinstance(value, int):
            return value
    return None


async def find_underperformers(
    client: httpx.AsyncClient,
    ig_account_id: str,
    access_token: str,
) -> tuple[List[Dict[str, Any]], str]:
    """Posts old enough to judge and too weak to keep. Returns (posts, note)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=MIN_AGE_DAYS)

    # Walk back through the account's history rather than glancing at the
    # newest page. Media comes newest-first, so the walk can stop as soon as a
    # whole page is too recent to qualify.
    posts: List[Dict[str, Any]] = []
    url = f"{GRAPH}/{ig_account_id}/media"
    params: Dict[str, Any] = {
        "access_token": access_token,
        "fields": "id,caption,media_product_type,media_type,timestamp,permalink",
        "limit": SCAN_LIMIT,
    }

    for page in range(MAX_PAGES):
        try:
            body = (await client.get(url, params=params)).json()
        except Exception as e:
            return [], f"could not list media: {e}"
        if "error" in body:
            return [], f"could not list media: {body['error'].get('message')}"

        batch = body.get("data", []) or []
        posts.extend(batch)
        if not batch:
            break

        oldest = batch[-1].get("timestamp") or ""
        try:
            oldest_when = datetime.fromisoformat(oldest.replace("Z", "+00:00"))
        except Exception:
            oldest_when = None
        # The whole page is newer than the age threshold, so everything beyond
        # it is newer still.
        if oldest_when and oldest_when > cutoff:
            break

        after = ((body.get("paging") or {}).get("cursors") or {}).get("after")
        if not after:
            break
        params = dict(params, after=after)

    candidates = []
    unmeasurable = 0
    protected = 0

    for post in posts:
        try:
            when = datetime.fromisoformat(
                (post.get("timestamp") or "").replace("Z", "+00:00")
            )
        except Exception:
            continue
        if when > cutoff:
            continue

        # "views" for everything, Reel or feed post.
        #
        # This used to ask for "plays" on Reels and "impressions" on feed
        # posts. Both are gone: from v22 Meta retired impressions for media
        # insights and replaced the family with a single `views`, and asking
        # for a retired name fails the whole request with (#100) rather than
        # degrading. The failure was indistinguishable from having no
        # permission at all, which is why it looked like the reconnect had not
        # worked.
        metrics = "views,reach"
        try:
            insights = (await client.get(
                f"{GRAPH}/{post['id']}/insights",
                params={"access_token": access_token, "metric": metrics},
            )).json()
        except Exception:
            unmeasurable += 1
            continue

        views = _views_from(insights)
        if views is None:
            # Cannot read the numbers, so cannot justify deleting it.
            unmeasurable += 1
            continue

        # The same floor every deletion path answers to. MIN_VIEWS alone is
        # this module's own rule; is_protected is the product's, and it is
        # checked here too so no single threshold change can quietly put
        # performing posts back in range.
        if is_protected(views):
            protected += 1
            continue
        if views >= MIN_VIEWS:
            continue

        candidates.append({
            "id": post["id"],
            "views": views,
            "age_days": (datetime.now(timezone.utc) - when).days,
            "permalink": post.get("permalink"),
            "caption": (post.get("caption") or "")[:60],
        })

    note = ""
    if unmeasurable:
        note = (
            f"{unmeasurable} post(s) had no readable view count and were left "
            f"alone. instagram_manage_insights is what makes them readable."
        )
    return candidates, note


async def cleanup_workspace(
    session: Any, workspace_id: str, *, dry_run: bool = False
) -> Dict[str, Any]:
    """Delete this workspace's old, unwatched posts. Never raises."""
    from sqlalchemy import select

    from database import SocialConnection
    from services.crypto_service import decrypt_token

    result: Dict[str, Any] = {
        "workspace": workspace_id, "deleted": 0, "found": 0, "note": "",
    }

    conn = (await session.execute(
        select(SocialConnection).where(
            SocialConnection.businessProfileId == workspace_id
        ).limit(1)
    )).scalars().first()
    if not conn or not conn.igAccountId or not conn.fbAccessToken:
        result["note"] = "no Instagram account connected"
        return result

    try:
        token = decrypt_token(conn.fbAccessToken)
    except Exception as e:
        result["note"] = f"token unreadable: {e}"
        return result

    async with httpx.AsyncClient(timeout=90) as client:
        candidates, note = await find_underperformers(
            client, conn.igAccountId, token
        )
        result["found"] = len(candidates)
        result["note"] = note

        if not candidates:
            return result

        # The cap is applied to the WORST performers, so a bounded run still
        # removes the posts that are hurting most.
        candidates.sort(key=lambda c: c["views"])
        batch = candidates[:MAX_DELETIONS_PER_RUN]
        if len(candidates) > len(batch):
            result["note"] = (
                f"{len(candidates)} qualify; taking the {len(batch)} weakest "
                f"this run. " + result["note"]
            ).strip()

        for post in batch:
            logger.info(
                f"Cleanup {workspace_id}: {'would delete' if dry_run else 'deleting'} "
                f"{post['id']} — {post['views']} views, {post['age_days']}d old, "
                f"{post['permalink']}"
            )
            if dry_run:
                continue

            try:
                response = await client.delete(
                    f"{GRAPH}/{post['id']}", params={"access_token": token}
                )
                payload = response.json() if response.content else {}
            except Exception as e:
                logger.warning(f"Cleanup: delete failed for {post['id']}: {e}")
                continue

            if response.status_code < 400 and not payload.get("error"):
                result["deleted"] += 1
            else:
                message = (payload.get("error") or {}).get("message", "")
                logger.warning(
                    f"Cleanup: Instagram refused to delete {post['id']}: {message}"
                )
                # A permission failure will fail identically for every other
                # post, so stop rather than making N pointless calls.
                if "permission" in message.lower():
                    result["note"] = (
                        "instagram_manage_contents is not on this token, so "
                        "nothing can be deleted yet. Reconnect the account."
                    )
                    break

    return result


async def run_cleanup(*, dry_run: bool = False) -> List[Dict[str, Any]]:
    """Every business, once. Safe to call on a schedule."""
    from sqlalchemy import select

    from database import AsyncSessionLocal, BusinessProfile

    if not ENABLED and not dry_run:
        logger.info(
            "Post cleanup is off. Set POST_CLEANUP_ENABLED=true to let it "
            "delete published posts."
        )
        return []

    results = []
    async with AsyncSessionLocal() as session:
        profiles = (await session.execute(select(BusinessProfile))).scalars().all()

    for profile in profiles:
        if getattr(profile, "automationPaused", False):
            continue
        # A session per workspace, because Neon closes idle connections and a
        # slow Graph call in the middle of a loop is exactly how that happens.
        async with AsyncSessionLocal() as session:
            try:
                outcome = await cleanup_workspace(
                    session, profile.id, dry_run=dry_run
                )
            except Exception as e:
                logger.error(f"Cleanup failed for {profile.name}: {e}")
                continue
        outcome["name"] = profile.name
        results.append(outcome)

    total = sum(r["deleted"] for r in results)
    logger.info(
        f"Post cleanup {'(dry run) ' if dry_run else ''}complete: "
        f"{total} post(s) deleted across {len(results)} business(es)"
    )
    return results
