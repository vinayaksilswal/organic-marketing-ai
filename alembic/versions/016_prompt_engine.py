"""Prompt engine tables

Revision ID: 016_prompt_engine
Revises: 015_billing
Create Date: 2026-07-31

The prompt engine shipped five new models with no migration. create_all() adds
tables on a fresh database but the deployed one is migrated, so on production
these tables would simply not exist and every call to the engine would fail
with UndefinedTable. This is the same class of drift that migration 006 had to
repair for 146 columns.

Column names are quoted to preserve the camelCase the models declare —
unquoted identifiers are folded to lowercase by Postgres and would not match.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "016_prompt_engine"
down_revision: Union[str, None] = "015_billing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS "PromptVersion" (
            id                  VARCHAR PRIMARY KEY,
            "businessProfileId" VARCHAR NOT NULL REFERENCES "BusinessProfile"(id) ON DELETE CASCADE,
            version             INTEGER NOT NULL DEFAULT 1,
            target_model        VARCHAR NOT NULL DEFAULT 'runway',
            prompt_json         JSON NOT NULL,
            positive_prompt     TEXT,
            negative_prompt     JSON,
            motivator           VARCHAR,
            seed                INTEGER,
            "createdAt"         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            "updatedAt"         TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE "PromptVersion"
              ADD CONSTRAINT uniq_prompt_version_per_workspace
              UNIQUE ("businessProfileId", version);
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)
    op.execute(
        'CREATE INDEX IF NOT EXISTS ix_prompt_version_workspace '
        'ON "PromptVersion" ("businessProfileId")'
    )

    op.execute("""
        CREATE TABLE IF NOT EXISTS "PromptValidationLog" (
            id                 VARCHAR PRIMARY KEY,
            "promptVersionId"  VARCHAR NOT NULL REFERENCES "PromptVersion"(id) ON DELETE CASCADE,
            is_valid           BOOLEAN NOT NULL DEFAULT FALSE,
            errors             JSON NOT NULL DEFAULT '[]'::json,
            detailed_checks    JSON NOT NULL DEFAULT '{}'::json,
            "createdAt"        TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE "PromptValidationLog"
              ADD CONSTRAINT uniq_validation_per_prompt UNIQUE ("promptVersionId");
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS "ModelRoutingRule" (
            id                       VARCHAR PRIMARY KEY,
            model_name               VARCHAR NOT NULL,
            prompt_template          JSON NOT NULL,
            supports_negative_prompt BOOLEAN NOT NULL DEFAULT TRUE,
            max_word_budget          INTEGER NOT NULL DEFAULT 85,
            "createdAt"              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            "updatedAt"              TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE "ModelRoutingRule"
              ADD CONSTRAINT uniq_model_name UNIQUE (model_name);
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS "GoldenDatasetSample" (
            id                      VARCHAR PRIMARY KEY,
            dataset_name            VARCHAR NOT NULL DEFAULT 'default_golden_dataset',
            intent                  VARCHAR NOT NULL,
            target_model            VARCHAR NOT NULL,
            customer_motivator      VARCHAR,
            expected_safety_pass    BOOLEAN NOT NULL DEFAULT TRUE,
            expected_heuristic_pass BOOLEAN NOT NULL DEFAULT TRUE,
            payload_sample          JSON NOT NULL,
            "createdAt"             TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS "CaptionVersion" (
            id                    VARCHAR PRIMARY KEY,
            "businessProfileId"   VARCHAR NOT NULL REFERENCES "BusinessProfile"(id) ON DELETE CASCADE,
            version               INTEGER NOT NULL DEFAULT 1,
            caption_text          TEXT NOT NULL,
            customer_motivator    VARCHAR,
            brand_language_anchor TEXT,
            product_feature       VARCHAR,
            is_valid              BOOLEAN NOT NULL DEFAULT FALSE,
            validation_errors     JSON NOT NULL DEFAULT '[]'::json,
            detailed_checks       JSON NOT NULL DEFAULT '{}'::json,
            generation_method     VARCHAR NOT NULL DEFAULT 'template',
            "createdAt"           TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE "CaptionVersion"
              ADD CONSTRAINT uniq_caption_version_per_workspace
              UNIQUE ("businessProfileId", version);
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)
    op.execute(
        'CREATE INDEX IF NOT EXISTS ix_caption_version_workspace '
        'ON "CaptionVersion" ("businessProfileId")'
    )


def downgrade() -> None:
    op.execute('DROP TABLE IF EXISTS "CaptionVersion"')
    op.execute('DROP TABLE IF EXISTS "GoldenDatasetSample"')
    op.execute('DROP TABLE IF EXISTS "ModelRoutingRule"')
    op.execute('DROP TABLE IF EXISTS "PromptValidationLog"')
    op.execute('DROP TABLE IF EXISTS "PromptVersion"')
