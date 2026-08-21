"""Who a LinkedIn post is authored by.

The service posted as `urn:li:organization:{LINKEDIN_ORGANIZATION_ID}` and
returned None when that env var was unset, which it always was -- so LinkedIn
publishing could never run for any customer.

Company Page posting needs LinkedIn's Community Management API and app review.
Personal-profile posting needs w_member_social and nothing else. Storing the
actor URN per connection lets a customer publish today on their profile and
move to a Page when the review clears, without a second code path.

Revision ID: 026_linkedin_actor
Revises: 025_posting_window
"""

from alembic import op

revision = "026_linkedin_actor"
down_revision = "025_posting_window"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('ALTER TABLE "SocialConnection" ADD COLUMN IF NOT EXISTS "linkedinActorUrn" TEXT')


def downgrade() -> None:
    op.execute('ALTER TABLE "SocialConnection" DROP COLUMN IF EXISTS "linkedinActorUrn"')
