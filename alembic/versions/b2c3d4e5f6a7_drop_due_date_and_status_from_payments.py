"""drop due_date and status from payments

Revision ID: b2c3d4e5f6a7
Revises: a7c4e9b1d3f2
Create Date: 2026-06-13

"""
from typing import Union

from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a7c4e9b1d3f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("payments", "due_date")
    op.drop_column("payments", "status")
    op.execute("DROP TYPE IF EXISTS paymentstatus")


def downgrade() -> None:
    pass
