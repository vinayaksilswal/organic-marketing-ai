"""The shared rate limiter.

Lives in its own module so routers can decorate endpoints with it. It used to
be constructed in main.py, which imports the routers -- so a router importing
it back would have closed an import cycle, and importing it at decoration time
would have found nothing there yet.

The key is the authenticated user where there is one, falling back to the
client address. Limiting purely by IP puts every customer behind a shared
office NAT or a mobile carrier gateway into one bucket, so one heavy user
throttles strangers.
"""

from __future__ import annotations

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def rate_limit_key(request: Request) -> str:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            import jwt as pyjwt

            # Unverified on purpose: this only picks a bucket. A forged token
            # buys the forger their own bucket, not access to anything.
            payload = pyjwt.decode(
                auth_header.split(" ")[1], options={"verify_signature": False}
            )
            uid = payload.get("sub")
            if uid:
                return f"user:{uid}"
        except Exception:
            pass
    return get_remote_address(request)


limiter = Limiter(key_func=rate_limit_key, default_limits=["200/minute"])
