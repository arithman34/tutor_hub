"""drop external_transaction_id from payments

Revision ID: d414880f6313
Revises: 1ff4947bc43f
Create Date: 2026-06-14 21:57:54.391550

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d414880f6313"
down_revision: Union[str, Sequence[str], None] = "1ff4947bc43f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("payments", "external_transaction_id")


def downgrade() -> None:
    op.add_column("payments", sa.Column("external_transaction_id", sa.String(), nullable=True))
