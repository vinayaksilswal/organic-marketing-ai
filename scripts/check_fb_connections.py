"""What each workspace actually has stored for Facebook, and whether it works.

Tokens are decrypted before they are judged. A previous pass read them at rest,
concluded every token was invalid, and sent an investigation after credentials
that were fine.
"""

import asyncio
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
        rows = (await session.execute(
            select(BusinessProfile, SocialConnection)
            .join(SocialConnection,
                  SocialConnection.businessProfileId == BusinessProfile.id)
            .order_by(BusinessProfile.name)
        )).all()

        for profile, conn in rows:
            print(f"\n=== {profile.name} ===")
            print(f"  fbPageId    : {conn.fbPageId or 'MISSING'}")
            print(f"  igAccountId : {conn.igAccountId or 'MISSING'}")
            print(f"  token stored: {'yes' if conn.fbAccessToken else 'NO'}")

            if not conn.fbAccessToken:
                continue
            try:
                token = decrypt_token(conn.fbAccessToken)
            except Exception as e:
                print(f"  token       : UNREADABLE ({e})")
                continue

            async with httpx.AsyncClient(timeout=45) as client:
                # Does the token work at all?
                me = (await client.get(
                    f"{GRAPH}/me", params={"access_token": token, "fields": "id,name"}
                )).json()
                if "error" in me:
                    print(f"  token       : REJECTED — {me['error'].get('message')}")
                    continue
                print(f"  token       : valid, identifies as {me.get('name')} ({me.get('id')})")

                if not conn.fbPageId:
                    print("  -> Facebook posting CANNOT work: no Page id stored.")
                    continue

                # Can it actually publish to that page?
                page = (await client.get(
                    f"{GRAPH}/{conn.fbPageId}",
                    params={"access_token": token, "fields": "id,name,category"},
                )).json()
                if "error" in page:
                    print(f"  page access : REFUSED — {page['error'].get('message')}")
                else:
                    print(f"  page access : ok — {page.get('name')} [{page.get('category')}]")

                perms = (await client.get(
                    f"{GRAPH}/me/permissions", params={"access_token": token}
                )).json()
                granted = sorted(
                    p["permission"] for p in perms.get("data", [])
                    if p.get("status") == "granted"
                )
                declined = sorted(
                    p["permission"] for p in perms.get("data", [])
                    if p.get("status") == "declined"
                )
                print(f"  granted     : {', '.join(granted) or 'none'}")
                if declined:
                    print(f"  DECLINED    : {', '.join(declined)}")


if __name__ == "__main__":
    asyncio.run(main())
