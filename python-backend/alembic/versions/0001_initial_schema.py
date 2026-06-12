"""initial_schema

Revision ID: 0001
Revises:
Create Date: 2025-05-14

Uses SQLModel.metadata.create_all() for the initial schema to handle
circular foreign-key dependencies correctly (PostgreSQL resolves them
as long as all tables are created within the same transaction).
"""
from typing import Sequence, Union

from alembic import op
from sqlmodel import SQLModel

import app.models  # noqa: F401 — populate metadata

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    SQLModel.metadata.create_all(bind)


def downgrade() -> None:
    bind = op.get_bind()
    SQLModel.metadata.drop_all(bind)
