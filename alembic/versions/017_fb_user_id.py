"""Add SocialConnection.fbUserId

Revision ID: 017_fb_user_id
Revises: 016_prompt_engine
Create Date: 2026-08-01

Meta's Data Deletion Callback identifies the person by their app-scoped
Facebook user id and sends nothing else. We stored the Page id and the
Instagram account id but never the user id, so an incoming deletion request
could not be matched to an account at all — and an app with no working
deletion callback is rejected at App Review.

Nullable on purpose. Connections made before this column existed have no user
id to backfill: the value is only obtainable from /me while the user's token is
live, and by the time a deletion request arrives the app has been removed. Those
rows fall back to the authenticated self-serve delete instead.

CREATE INDEX runs as its own statement because asyncpg rejects multiple
statements in one execute(), and IF NOT EXISTS on both so a re-run after a
partial deploy is a no-op rather than a failure.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "017_fb_user_id"
down_revision: Union[str, None] = "016_prompt_engine"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('ALTER TABLE "SocialConnection" ADD COLUMN IF NOT EXISTS "fbUserId" VARCHAR')
    op.execute('CREATE INDEX IF NOT EXISTS "ix_SocialConnection_fbUserId" ON "SocialConnection" ("fbUserId")')


def downgrade() -> None:
    op.execute('DROP INDEX IF EXISTS "ix_SocialConnection_fbUserId"')
    op.execute('ALTER TABLE "SocialConnection" DROP COLUMN IF EXISTS "fbUserId"')
