"""What is actually on each Instagram account, newest first?

The database records what this platform attempted. This reads what Instagram
itself holds, which also catches posts made by hand in the app -- and settles
whether any image has landed recently by any route.
"""

import asyncio
import sys
from datetime import datetime, timezone
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
    now = datetime.now(timezone.utc)

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
            body = (await client.get(
                f"{GRAPH}/{conn.igAccountId}/media",
                params={
                    "access_token": token,
                    "fields": "id,media_type,media_product_type,timestamp,"
                              "like_count,comments_count,permalink",
                    "limit": 8,
                },
            )).json()
            items = body.get("data") or []

            print(f"\n=== {profile.name} — {len(items)} most recent on Instagram ===")
            newest_image = None
            for m in items:
                try:
                    when = datetime.fromisoformat(
                        (m.get("timestamp") or "").replace("Z", "+00:00")
                    )
                    age = (now - when).total_seconds() / 3600
                    ago = f"{age:>5.1f}h ago"
                except Exception:
                    ago = "        ?"
                    age = None

                kind = m.get("media_product_type") or m.get("media_type")
                is_image = m.get("media_type") in ("IMAGE", "CAROUSEL_ALBUM")
                if is_image and newest_image is None and age is not None:
                    newest_image = age
                print(f"  {ago}  {str(kind):<8} {str(m.get('media_type')):<15} "
                      f"likes={m.get('like_count')} comments={m.get('comments_count')}")

            if newest_image is None:
                print("  no image or carousel in the recent window at all")
            else:
                print(f"  -> most recent IMAGE/CAROUSEL: {newest_image:.1f}h ago")


if __name__ == "__main__":
    asyncio.run(main())
