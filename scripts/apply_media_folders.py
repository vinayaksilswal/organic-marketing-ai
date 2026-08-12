"""Create the MediaFolder table and the Media folder columns on the live DB.

Run once:  python -m scripts.apply_media_folders
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from database import init_db

STATEMENTS = [
    """CREATE TABLE IF NOT EXISTS "MediaFolder" (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        caption TEXT,
        "isActive" BOOLEAN NOT NULL DEFAULT TRUE,
        "businessProfileId" TEXT REFERENCES "BusinessProfile"(id) ON DELETE CASCADE,
        "createdAt" TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        "updatedAt" TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )""",
    'CREATE INDEX IF NOT EXISTS "ix_mediafolder_workspace" ON "MediaFolder" ("businessProfileId")',
    'ALTER TABLE "Media" ADD COLUMN IF NOT EXISTS "folderId" TEXT '
    'REFERENCES "MediaFolder"(id) ON DELETE SET NULL',
    'ALTER TABLE "Media" ADD COLUMN IF NOT EXISTS "folderPosition" INTEGER NOT NULL DEFAULT 0',
    'CREATE INDEX IF NOT EXISTS "ix_media_folder" ON "Media" ("folderId")',
]


async def main() -> None:
    engine = await init_db()
    async with engine.begin() as conn:
        for sql in STATEMENTS:
            await conn.execute(text(sql))
            print("ok:", " ".join(sql.split())[:78])

        rows = (await conn.execute(text(
            'SELECT column_name FROM information_schema.columns '
            "WHERE table_name = 'Media' AND column_name IN ('folderId','folderPosition')"
        ))).fetchall()
        print("\nMedia now has:", sorted(r[0] for r in rows))

        exists = (await conn.execute(text(
            "SELECT to_regclass('\"MediaFolder\"') IS NOT NULL"
        ))).scalar()
        print("MediaFolder table present:", exists)


if __name__ == "__main__":
    asyncio.run(main())
