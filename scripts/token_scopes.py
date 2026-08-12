"""What can each stored token actually DO?

Staging an unpublished photo and publishing a feed post need different
permissions, so "the upload worked" does not mean "the post would appear".
debug_token reports the granular scopes, including which page ids each one was
granted for -- Facebook's login flow lets a user grant a subset of their pages,
and a page left out of that subset behaves exactly like this: readable,
stageable, and unable to publish.
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

# The two that matter for publishing a page post and a reel.
KEY_SCOPES = ("pages_manage_posts", "pages_read_engagement",
              "instagram_basic", "instagram_content_publish",
              "pages_show_list", "business_management")


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
            if not conn.fbAccessToken:
                continue
            token = decrypt_token(conn.fbAccessToken)
            r = await client.get(
                f"{GRAPH}/debug_token",
                params={"input_token": token, "access_token": token},
            )
            body = r.json().get("data", {})
            if not body or "error" in r.json():
                print(f"{profile.name}: could not inspect token — "
                      f"{r.json().get('error', {}).get('message', 'no data')}")
                continue

            scopes = body.get("scopes") or []
            granular = body.get("granular_scopes") or []
            token_type = body.get("type")

            print(f"\n=== {profile.name} (page {conn.fbPageId}) ===")
            print(f"  token type: {token_type}")
            missing = [s for s in KEY_SCOPES if s not in scopes]
            print(f"  has: {', '.join(s for s in KEY_SCOPES if s in scopes) or 'none of the key scopes'}")
            if missing:
                print(f"  MISSING: {', '.join(missing)}")

            # Granular scopes are per-target, and the target is not always a
            # PAGE: the instagram_* scopes are granted against Instagram
            # account ids. Comparing those to fbPageId reports a false "not
            # granted" for an account that is in fact fully authorised.
            for entry in granular:
                scope = entry.get("scope")
                if scope not in ("pages_manage_posts", "instagram_content_publish",
                                 "pages_read_engagement"):
                    continue
                ids = entry.get("target_ids")
                expected = (
                    conn.igAccountId if scope.startswith("instagram_")
                    else conn.fbPageId
                )
                kind = "Instagram account" if scope.startswith("instagram_") else "page"
                if ids is None:
                    print(f"  {scope}: all targets")
                elif expected and expected in ids:
                    print(f"  {scope}: granted for THIS {kind} ({expected})")
                else:
                    print(f"  {scope}: NOT granted for this {kind} "
                          f"({expected}); granted for {ids}")


if __name__ == "__main__":
    asyncio.run(main())
