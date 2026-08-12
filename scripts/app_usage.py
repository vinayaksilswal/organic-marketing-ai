"""How throttled is the app right now, and is the block app-wide or per-account?

Meta reports usage in response headers rather than in a body, so a single
cheap GET carries the answer. Kept to ONE request because the thing being
measured is request volume.
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from sqlalchemy import select

from database import AsyncSessionLocal, BusinessProfile, SocialConnection, init_db
from services.crypto_service import decrypt_token

GRAPH = "https://graph.facebook.com/v21.0"


async def main() -> None:
    await init_db()

    async with AsyncSessionLocal() as session:
        row = (await session.execute(
            select(BusinessProfile, SocialConnection)
            .join(SocialConnection,
                  SocialConnection.businessProfileId == BusinessProfile.id)
            .where(BusinessProfile.name == "HollyVerse")
            .limit(1)
        )).first()

    profile, conn = row
    token = decrypt_token(conn.fbAccessToken)

    async with httpx.AsyncClient(timeout=45) as client:
        r = await client.get(
            f"{GRAPH}/{conn.fbPageId}", params={"access_token": token, "fields": "id"}
        )

    for header in ("x-app-usage", "x-business-use-case-usage", "x-ad-account-usage"):
        raw = r.headers.get(header)
        if not raw:
            continue
        print(f"\n{header}:")
        try:
            parsed = json.loads(raw)
        except Exception:
            print(f"  {raw}")
            continue

        if isinstance(parsed, dict) and header == "x-app-usage":
            print(f"  call volume   : {parsed.get('call_count')}% of the hourly limit")
            print(f"  cpu time      : {parsed.get('total_cputime')}%")
            print(f"  total time    : {parsed.get('total_time')}%")
        else:
            for key, entries in (parsed or {}).items():
                for entry in entries or []:
                    print(f"  {key}: type={entry.get('type')} "
                          f"calls={entry.get('call_count')}% "
                          f"cpu={entry.get('total_cputime')}% "
                          f"time={entry.get('total_time')}% "
                          f"reset_in={entry.get('estimated_time_to_regain_access')}min")

    if not any(h in r.headers for h in
               ("x-app-usage", "x-business-use-case-usage")):
        print("No usage headers returned.")
        print(f"status {r.status_code}: {r.text[:200]}")


if __name__ == "__main__":
    asyncio.run(main())
