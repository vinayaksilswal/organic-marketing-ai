"""Add BusinessProfile.primaryOffer

Revision ID: 011_primary_offer
Revises: 010_mstate_unique
Create Date: 2026-07-30

Every creative is supposed to drive one action, but there was nowhere to store
what that action is. The AI therefore invented a call to action per post, so
the offer drifted between "learn more", "get started" and "book a demo" — and
nothing was consistent enough for a viewer to act on twice.

Nullable: a business that has not set one still gets a soft CTA rather than a
fabricated offer.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "011_primary_offer"
down_revision: Union[str, None] = "010_mstate_unique"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('ALTER TABLE "BusinessProfile" ADD COLUMN IF NOT EXISTS "primaryOffer" TEXT')


def downgrade() -> None:
    op.execute('ALTER TABLE "BusinessProfile" DROP COLUMN IF EXISTS "primaryOffer"')
