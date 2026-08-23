"""Store a YouTube connection.

Only the refresh token is kept. Google's access tokens last an hour, so a
stored one is stale by the time the scheduler next runs; it is exchanged for a
fresh access token on each upload instead.

The channel id and title are kept so the interface can say which channel is
connected without a network call — a connect panel that says "connected" and
nothing else is a panel nobody trusts.

Revision ID: 027_youtube_connection
Revises: 026_linkedin_actor
"""

from alembic import op

revision = "027_youtube_connection"
down_revision = "026_linkedin_actor"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # IF NOT EXISTS because database.py's bootstrap adds the same columns on
    # startup; whichever runs first, the other must not fail.
    op.execute(
        'ALTER TABLE "SocialConnection" ADD COLUMN IF NOT EXISTS "youtubeRefreshToken" TEXT'
    )
    op.execute(
        'ALTER TABLE "SocialConnection" ADD COLUMN IF NOT EXISTS "youtubeChannelId" VARCHAR'
    )
    op.execute(
        'ALTER TABLE "SocialConnection" ADD COLUMN IF NOT EXISTS "youtubeChannelTitle" VARCHAR'
    )


def downgrade() -> None:
    op.execute('ALTER TABLE "SocialConnection" DROP COLUMN IF EXISTS "youtubeChannelTitle"')
    op.execute('ALTER TABLE "SocialConnection" DROP COLUMN IF EXISTS "youtubeChannelId"')
    op.execute('ALTER TABLE "SocialConnection" DROP COLUMN IF EXISTS "youtubeRefreshToken"')
