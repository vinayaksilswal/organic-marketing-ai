"""How much of Instagram's publishing quota has each account used?

The Content Publishing API allows 25 published posts per rolling 24 hours per
account. Past that, containers still upload and still reach FINISHED -- the
refusal happens only at media_publish. That failure is indistinguishable from
a bad file unless you ask for the quota directly.

BollyVerse is configured to post hourly, which is 24 a day against a cap of 25.
"""

import asyncio
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
            r = await client.get(
                f"{GRAPH}/{conn.igAccountId}/content_publishing_limit",
                params={
                    "access_token": token,
                    "fields": "config,quota_usage",
                },
            )
            body = r.json()
            if "error" in body:
                print(f"{profile.name:<22} error: {body['error'].get('message')}")
                continue

            data = (body.get("data") or [{}])[0]
            used = data.get("quota_usage")
            cap = (data.get("config") or {}).get("quota_total", 25)
            flag = ""
            if used is not None and cap:
                if used >= cap:
                    flag = "  <-- AT THE CAP, publishing is refused"
                elif used >= cap * 0.8:
                    flag = "  <-- close to the cap"
            print(f"{profile.name:<22} {used}/{cap} posts used in the last 24h{flag}")


if __name__ == "__main__":
    asyncio.run(main())
