"""drop truelayer tokens and rename transaction id column

Revision ID: 1ff4947bc43f
Revises: 430eae33957c
Create Date: 2026-06-14 21:01:37.282469

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1ff4947bc43f"
down_revision: Union[str, Sequence[str], None] = "430eae33957c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("truelayer_tokens")
    op.alter_column("payments", "truelayer_transaction_id", new_column_name="external_transaction_id")


def downgrade() -> None:
    op.alter_column("payments", "external_transaction_id", new_column_name="truelayer_transaction_id")
    op.create_table(
        "truelayer_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("access_token", sa.String(), nullable=False),
        sa.Column("refresh_token", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
