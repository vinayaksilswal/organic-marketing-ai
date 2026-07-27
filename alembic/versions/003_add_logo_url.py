"""Add logoUrl to BusinessProfile

Revision ID: 003_add_logo_url
Revises: 002_team_and_constraints
Create Date: 2026-07-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003_add_logo_url"
down_revision: Union[str, None] = "002_team_and_constraints"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE "BusinessProfile" ADD COLUMN "logoUrl" VARCHAR;
        EXCEPTION WHEN duplicate_column THEN NULL;
        END $$
    """)


def downgrade() -> None:
    op.drop_column("BusinessProfile", "logoUrl")
