"""Recurring billing: Subscription, UsageCounter, ProcessedWebhookEvent

Revision ID: 015_billing
Revises: 014_email_config
Create Date: 2026-07-31

Checkout took a ONE-TIME $17 PayPal order and flipped User.subscriptionStatus
to ACTIVE forever. Nothing recurred, nothing expired, and there was no way to
tell a paying customer from someone who paid once in March.

Subscription tracks the PayPal subscription id, the plan and the period end.
UsageCounter meters usage per billing month so tier limits can be enforced.
ProcessedWebhookEvent makes webhook handling idempotent — PayPal retries
deliveries, and without it a repeated payment event would extend a
subscription twice.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "015_billing"
down_revision: Union[str, None] = "014_email_config"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS "Subscription" (
            id                      VARCHAR PRIMARY KEY,
            "userId"                VARCHAR NOT NULL REFERENCES "User"(id) ON DELETE CASCADE,
            "planCode"              VARCHAR NOT NULL DEFAULT 'starter',
            "paypalSubscriptionId"  VARCHAR,
            "paypalPlanId"          VARCHAR,
            status                  VARCHAR NOT NULL DEFAULT 'APPROVAL_PENDING',
            "currentPeriodEnd"      TIMESTAMPTZ,
            "cancelAtPeriodEnd"     BOOLEAN NOT NULL DEFAULT FALSE,
            "lastPaymentAt"         TIMESTAMPTZ,
            "lastError"             TEXT,
            "createdAt"             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            "updatedAt"             TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute('CREATE INDEX IF NOT EXISTS ix_subscription_user ON "Subscription" ("userId")')
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE "Subscription"
              ADD CONSTRAINT uniq_paypal_subscription_id UNIQUE ("paypalSubscriptionId");
        EXCEPTION WHEN duplicate_object OR duplicate_table THEN NULL;
        END $$
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS "UsageCounter" (
            id            VARCHAR PRIMARY KEY,
            "userId"      VARCHAR NOT NULL REFERENCES "User"(id) ON DELETE CASCADE,
            metric        VARCHAR NOT NULL,
            "periodStart" VARCHAR NOT NULL,
            count         INTEGER NOT NULL DEFAULT 0,
            "updatedAt"   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute('CREATE INDEX IF NOT EXISTS ix_usage_user ON "UsageCounter" ("userId")')
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE "UsageCounter"
              ADD CONSTRAINT uniq_usage_user_metric_period
              UNIQUE ("userId", metric, "periodStart");
        EXCEPTION WHEN duplicate_object OR duplicate_table THEN NULL;
        END $$
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS "ProcessedWebhookEvent" (
            id            VARCHAR PRIMARY KEY,
            "eventType"   VARCHAR,
            "processedAt" TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # The CREATE TABLE above only runs on a database that does not already have
    # these tables. Production's schema is built by create_all at application
    # startup, and SQLAlchemy's `Column(..., default=False)` is a PYTHON-side
    # default — it emits NOT NULL with no DEFAULT clause. So the deployed table
    # can have NOT NULL columns that no database default will fill.
    #
    # Align them, so the schema matches what this migration declares and any
    # future raw INSERT behaves the same on both paths.
    # Separate blocks: a PL/pgSQL exception handler rolls back everything in
    # its block, so pairing these would let one failure undo the other.
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE "Subscription" ALTER COLUMN "cancelAtPeriodEnd" SET DEFAULT FALSE;
        EXCEPTION WHEN undefined_column OR undefined_table THEN NULL;
        END $$
    """)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE "UsageCounter" ALTER COLUMN count SET DEFAULT 0;
        EXCEPTION WHEN undefined_column OR undefined_table THEN NULL;
        END $$
    """)

    # Anyone already marked ACTIVE paid for something. Grandfather them onto
    # the starter plan rather than cutting off access at deploy time.
    #
    # Every NOT NULL column is listed explicitly rather than left to a default,
    # because as above the deployed table may not carry one.
    op.execute("""
        INSERT INTO "Subscription"
            (id, "userId", "planCode", status, "cancelAtPeriodEnd", "createdAt", "updatedAt")
        SELECT
            'grandfathered-' || u.id, u.id, 'starter', 'ACTIVE', FALSE, NOW(), NOW()
          FROM "User" u
         WHERE u."subscriptionStatus" = 'ACTIVE'
           AND NOT EXISTS (SELECT 1 FROM "Subscription" s WHERE s."userId" = u.id)
    """)


def downgrade() -> None:
    op.execute('DROP TABLE IF EXISTS "ProcessedWebhookEvent"')
    op.execute('DROP TABLE IF EXISTS "UsageCounter"')
    op.execute('DROP TABLE IF EXISTS "Subscription"')
