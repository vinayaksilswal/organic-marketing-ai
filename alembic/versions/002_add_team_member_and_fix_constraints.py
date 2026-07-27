"""Add TeamMember table and fix SocialConnection constraints

Revision ID: 002_team_and_constraints
Revises: 001_baseline
Create Date: 2026-07-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002_team_and_constraints"
down_revision: Union[str, None] = "001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create TeamMember table if it doesn't exist (create_all may have already made it)
    op.execute("""
        CREATE TABLE IF NOT EXISTS "TeamMember" (
            id VARCHAR PRIMARY KEY,
            "businessProfileId" VARCHAR NOT NULL REFERENCES "BusinessProfile"(id) ON DELETE CASCADE,
            "userId" VARCHAR REFERENCES "User"(id) ON DELETE SET NULL,
            email VARCHAR NOT NULL,
            role VARCHAR NOT NULL DEFAULT 'editor',
            status VARCHAR NOT NULL DEFAULT 'pending',
            "invitedAt" TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            "acceptedAt" TIMESTAMP WITH TIME ZONE,
            CONSTRAINT uniq_workspace_team_email UNIQUE ("businessProfileId", email)
        )
    """)

    # Drop the old unique constraint on SocialConnection.userId (if it exists)
    # PostgreSQL names auto-generated unique constraints as "<table>_<column>_key"
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE "SocialConnection" DROP CONSTRAINT IF EXISTS "SocialConnection_userId_key";
        EXCEPTION WHEN undefined_object THEN NULL;
        END $$
    """)

    # Add composite unique constraint (userId + businessProfileId)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE "SocialConnection"
                ADD CONSTRAINT uniq_user_workspace_social UNIQUE ("userId", "businessProfileId");
        EXCEPTION WHEN duplicate_table THEN NULL;
        END $$
    """)


def downgrade() -> None:
    op.execute('ALTER TABLE "SocialConnection" DROP CONSTRAINT IF EXISTS uniq_user_workspace_social')
    op.execute('DROP TABLE IF EXISTS "TeamMember"')
