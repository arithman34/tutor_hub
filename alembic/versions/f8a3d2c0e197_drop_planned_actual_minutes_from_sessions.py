"""drop planned and actual minutes from sessions

Revision ID: f8a3d2c0e197
Revises: c3a1d9e47f02
Create Date: 2026-06-13 22:23:32:683279

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "f8a3d2c0e197"
down_revision: Union[str, None] = "c3a1d9e47f02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("sessions", "planned_minutes")
    op.drop_column("sessions", "actual_minutes")


def downgrade() -> None:
    op.add_column("sessions", sa.Column("planned_minutes", sa.Integer(), nullable=True))
    op.add_column("sessions", sa.Column("actual_minutes", sa.Integer(), nullable=True))
    op.add_column("sessions", sa.Column("actual_minutes", sa.Integer(), nullable=True))
