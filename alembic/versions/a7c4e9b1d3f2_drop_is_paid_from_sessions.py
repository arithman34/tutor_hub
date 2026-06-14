"""drop is_paid from sessions

Revision ID: a7c4e9b1d3f2
Revises: f8a3d2c0e197
Create Date: 2026-06-13 23:45:37.872912

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "a7c4e9b1d3f2"
down_revision: Union[str, None] = "f8a3d2c0e197"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("sessions", "is_paid")


def downgrade() -> None:
    op.add_column("sessions", sa.Column("is_paid", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("sessions", sa.Column("is_paid", sa.Boolean(), nullable=False, server_default="false"))
