"""Deduplicate MarketingState and enforce one row per workspace

Revision ID: 010_mstate_unique
Revises: 009_media_caption
Create Date: 2026-07-30

MarketingState had no uniqueness on businessProfileId, and three separate code
paths created rows (onboarding, the auto-approve endpoint, the interval
endpoint). Every reader then did .first() with no ORDER BY, so which row won
was down to the query plan.

The user-visible symptom: turning auto-approve OFF updated one row while the
publisher read another, and posts kept going out.

Dedupe keeps the OLDEST row per workspace — that is the one onboarding created
and the one whose id is referenced elsewhere. Auto-approve is folded down
conservatively: the merged row is auto-approving only if EVERY duplicate was,
so this migration can never turn publishing on for someone.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "010_mstate_unique"
down_revision: Union[str, None] = "009_media_caption"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Fold duplicates down onto the oldest row per workspace.
    op.execute("""
        DO $$ BEGIN
            UPDATE "MarketingState" ms
               SET "autoApprove" = sub.all_approved
              FROM (
                    SELECT "businessProfileId",
                           bool_and("autoApprove") AS all_approved,
                           MIN("createdAt")        AS first_created
                      FROM "MarketingState"
                     WHERE "businessProfileId" IS NOT NULL
                     GROUP BY "businessProfileId"
                    HAVING COUNT(*) > 1
                   ) sub
             WHERE ms."businessProfileId" = sub."businessProfileId"
               AND ms."createdAt" = sub.first_created;
        EXCEPTION WHEN undefined_column THEN NULL;
        END $$
    """)

    # Delete every row that is not the oldest for its workspace.
    op.execute("""
        DELETE FROM "MarketingState" ms
         WHERE ms."businessProfileId" IS NOT NULL
           AND ms.ctid NOT IN (
                SELECT DISTINCT ON ("businessProfileId") ctid
                  FROM "MarketingState"
                 WHERE "businessProfileId" IS NOT NULL
                 ORDER BY "businessProfileId", "createdAt" ASC
           )
    """)

    op.execute("""
        DO $$ BEGIN
            ALTER TABLE "MarketingState"
              ADD CONSTRAINT uniq_marketing_state_workspace
              UNIQUE ("businessProfileId");
        EXCEPTION WHEN duplicate_object OR duplicate_table THEN NULL;
        END $$
    """)


def downgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE "MarketingState" DROP CONSTRAINT uniq_marketing_state_workspace;
        EXCEPTION WHEN undefined_object THEN NULL;
        END $$
    """)
