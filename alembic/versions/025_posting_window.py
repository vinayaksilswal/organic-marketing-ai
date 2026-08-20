"""When a workspace may post, not just how often.

A fixed interval drifts through the whole clock: a 4-hour cadence starting at
20:58 posts at 02:58 and 08:58. Two live workspaces show exactly that. This
lets a customer say which days and which hours, in their own timezone.

All null means no restriction, so every existing workspace is unaffected.

Revision ID: 025_posting_window
Revises: 024_media_keyframes
"""

from alembic import op

revision = "025_posting_window"
down_revision = "024_media_keyframes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "postingDays" JSONB')
    op.execute('ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "postingStartHour" INTEGER')
    op.execute('ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "postingEndHour" INTEGER')
    op.execute('ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "postingTimezone" TEXT')


def downgrade() -> None:
    for col in ("postingDays", "postingStartHour", "postingEndHour", "postingTimezone"):
        op.execute(f'ALTER TABLE "BusinessProfile" DROP COLUMN IF EXISTS "{col}"')
