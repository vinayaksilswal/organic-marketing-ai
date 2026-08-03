"""Move media that landed in the wrong business back where it belongs.

Uploading a folder sends dozens of sequential requests over several minutes,
and the workspace id was read from localStorage on each one. localStorage is
shared between tabs, so switching business in another tab redirected every
remaining batch. One folder ended up split across five workspaces with nothing
on screen showing it.

The frontend now pins the workspace for the whole upload. This repairs what
the old behaviour scattered, using the folder prefix in each filename -- which
records where the file actually came from and is unaffected by the bug.

    python scripts/reassign_misfiled_media.py --folder sensual_beautiful_angels --to HollyVerse
    python scripts/reassign_misfiled_media.py --folder sensual_beautiful_angels --to HollyVerse --apply

Dry run by default. --apply writes a rollback file first, so a wrong call can
be undone:

    python scripts/reassign_misfiled_media.py --undo rollback-<timestamp>.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select


def _folder_of(filename: str) -> str:
    """The folder a file was uploaded from, or "" for a bare filename.

    This is the only trustworthy record of origin: the businessProfileId was
    set by whichever workspace happened to be active when that batch was sent.
    """
    name = (filename or "").replace("\\", "/")
    return name.rsplit("/", 1)[0] if "/" in name else ""


async def _undo(path: str) -> int:
    from database import AsyncSessionLocal, Media, init_db

    await init_db()
    record = json.loads(Path(path).read_text(encoding="utf-8"))
    async with AsyncSessionLocal() as session:
        for media_id, original in record["moves"].items():
            row = await session.get(Media, media_id)
            if row:
                row.businessProfileId = original
        await session.commit()
    print(f"Restored {len(record['moves'])} assets to their previous businesses")
    return 0


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", help="folder prefix that identifies the files")
    ap.add_argument("--to", help="business name or id that should own them")
    ap.add_argument("--apply", action="store_true", help="actually move them")
    ap.add_argument("--undo", help="rollback file from a previous --apply")
    args = ap.parse_args()

    if args.undo:
        return await _undo(args.undo)
    if not args.folder or not args.to:
        ap.error("--folder and --to are required")

    from database import AsyncSessionLocal, BusinessProfile, Media, init_db

    await init_db()

    async with AsyncSessionLocal() as session:
        target = await session.get(BusinessProfile, args.to)
        if target is None:
            target = (await session.execute(
                select(BusinessProfile).where(BusinessProfile.name == args.to)
            )).scalars().first()
        if target is None:
            print(f"No business matching {args.to!r}")
            return 1

        profiles = {
            p.id: p.name
            for p in (await session.execute(select(BusinessProfile))).scalars().all()
        }
        rows = (await session.execute(select(Media))).scalars().all()

        belongs = [r for r in rows if _folder_of(r.filename).startswith(args.folder)]
        misfiled = [r for r in belongs if r.businessProfileId != target.id]

        print(f"\nFolder {args.folder!r} -> {target.name} [{target.id}]")
        print(f"  {len(belongs)} assets carry that folder prefix")
        print(f"  {len(belongs) - len(misfiled)} already in the right business")
        print(f"  {len(misfiled)} to move\n")

        if misfiled:
            for pid, count in Counter(r.businessProfileId for r in misfiled).most_common():
                print(f"    {count:>5}  from {profiles.get(pid, pid)}")

        # Anything the target holds that did NOT come from this folder is
        # reported but never touched -- it may be legitimately its own.
        strays = [
            r for r in rows
            if r.businessProfileId == target.id
            and not _folder_of(r.filename).startswith(args.folder)
        ]
        if strays:
            print(f"\n  {len(strays)} asset(s) already in {target.name} are from "
                  f"other folders and are left alone:")
            for folder, count in Counter(_folder_of(r.filename) for r in strays).most_common(6):
                print(f"    {count:>5}  {folder or '(no folder)'}")

        if not args.apply:
            print("\nDry run. Re-run with --apply to move them.")
            return 0
        if not misfiled:
            print("\nNothing to move.")
            return 0

        stamp = time.strftime("%Y%m%d-%H%M%S")
        rollback = Path(f"rollback-{stamp}.json")
        rollback.write_text(json.dumps({
            "folder": args.folder,
            "target": target.id,
            "moves": {r.id: r.businessProfileId for r in misfiled},
        }, indent=2), encoding="utf-8")
        print(f"\nRollback written to {rollback}")

        for r in misfiled:
            r.businessProfileId = target.id
        await session.commit()

    print(f"Moved {len(misfiled)} assets into {target.name}")
    print(f"Undo with:  python scripts/reassign_misfiled_media.py --undo {rollback}")
    return 0


if __name__ == "__main__":
    from loguru import logger

    logger.remove()
    logger.add(sys.stderr, level="ERROR")
    raise SystemExit(asyncio.run(main()))
