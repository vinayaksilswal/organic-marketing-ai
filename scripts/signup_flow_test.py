"""Walk the path a paid visitor takes, against production.

Ads send someone to the landing page, they press Start free, and every step
after that has to work or the click is wasted. This exercises the real
endpoints on the live backend with a throwaway account:

  register -> reach the product -> see the free plan -> get an upgrade link

The upgrade step stops at the approval URL. Following it would mean agreeing
to a subscription, which is not something a test should do.
"""

import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

API = "https://organic-marketing-ai-0abh.onrender.com/api/v1"
ORIGIN = "https://www.organiflo.com"


async def main() -> None:
    email = f"adtest-{uuid.uuid4().hex[:10]}@example.com"
    password = "TestPassw0rd!2026"
    headers = {"Origin": ORIGIN}
    ok = True

    async with httpx.AsyncClient(timeout=90) as c:
        print(f"1. register {email}")
        r = await c.post(f"{API}/auth/register",
                         json={"email": email, "password": password}, headers=headers)
        print(f"   HTTP {r.status_code}")
        if r.status_code >= 400:
            print(f"   FAILED: {r.text[:200]}")
            return
        body = r.json()
        token = body.get("token") or body.get("access_token")
        if not token:
            r = await c.post(f"{API}/auth/login",
                             json={"email": email, "password": password}, headers=headers)
            token = r.json().get("token") or r.json().get("access_token")
        print(f"   token: {'yes' if token else 'NO TOKEN'}")
        if not token:
            return
        auth = {**headers, "Authorization": f"Bearer {token}"}

        print("\n2. who am I, and can I use the product?")
        r = await c.get(f"{API}/users/me", headers=auth)
        me = r.json() if r.status_code < 400 else {}
        status = me.get("subscriptionStatus")
        print(f"   HTTP {r.status_code}  subscriptionStatus={status}")
        # The old gate bounced anything that was not ACTIVE to /checkout.
        print(f"   -> a new account is {status}; the dashboard must still open")

        print("\n3. what plan am I on?")
        r = await c.get(f"{API}/billing/me", headers=auth)
        if r.status_code >= 400:
            print(f"   FAILED HTTP {r.status_code}: {r.text[:160]}")
            ok = False
        else:
            b = r.json()
            plan = (b.get("plan") or {})
            print(f"   plan: {plan.get('name')} at ${plan.get('price')}")
            print(f"   limits: {plan.get('limits')}")
            if plan.get("code") != "free":
                print("   UNEXPECTED: a new account should be on free")
                ok = False

        print("\n4. can I upgrade and pay?")
        r = await c.post(f"{API}/billing/subscribe",
                         json={"planCode": "starter"}, headers=auth)
        if r.status_code >= 400:
            print(f"   FAILED HTTP {r.status_code}: {r.text[:220]}")
            ok = False
        else:
            b = r.json()
            approve = b.get("approveUrl") or b.get("approve_url") or b.get("url")
            print(f"   HTTP {r.status_code}")
            print(f"   PayPal approval URL: {'yes' if approve else 'MISSING'}")
            if approve:
                print(f"   {approve[:96]}")
                print("   (not followed — that would authorise a real subscription)")
            else:
                print(f"   body: {str(b)[:220]}")
                ok = False

    print("\n" + "=" * 62)
    print("SIGNUP -> FREE -> UPGRADE PATH: " + ("WORKS" if ok else "BROKEN"))


if __name__ == "__main__":
    asyncio.run(main())
