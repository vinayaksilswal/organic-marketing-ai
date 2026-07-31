"""Add EmailConfig — per-workspace email sending credentials

Revision ID: 014_email_config
Revises: 013_page_category
Create Date: 2026-07-30

Email could only be sent through one global RESEND_API_KEY. Every customer's
mail would therefore leave from the platform's own domain, which is bad for
deliverability and impossible for a business that wants to send as itself.

The API key is stored Fernet-encrypted, the same as social tokens.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "014_email_config"
down_revision: Union[str, None] = "013_page_category"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS "EmailConfig" (
            id                 VARCHAR PRIMARY KEY,
            "userId"           VARCHAR NOT NULL REFERENCES "User"(id) ON DELETE CASCADE,
            provider           VARCHAR NOT NULL DEFAULT 'resend',
            "apiKey"           TEXT NOT NULL,
            "fromEmail"        VARCHAR NOT NULL,
            "fromName"         VARCHAR,
            "replyTo"          VARCHAR,
            verified           BOOLEAN NOT NULL DEFAULT FALSE,
            "lastError"        TEXT,
            "createdAt"        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            "updatedAt"        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            "businessProfileId" VARCHAR REFERENCES "BusinessProfile"(id) ON DELETE CASCADE
        )
    """)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE "EmailConfig"
              ADD CONSTRAINT uniq_email_config_workspace UNIQUE ("businessProfileId");
        EXCEPTION WHEN duplicate_object OR duplicate_table THEN NULL;
        END $$
    """)


def downgrade() -> None:
    op.execute('DROP TABLE IF EXISTS "EmailConfig"')
