"""Find, and optionally delete, live posts whose captions contain a URL.

A raw link in an Instagram caption is not clickable. It reads as spam to a
human, it is dead weight to the algorithm, and it is one of the clearer
automation tells an account can send. The generator has stripped URLs for a
while via _strip_urls, so anything still carrying one was published before
that guard or slipped past it.

Reads captions from Instagram itself rather than from our post table, so posts
made by any route are covered.

Dry run by default. Pass --apply to delete.
"""

import argparse
import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from sqlalchemy import select

from database import (
    AsyncSessionLocal, BusinessProfile, SocialConnection, init_db,
)
from services.crypto_service import decrypt_token

GRAPH = "https://graph.facebook.com/v21.0"
SCAN_LIMIT = 100

# A bare domain counts too: "quantcai.com" is as unclickable as the full URL.
URL_PATTERN = re.compile(
    r"(https?://\S+|www\.\S+|\b[a-z0-9-]+\.(?:com|io|in|net|org|ai|co|app|dev|shop|store)\b)",
    re.IGNORECASE,
)

# Phrases that merely REFER to a link are fine and must not be caught --
# "link in bio" is the correct call to action on Instagram.
ALLOWED = re.compile(r"link in bio", re.IGNORECASE)


def urls_in(caption: str):
    text = ALLOWED.sub("", caption or "")
    return URL_PATTERN.findall(text)


from services.post_protection import is_protected, refusal_reason


async def _read_views(client, media_id: str, token: str):
    """Views for one post, or None when they cannot be read.

    None is protective here: a post that cannot be measured cannot be shown to
    have failed, and this script deletes irreversibly.
    """
    try:
        body = (await client.get(
            f"{GRAPH}/{media_id}/insights",
            params={"access_token": token, "metric": "views,reach"},
        )).json()
    except Exception:
        return None
    if not body or "error" in body:
        return None
    values = {
        row.get("name"): (row.get("values") or [{}])[0].get("value")
        for row in body.get("data", [])
    }
    for metric in ("views", "reach"):
        v = values.get(metric)
        if isinstance(v, int):
            return v
    return None


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--business", help="limit to one business")
    args = ap.parse_args()

    await init_db()

    async with AsyncSessionLocal() as session:
        rows = (await session.execute(
            select(BusinessProfile, SocialConnection)
            .join(SocialConnection,
                  SocialConnection.businessProfileId == BusinessProfile.id)
            .order_by(BusinessProfile.name)
        )).all()

    total_found = total_deleted = total_protected = 0

    async with httpx.AsyncClient(timeout=90) as client:
        for profile, conn in rows:
            if args.business and profile.name != args.business:
                continue
            if not conn.igAccountId or not conn.fbAccessToken:
                continue
            token = decrypt_token(conn.fbAccessToken)

            body = (await client.get(
                f"{GRAPH}/{conn.igAccountId}/media",
                params={
                    "access_token": token,
                    "fields": "id,caption,permalink,timestamp",
                    "limit": SCAN_LIMIT,
                },
            )).json()
            if "error" in body:
                print(f"{profile.name}: could not list media — "
                      f"{body['error'].get('message')}")
                continue

            offenders = []
            for post in body.get("data", []) or []:
                found = urls_in(post.get("caption") or "")
                if found:
                    offenders.append((post, found))

            if not offenders:
                continue

            print(f"\n=== {profile.name}: {len(offenders)} post(s) with a URL ===")
            total_found += len(offenders)

            for post, found in offenders:
                print(f"  {post.get('permalink')}")
                print(f"    urls: {', '.join(sorted(set(found))[:4])}")

                # Reach outranks every other reason to delete.
                #
                # This script used to match on caption text and nothing else,
                # and it deleted fifty-four posts in one run -- including a
                # reel that had reached four thousand views. A link in the
                # caption of a post that worked is a caption problem, and the
                # answer to a caption problem is never to destroy the reach.
                views = await _read_views(client, post["id"], token)
                if is_protected(views):
                    print(f"    KEPT — {refusal_reason(views)}")
                    total_protected += 1
                    continue

                if not args.apply:
                    continue

                response = await client.delete(
                    f"{GRAPH}/{post['id']}", params={"access_token": token}
                )
                payload = response.json() if response.content else {}
                if response.status_code < 400 and not payload.get("error"):
                    print("    DELETED")
                    total_deleted += 1
                else:
                    message = (payload.get("error") or {}).get("message", "")
                    print(f"    could not delete: {message[:90]}")
                await asyncio.sleep(2)

    print(f"\n{total_found} post(s) carry a URL; {total_deleted} deleted.")
    if total_found and not args.apply:
        print("Dry run. Pass --apply to delete them.")


if __name__ == "__main__":
    asyncio.run(main())
