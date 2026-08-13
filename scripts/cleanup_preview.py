"""What would the daily cleanup remove right now? Nothing is deleted.

Runs the real job in dry-run mode against the live accounts, so the rule can
be judged on actual posts before it is ever armed.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database import init_db
from services.post_cleanup import (
    MAX_DELETIONS_PER_RUN, MIN_AGE_DAYS, MIN_VIEWS, run_cleanup,
)


async def main() -> None:
    await init_db()
    print(f"rule: older than {MIN_AGE_DAYS} days AND fewer than {MIN_VIEWS} "
          f"views, at most {MAX_DELETIONS_PER_RUN} per business per run\n")

    results = await run_cleanup(dry_run=True)

    print(f"\n{'BUSINESS':<22} {'WOULD DELETE':>13}  NOTE")
    print("-" * 78)
    for outcome in sorted(results, key=lambda r: -r.get("found", 0)):
        print(f"{str(outcome.get('name'))[:21]:<22} {outcome.get('found', 0):>13}  "
              f"{outcome.get('note', '')[:44]}")

    total = sum(r.get("found", 0) for r in results)
    print(f"\n{total} post(s) across all businesses match the rule.")
    if total == 0:
        print("Nothing qualifies, so arming this changes nothing today.")


if __name__ == "__main__":
    asyncio.run(main())
