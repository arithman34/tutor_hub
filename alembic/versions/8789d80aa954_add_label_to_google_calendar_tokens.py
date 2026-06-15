"""add label to google_calendar_tokens

Revision ID: 8789d80aa954
Revises: ae141747e4d5
Create Date: 2026-06-15 15:49:14.258580

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8789d80aa954"
down_revision: Union[str, Sequence[str], None] = "ae141747e4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "google_calendar_tokens",
        sa.Column("label", sa.String(), nullable=False, server_default="Tuition"),
    )


def downgrade() -> None:
    op.drop_column("google_calendar_tokens", "label")
