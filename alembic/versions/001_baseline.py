"""Baseline: stamp existing schema

Revision ID: 001_baseline
Revises:
Create Date: 2026-07-26

This is a baseline migration. The schema already exists in production
(created by SQLAlchemy's create_all). This migration exists so Alembic
can track the schema from this point forward. It performs no operations.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
