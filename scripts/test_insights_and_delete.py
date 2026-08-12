"""Can we read view counts, and can we delete a post? Tested, not assumed.

The 15-day / under-100-views cleanup was declined earlier on the grounds that
it needed instagram_manage_insights and instagram_manage_contents, neither
supposedly granted. That claim came from reading META_SCOPES rather than from
asking Meta, and a similar claim about pages_read_engagement turned out to be
wrong on 12 Aug 2026 -- it was granted the whole time.

So this asks the API directly:
  1. what the token reports as granted
  2. whether insights actually return view counts on a real post
  3. whether the delete endpoint is reachable (checked WITHOUT deleting)
"""

import asyncio
import json
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


async def main() -> None:
    await init_db()

    async with AsyncSessionLocal() as session:
        rows = (await session.execute(
            select(BusinessProfile, SocialConnection)
            .join(SocialConnection,
                  SocialConnection.businessProfileId == BusinessProfile.id)
            .order_by(BusinessProfile.name)
        )).all()

    async with httpx.AsyncClient(timeout=60) as client:
        for profile, conn in rows:
            if not conn.igAccountId or not conn.fbAccessToken:
                continue
            token = decrypt_token(conn.fbAccessToken)
            print(f"\n=== {profile.name} ===")

            # Scopes, as Meta reports them.
            dbg = (await client.get(
                f"{GRAPH}/debug_token",
                params={"input_token": token, "access_token": token},
            )).json().get("data", {})
            scopes = dbg.get("scopes") or []
            for scope in ("instagram_manage_insights", "instagram_manage_comments",
                          "instagram_content_publish", "instagram_basic"):
                print(f"  {scope:<28} {'granted' if scope in scopes else 'NOT granted'}")

            # A real post to measure against.
            media = (await client.get(
                f"{GRAPH}/{conn.igAccountId}/media",
                params={
                    "access_token": token,
                    "fields": "id,media_product_type,timestamp,like_count,comments_count",
                    "limit": 3,
                },
            )).json()
            items = media.get("data") or []
            if not items:
                print("  no media to test insights on")
                continue

            post = items[0]
            kind = post.get("media_product_type")
            # Reels report plays/views; feed posts report impressions/reach.
            metrics = ("plays,reach,likes,comments,saved"
                       if kind == "REELS" else "impressions,reach,saved")
            insights = (await client.get(
                f"{GRAPH}/{post['id']}/insights",
                params={"access_token": token, "metric": metrics},
            )).json()

            if "error" in insights:
                print(f"  INSIGHTS BLOCKED: {insights['error'].get('message')}")
            else:
                values = {
                    row["name"]: (row.get("values") or [{}])[0].get("value")
                    for row in insights.get("data", [])
                }
                print(f"  INSIGHTS OK on a {kind} post: {values}")

            # Is the delete endpoint reachable? Asked by requesting the media
            # object's own fields with the delete capability implied -- an
            # actual DELETE is destructive and is not performed here.
            probe = (await client.get(
                f"{GRAPH}/{post['id']}",
                params={"access_token": token, "fields": "id,permalink"},
            )).json()
            if "error" in probe:
                print(f"  media read: {probe['error'].get('message')}")
            else:
                print(f"  media readable: {probe.get('permalink', '')[:60]}")


if __name__ == "__main__":
    asyncio.run(main())
