"""Add prompt/promptType to Media

Revision ID: 004_media_prompt
Revises: 003_add_logo_url
Create Date: 2026-07-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004_media_prompt"
down_revision: Union[str, None] = "003_add_logo_url"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE "Media" ADD COLUMN "prompt" TEXT;
        EXCEPTION WHEN duplicate_column THEN NULL;
        END $$
    """)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE "Media" ADD COLUMN "promptType" VARCHAR;
        EXCEPTION WHEN duplicate_column THEN NULL;
        END $$
    """)


def downgrade() -> None:
    op.drop_column("Media", "promptType")
    op.drop_column("Media", "prompt")
