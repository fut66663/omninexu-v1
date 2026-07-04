"""add_source_column_to_financial_facts

Revision ID: 45dc05600600
Revises: a1b2c3d4e5f6
Create Date: 2026-07-01 23:21:46.017354

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '45dc05600600'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add source column with backfill."""
    # Step 1: add as nullable
    with op.batch_alter_table('financial_facts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('source', sa.String(length=10), nullable=True))

    # Step 2: backfill from source_filing
    op.execute(
        "UPDATE financial_facts SET source = 'simfin' WHERE source_filing = 'simfin'"
    )
    op.execute(
        "UPDATE financial_facts SET source = 'edgar' WHERE source_filing != 'simfin'"
    )

    # Step 3: make NOT NULL
    with op.batch_alter_table('financial_facts', schema=None) as batch_op:
        batch_op.alter_column('source', nullable=False)


def downgrade() -> None:
    """Drop source column."""
    with op.batch_alter_table('financial_facts', schema=None) as batch_op:
        batch_op.drop_column('source')
