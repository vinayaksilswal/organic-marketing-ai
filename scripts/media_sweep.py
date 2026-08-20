"""Retire assets whose files no longer exist.

The scheduler runs this daily once deployed. Run it by hand to clean up now.

    python scripts/media_sweep.py              # report only, changes nothing
    python scripts/media_sweep.py --apply      # retire the dead ones

A retired asset is not deleted. isActive goes false and the reason is written
onto the row, so it stops being scheduled and can be re-enabled by hand or
picked up again by a later sweep if the file comes back.

Only 404 and 410 retire anything. A timeout or a 5xx is reported and left
alone, because emptying a catalog over a bad minute is worse than the problem
this fixes.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


async def main() -> None:
    from database import init_db
    from services.media_health import sweep

    apply = "--apply" in sys.argv
    workspace = None
    for arg in sys.argv[1:]:
        if arg.startswith("--workspace="):
            workspace = arg.split("=", 1)[1]

    await init_db()
    result = await sweep(workspace_id=workspace, dry_run=not apply)

    print()
    print(f"  checked      {result['checked']}")
    print(f"  gone         {result['retired']}")
    print(f"  unreachable  {result['unreachable']}  (left alone on purpose)")
    print()

    if result["items"]:
        print("  These files no longer exist in storage:")
        for item in result["items"]:
            print(f"    {item['status']}  {item['id'][:8]}  {(item['filename'] or '')[:52]}")
        print()

    if not apply and result["retired"]:
        print("  Nothing was changed. Re-run with --apply to retire them.")
    elif apply and result["retired"]:
        print(f"  {result['retired']} asset(s) retired from the posting rotation.")
    else:
        print("  Every asset still resolves.")


if __name__ == "__main__":
    asyncio.run(main())
