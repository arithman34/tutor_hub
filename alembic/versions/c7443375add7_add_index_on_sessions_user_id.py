"""add index on sessions.user_id

Revision ID: c7443375add7
Revises: c233f6aeb7bc
Create Date: 2026-07-28 21:03:11.122904

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7443375add7'
down_revision: Union[str, Sequence[str], None] = 'c233f6aeb7bc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_sessions_user_id", table_name="sessions")