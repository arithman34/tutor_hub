"""add address to users

Revision ID: 0d800a52e78f
Revises: defd8d03dd87
Create Date: 2026-07-18 21:41:27.939684

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0d800a52e78f"
down_revision: Union[str, Sequence[str], None] = "defd8d03dd87"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("address", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "address")
