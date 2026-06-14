"""add is_no_show to sessions

Revision ID: ed2f9407efa1
Revises: b2c3d4e5f6a7
Create Date: 2026-06-13 23:29:17.414852

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ed2f9407efa1"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("sessions", sa.Column("is_no_show", sa.Boolean(), nullable=False, server_default="false"))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("sessions", "is_no_show")
