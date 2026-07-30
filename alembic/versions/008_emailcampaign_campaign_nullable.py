"""Allow EmailCampaign.campaignId to be NULL

Revision ID: 008_email_campaign_null
Revises: 007_post_campaign_null
Create Date: 2026-07-30

An email drafted by the automation run has no parent social campaign, but
campaignId was NOT NULL, so every run failed with:

    NotNullViolationError: null value in column "campaignId" of relation
    "EmailCampaign" violates not-null constraint

Same defect as SocialPost.campaignId, fixed in 007.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "008_email_campaign_null"
down_revision: Union[str, None] = "007_post_campaign_null"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE "EmailCampaign" ALTER COLUMN "campaignId" DROP NOT NULL;
        EXCEPTION WHEN undefined_column THEN NULL;
        END $$
    """)


def downgrade() -> None:
    # Existing standalone campaigns have no campaign to point at.
    pass
