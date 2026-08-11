"""Pause automation per workspace.

Defaults to false and is non-nullable, so every existing workspace keeps
running. A migration that paused live accounts would be silent and would look
exactly like the automation being broken.

Revision ID: 020_automation_paused
Revises: 019_media_has_audio
"""
from typing import Union

from alembic import op

revision: str = "020_automation_paused"
down_revision: Union[str, None] = "019_media_has_audio"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        'ALTER TABLE "BusinessProfile" '
        'ADD COLUMN IF NOT EXISTS "automationPaused" BOOLEAN NOT NULL DEFAULT FALSE'
    )


def downgrade() -> None:
    op.execute('ALTER TABLE "BusinessProfile" DROP COLUMN IF EXISTS "automationPaused"')
