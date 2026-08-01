"""Add BusinessProfile.brandIntelligence

Revision ID: 018_brand_intel
Revises: 017_fb_user_id
Create Date: 2026-08-01

The deep marketing profile — pain point, transformation, objection, decision
driver, competitor visual world — was being synthesised from scratch on every
single generation: a website scrape, a vision call and an LLM call, per prompt.
The result was thrown away each time.

Beyond the cost, that made the system incapable of understanding a business
consistently. Two runs an hour apart could decide the same company sold
different things, because nothing anchored the answer.

Persisting it makes the understanding a stable asset that every later prompt
builds on, and makes it inspectable and correctable by the user.

JSONB rather than JSON: Postgres can index and query inside it later, and the
cast from an existing NULL column is free. The model declares JSON, which
SQLAlchemy maps to JSONB on Postgres and to TEXT on SQLite for tests.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "018_brand_intel"
down_revision: Union[str, None] = "017_fb_user_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Separate statements: asyncpg rejects more than one per execute().
    op.execute(
        'ALTER TABLE "BusinessProfile" '
        'ADD COLUMN IF NOT EXISTS "brandIntelligence" JSONB'
    )
    op.execute(
        'ALTER TABLE "BusinessProfile" '
        'ADD COLUMN IF NOT EXISTS "brandIntelligenceAt" TIMESTAMPTZ'
    )


def downgrade() -> None:
    op.execute('ALTER TABLE "BusinessProfile" DROP COLUMN IF EXISTS "brandIntelligenceAt"')
    op.execute('ALTER TABLE "BusinessProfile" DROP COLUMN IF EXISTS "brandIntelligence"')
