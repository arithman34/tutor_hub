"""capitalise existing names

Revision ID: c3a1d9e47f02
Revises: ab881e52e6f8
Create Date: 2026-06-13 18:47:12.435667

"""

from typing import Sequence, Union

from alembic import op

revision: str = "c3a1d9e47f02"
down_revision: Union[str, None] = "ab881e52e6f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CAP = "UPPER(LEFT({col}, 1)) || SUBSTRING({col}, 2)"


def _cap_table(table: str) -> None:
    for col in ("first_name", "last_name"):
        expr = _CAP.format(col=col)
        op.execute(f"UPDATE {table} SET {col} = {expr} WHERE {col} <> ''")


def upgrade() -> None:
    _cap_table("users")
    _cap_table("students")
    _cap_table("payees")


def downgrade() -> None:
    pass
