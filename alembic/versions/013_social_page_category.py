"""Add SocialConnection.fbPageCategory

Revision ID: 013_page_category
Revises: 012_media_gen_status
Create Date: 2026-07-30

Meta already classifies every Page — "Software Company", "Clothing Store",
"Restaurant" — and returns it on the /me/accounts response we were already
fetching. We discarded it.

Storing it gives each connected account a niche that came from the platform
rather than from a guess, which is what keeps two businesses connected through
the same login from producing interchangeable copy.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "013_page_category"
down_revision: Union[str, None] = "012_media_gen_status"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('ALTER TABLE "SocialConnection" ADD COLUMN IF NOT EXISTS "fbPageCategory" VARCHAR')


def downgrade() -> None:
    op.execute('ALTER TABLE "SocialConnection" DROP COLUMN IF EXISTS "fbPageCategory"')
