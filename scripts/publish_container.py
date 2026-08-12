"""Publish one already-built container, and report the quota around it.

THIS PUBLISHES. It exists to settle whether media_publish refuses carousels
specifically, which is the one step carousel_isolate deliberately stops short
of. Reads the publishing quota immediately before and after, so a refusal can
be attributed to the quota or ruled out.
"""

import argparse
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


async def quota(client, ig_id, token):
    body = (await client.get(
        f"{GRAPH}/{ig_id}/content_publishing_limit",
        params={"access_token": token, "fields": "config,quota_usage"},
    )).json()
    data = (body.get("data") or [{}])[0]
    return data.get("quota_usage"), (data.get("config") or {}).get("quota_total")


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("container")
    ap.add_argument("--business", default="HollyVerse")
    args = ap.parse_args()

    await init_db()
    async with AsyncSessionLocal() as session:
        profile = (await session.execute(
            select(BusinessProfile).where(BusinessProfile.name == args.business)
        )).scalars().first()
        conn = (await session.execute(
            select(SocialConnection).where(
                SocialConnection.businessProfileId == profile.id
            ).limit(1)
        )).scalars().first()
    token = decrypt_token(conn.fbAccessToken)

    async with httpx.AsyncClient(timeout=120) as client:
        used, cap = await quota(client, conn.igAccountId, token)
        print(f"before: {used}/{cap} posts used in the last 24h")

        r = await client.post(
            f"{GRAPH}/{conn.igAccountId}/media_publish",
            data={"access_token": token, "creation_id": args.container},
        )
        body = r.json()
        print(f"publish -> HTTP {r.status_code}: {json.dumps(body)[:400]}")

        used_after, cap_after = await quota(client, conn.igAccountId, token)
        print(f"after : {used_after}/{cap_after} posts used in the last 24h")

        if "error" not in body:
            print(f"\nPUBLISHED as {body.get('id')} — carousels do work.")
        else:
            err = body["error"]
            print(f"\nREFUSED code={err.get('code')}/{err.get('error_subcode')}")
            print(f"  {err.get('message')}")
            if used is not None and cap and used < cap:
                print(f"  Quota was {used}/{cap}, so this is NOT the daily limit.")


if __name__ == "__main__":
    asyncio.run(main())
