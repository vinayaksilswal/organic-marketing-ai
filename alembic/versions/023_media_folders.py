"""Media folders — a folder of assets publishes as one carousel post.

Revision ID: 023_media_folders
Revises: 022_proven_offers
"""

from alembic import op

revision = "023_media_folders"
down_revision = "022_proven_offers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS "MediaFolder" (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            caption TEXT,
            "isActive" BOOLEAN NOT NULL DEFAULT TRUE,
            "businessProfileId" TEXT REFERENCES "BusinessProfile"(id) ON DELETE CASCADE,
            "createdAt" TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            "updatedAt" TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute(
        'CREATE INDEX IF NOT EXISTS "ix_mediafolder_workspace" '
        'ON "MediaFolder" ("businessProfileId")'
    )
    # SET NULL, not CASCADE: deleting a folder must free its files, never
    # destroy a business's media.
    op.execute(
        'ALTER TABLE "Media" ADD COLUMN IF NOT EXISTS "folderId" TEXT '
        'REFERENCES "MediaFolder"(id) ON DELETE SET NULL'
    )
    op.execute(
        'ALTER TABLE "Media" ADD COLUMN IF NOT EXISTS "folderPosition" INTEGER NOT NULL DEFAULT 0'
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS "ix_media_folder" ON "Media" ("folderId")'
    )


def downgrade() -> None:
    op.execute('DROP INDEX IF EXISTS "ix_media_folder"')
    op.execute('ALTER TABLE "Media" DROP COLUMN IF EXISTS "folderPosition"')
    op.execute('ALTER TABLE "Media" DROP COLUMN IF EXISTS "folderId"')
    op.execute('DROP INDEX IF EXISTS "ix_mediafolder_workspace"')
    op.execute('DROP TABLE IF EXISTS "MediaFolder"')
