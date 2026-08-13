"""Delete the diagnostic posts this session published by mistake.

Five posts reached live accounts while the API reported failure:

    HollyVerse  "Test pattern."
    HollyVerse  "Golden hour, quietly."          (twice)
    HollyVerse  "diagnostic, not published"
    quantcai    "Signal, not noise."

Whether the API can remove them is TESTED here rather than assumed. Instagram's
Content Publishing API is documented as publish-only, but that claim has been
wrong once already this session about a different permission, so it is worth
four seconds to ask.

Matches on the exact caption and nothing else, so no real post can be caught
by it. Pass --apply to attempt deletion; the default only lists what matched.
"""

import argparse
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

# Exact captions written by the diagnostic scripts. Nothing else may match.
DIAGNOSTIC_CAPTIONS = {
    "Test pattern.",
    "Golden hour, quietly.",
    "diagnostic, not published",
    "Signal, not noise.",
    "diagnostic container, not published",
    "geometry check, not published",
}


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

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

            body = (await client.get(
                f"{GRAPH}/{conn.igAccountId}/media",
                params={
                    "access_token": token,
                    "fields": "id,caption,permalink,timestamp",
                    "limit": 25,
                },
            )).json()

            targets = [
                m for m in (body.get("data") or [])
                if (m.get("caption") or "").strip() in DIAGNOSTIC_CAPTIONS
            ]
            if not targets:
                continue

            print(f"\n=== {profile.name}: {len(targets)} diagnostic post(s) ===")
            for m in targets:
                print(f"  {m['id']}  {m.get('permalink')}")
                print(f"    caption: {(m.get('caption') or '')[:60]}")

                if not args.apply:
                    continue

                r = await client.delete(
                    f"{GRAPH}/{m['id']}", params={"access_token": token}
                )
                payload = r.json() if r.content else {}
                if r.status_code < 400 and not payload.get("error"):
                    print(f"    DELETED")
                else:
                    error = (payload.get("error") or {})
                    print(f"    could not delete: HTTP {r.status_code} — "
                          f"{error.get('message', json.dumps(payload)[:120])}")

    if not args.apply:
        print("\nDry run. Pass --apply to attempt deletion.")


if __name__ == "__main__":
    asyncio.run(main())
