"""add admin_tutor role

Revision ID: bcfa16d3bdb6
Revises: 8789d80aa954
Create Date: 2026-06-17 10:59:48.092580

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "bcfa16d3bdb6"
down_revision: Union[str, Sequence[str], None] = "8789d80aa954"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE userrole ADD VALUE 'admin_tutor'")


def downgrade() -> None:
    # PostgreSQL doesn't support DROP VALUE; full enum recreation needed
    op.execute("ALTER TABLE users ALTER COLUMN role TYPE VARCHAR USING role::text")
    op.execute("DROP TYPE userrole")
    op.execute("CREATE TYPE userrole AS ENUM ('admin', 'tutor')")
    op.execute("ALTER TABLE users ALTER COLUMN role TYPE userrole USING role::userrole")
