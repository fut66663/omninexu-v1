"""Add source_filing column to institutional_holdings

Revision ID: a1b2c3d4e5f6
Revises: d8e8c9528f73
Create Date: 2026-07-01 13:50:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "d8e8c9528f73"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("institutional_holdings") as batch_op:
        batch_op.add_column(
            sa.Column("source_filing", sa.String(length=255), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("institutional_holdings") as batch_op:
        batch_op.drop_column("source_filing")
