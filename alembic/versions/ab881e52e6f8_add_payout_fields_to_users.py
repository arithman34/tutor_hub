"""add payout fields to users

Revision ID: ab881e52e6f8
Revises: d3e5f3196bbb
Create Date: 2026-06-13 15:53:25.916045

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ab881e52e6f8'
down_revision: Union[str, Sequence[str], None] = 'd3e5f3196bbb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    payout_type_enum = sa.Enum('percentage', 'hourly', name='payouttype')
    payout_type_enum.create(op.get_bind())
    op.add_column('users', sa.Column('payout_type', payout_type_enum, nullable=True))
    op.add_column('users', sa.Column('payout_percentage', sa.Float(), nullable=True))
    op.add_column('users', sa.Column('payout_hourly_rate', sa.Float(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'payout_hourly_rate')
    op.drop_column('users', 'payout_percentage')
    op.drop_column('users', 'payout_type')
    sa.Enum(name='payouttype').drop(op.get_bind())
