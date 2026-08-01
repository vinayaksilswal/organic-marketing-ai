"""Record whether a Media clip carries a sound track.

Instagram's licensed-music picker is only reachable inside the app; the
Content Publishing API cannot attach a track. A silent clip auto-published
through the API is silent permanently, so the scheduler needs to know which
clips those are.

NULL means "not probed yet" and is the correct state for every existing row —
the backfill fills it in as clips are touched.

Revision ID: 019_media_has_audio
Revises: 018_brand_intel
"""
from typing import Union

from alembic import op

revision: str = "019_media_has_audio"
down_revision: Union[str, None] = "018_brand_intel"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('ALTER TABLE "Media" ADD COLUMN IF NOT EXISTS "hasAudio" BOOLEAN')


def downgrade() -> None:
    op.execute('ALTER TABLE "Media" DROP COLUMN IF EXISTS "hasAudio"')
