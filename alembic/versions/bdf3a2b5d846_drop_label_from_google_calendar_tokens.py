"""drop label from google_calendar_tokens

Revision ID: bdf3a2b5d846
Revises: 0d800a52e78f
Create Date: 2026-07-18 21:49:08.059159

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "bdf3a2b5d846"
down_revision: Union[str, Sequence[str], None] = "0d800a52e78f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("google_calendar_tokens", "label")


def downgrade() -> None:
    op.add_column(
        "google_calendar_tokens",
        sa.Column("label", sa.String(), nullable=False, server_default="Tuition"),
    )
