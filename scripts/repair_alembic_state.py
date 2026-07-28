"""
=============================================================================
Repair a stranded alembic_version stamp
=============================================================================
The production database was stamped by an earlier, since-replaced migration
set. Its alembic_version row points at a revision id that no longer exists in
alembic/versions, so `alembic upgrade head` aborts with:

    Can't locate revision identified by '<old-id>'

...which fails the build and leaves Render serving the previous image.

This script re-points a stranded stamp at our base revision. Every migration
from 002 onward is written to be idempotent (CREATE TABLE IF NOT EXISTS,
ADD COLUMN guarded by duplicate_column, constraints guarded by
duplicate_object), so replaying them over a database that already has some of
those objects is safe.

It is deliberately conservative:
  - does nothing when there is no alembic_version table (a fresh database)
  - does nothing when the stamp is already a revision we know about
  - only rewrites a stamp it cannot resolve
=============================================================================
"""
from __future__ import annotations

import asyncio
import pathlib
import re
import sys

BASE_REVISION = "001_baseline"


def known_revisions() -> set[str]:
    """Revision ids declared in alembic/versions."""
    versions = pathlib.Path(__file__).resolve().parent.parent / "alembic" / "versions"
    found: set[str] = set()
    for path in versions.glob("*.py"):
        if path.name == "__init__.py":
            continue
        m = re.search(r'^revision(?::\s*str)?\s*=\s*["\']([^"\']+)["\']', path.read_text(encoding="utf-8"), re.M)
        if m:
            found.add(m.group(1))
    return found


async def main() -> int:
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    from config import settings
    from database import get_async_database_url

    revisions = known_revisions()
    if BASE_REVISION not in revisions:
        print(f"[alembic-repair] Base revision {BASE_REVISION} not found on disk; aborting.")
        return 1
    print(f"[alembic-repair] Known revisions: {', '.join(sorted(revisions))}")

    url, connect_args = get_async_database_url(settings.database_url)
    engine = create_async_engine(url, connect_args=connect_args)

    try:
        async with engine.begin() as conn:
            exists = (await conn.execute(text("SELECT to_regclass('public.alembic_version')"))).scalar()
            if not exists:
                print("[alembic-repair] No alembic_version table — fresh database, nothing to repair.")
                return 0

            stamps = [r[0] for r in (await conn.execute(text("SELECT version_num FROM alembic_version"))).fetchall()]
            if not stamps:
                print("[alembic-repair] alembic_version is empty — nothing to repair.")
                return 0

            stranded = [s for s in stamps if s not in revisions]
            if not stranded:
                print(f"[alembic-repair] Stamp {stamps} is valid — nothing to repair.")
                return 0

            print(f"[alembic-repair] Stranded stamp(s) {stranded} not present in this migration set.")
            print(f"[alembic-repair] Re-pointing to {BASE_REVISION}; migrations 002+ are idempotent and will replay safely.")

            # Single-row table by definition, so replace its contents outright.
            await conn.execute(text("DELETE FROM alembic_version"))
            await conn.execute(
                text("INSERT INTO alembic_version (version_num) VALUES (:rev)"),
                {"rev": BASE_REVISION},
            )
            print(f"[alembic-repair] Stamp is now {BASE_REVISION}.")
            return 0
    finally:
        await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
