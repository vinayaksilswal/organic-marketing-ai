"""Add Media.generationStatus and Media.generationError

Revision ID: 012_media_gen_status
Revises: 011_primary_offer
Create Date: 2026-07-30

The video pipeline runs several LLM calls in sequence, each of which may walk a
fallback chain of free models that rate-limit. Held inside the HTTP request,
that regularly exceeded the server timeout. A killed worker sends no response,
so no CORS header reaches the browser and it reports:

    "No 'Access-Control-Allow-Origin' header is present on the requested
     resource"

which is a lie about the cause and sent us looking at CORS config that was
correct all along.

Generation now happens in the background. The asset row is created up front as
PENDING and the client watches it become READY or FAILED.

Existing rows stay NULL, meaning "nothing was ever generated for this" — a
plain upload — which is the correct reading of history.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "012_media_gen_status"
down_revision: Union[str, None] = "011_primary_offer"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('ALTER TABLE "Media" ADD COLUMN IF NOT EXISTS "generationStatus" VARCHAR')
    op.execute('ALTER TABLE "Media" ADD COLUMN IF NOT EXISTS "generationError" TEXT')
    # Anything already carrying a prompt finished successfully.
    op.execute("""
        UPDATE "Media"
           SET "generationStatus" = 'READY'
         WHERE "generationStatus" IS NULL
           AND "prompt" IS NOT NULL
           AND "prompt" <> ''
    """)


def downgrade() -> None:
    op.execute('ALTER TABLE "Media" DROP COLUMN IF EXISTS "generationStatus"')
    op.execute('ALTER TABLE "Media" DROP COLUMN IF EXISTS "generationError"')
