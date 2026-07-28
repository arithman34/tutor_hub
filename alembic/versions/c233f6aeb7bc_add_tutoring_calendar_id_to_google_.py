"""add tutoring_calendar_id to google_calendar_tokens

Revision ID: c233f6aeb7bc
Revises: bdf3a2b5d846
Create Date: 2026-07-28 15:44:30.460522

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c233f6aeb7bc"
down_revision: Union[str, Sequence[str], None] = "bdf3a2b5d846"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("google_calendar_tokens", sa.Column("tutoring_calendar_id", sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("google_calendar_tokens", "tutoring_calendar_id")
