"""Add Media.caption and Media.isActive

Revision ID: 009_media_caption
Revises: 008_email_campaign_null
Create Date: 2026-07-30

Two gaps this closes:

  caption  — the catalog UI has always shown a "Base Caption" column and the
             upload form has always had a Base Caption field, but there was
             nowhere to store it. The column fell back to the filename, and
             the typed value was discarded. The caption writer therefore had
             no description of the asset it was writing about.

  isActive — the DEACTIVATE button had no backing column, so it could only
             ever be cosmetic. Automation now skips inactive assets.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "009_media_caption"
down_revision: Union[str, None] = "008_email_campaign_null"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('ALTER TABLE "Media" ADD COLUMN IF NOT EXISTS "caption" TEXT')
    op.execute(
        'ALTER TABLE "Media" ADD COLUMN IF NOT EXISTS "isActive" BOOLEAN NOT NULL DEFAULT TRUE'
    )
    # Existing AI assets already carry the prompt that produced them; that is
    # exactly the description the caption writer needs, so backfill from it
    # rather than leaving years of assets contextless.
    op.execute("""
        UPDATE "Media"
           SET "caption" = "prompt"
         WHERE "caption" IS NULL
           AND "prompt" IS NOT NULL
           AND "prompt" <> ''
    """)


def downgrade() -> None:
    op.execute('ALTER TABLE "Media" DROP COLUMN IF EXISTS "caption"')
    op.execute('ALTER TABLE "Media" DROP COLUMN IF EXISTS "isActive"')
