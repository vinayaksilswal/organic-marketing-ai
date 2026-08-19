"""The two stills a clip is generated between, stored beside its prompt.

A video model cannot spell, which is why the call to action is spoken and the
end card is composited. An image model can, so the frame carrying the brand
name and the offer is generated as a still and the clip is built to land on
it. Those prompts were being generated and dropped -- the pipeline returned
them and nothing read the return.

`plan` holds the beat sheet the prompt was written to, so the length a prompt
was built for travels with it. A 30s prompt rendered at 10s is not a shorter
ad, it is a truncated one.

Revision ID: 024_media_keyframes
Revises: 023_media_folders
"""

from alembic import op

revision = "024_media_keyframes"
down_revision = "023_media_folders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('ALTER TABLE "Media" ADD COLUMN IF NOT EXISTS "keyframes" JSONB')
    op.execute('ALTER TABLE "Media" ADD COLUMN IF NOT EXISTS "plan" JSONB')


def downgrade() -> None:
    op.execute('ALTER TABLE "Media" DROP COLUMN IF EXISTS "keyframes"')
    op.execute('ALTER TABLE "Media" DROP COLUMN IF EXISTS "plan"')
