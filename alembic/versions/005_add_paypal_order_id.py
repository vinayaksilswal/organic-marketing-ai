"""Add unique paypalOrderId to User (prevents payment replay)

Revision ID: 005_paypal_order_id
Revises: 004_media_prompt
Create Date: 2026-07-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005_paypal_order_id"
down_revision: Union[str, None] = "004_media_prompt"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE "User" ADD COLUMN "paypalOrderId" VARCHAR;
        EXCEPTION WHEN duplicate_column THEN NULL;
        END $$
    """)
    # Postgres permits many NULLs under a unique constraint, so existing users
    # (who have no recorded order) are unaffected.
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE "User" ADD CONSTRAINT uniq_user_paypal_order UNIQUE ("paypalOrderId");
        EXCEPTION WHEN duplicate_table THEN NULL;
                  WHEN duplicate_object THEN NULL;
        END $$
    """)


def downgrade() -> None:
    op.execute('ALTER TABLE "User" DROP CONSTRAINT IF EXISTS uniq_user_paypal_order')
    op.drop_column("User", "paypalOrderId")
