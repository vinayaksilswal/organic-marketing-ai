"""Allow SocialPost.campaignId to be NULL

Revision ID: 007_post_campaign_null
Revises: 006_reconcile_columns
Create Date: 2026-07-28

A post created by the scheduler or the manual "Run Automation" button has no
parent campaign, but campaignId was NOT NULL. Every such run failed with:

    NotNullViolationError: null value in column "campaignId" of relation
    "SocialPost" violates not-null constraint

Migration 006 only ADDs columns; it cannot relax an existing constraint, so
this is separate. Standalone posts are a legitimate concept — the campaign
link stays optional.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "007_post_campaign_null"
down_revision: Union[str, None] = "006_reconcile_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE "SocialPost" ALTER COLUMN "campaignId" DROP NOT NULL;
        EXCEPTION WHEN undefined_column THEN NULL;
        END $$
    """)


def downgrade() -> None:
    # Not restored: existing standalone posts have no campaign to point at,
    # so re-adding NOT NULL would fail.
    pass
