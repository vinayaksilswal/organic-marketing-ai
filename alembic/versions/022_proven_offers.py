"""Proven offers on the business profile.

What the business has already sold, and the angle that sold it, so organic
captions inherit from paid results instead of guessing.

Revision ID: 022_proven_offers
Revises: 021_hashtag_sets
"""

from alembic import op

revision = "022_proven_offers"
down_revision = "021_hashtag_sets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "provenOffers" JSONB')


def downgrade() -> None:
    op.execute('ALTER TABLE "BusinessProfile" DROP COLUMN IF EXISTS "provenOffers"')
