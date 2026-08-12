"""Tiered hashtag sets per business.

Nullable: a business created before this, or one whose generation failed,
falls back to suggestedHashtags. Absent must mean "not built yet", never
"built and empty", or the backfill cannot tell them apart.

Revision ID: 021_hashtag_sets
Revises: 020_automation_paused
"""
from typing import Union

from alembic import op

revision: str = "021_hashtag_sets"
down_revision: Union[str, None] = "020_automation_paused"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "hashtagSets" JSONB')


def downgrade() -> None:
    op.execute('ALTER TABLE "BusinessProfile" DROP COLUMN IF EXISTS "hashtagSets"')
