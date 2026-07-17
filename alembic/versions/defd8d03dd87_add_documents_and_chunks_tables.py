"""add documents and chunks tables

Revision ID: defd8d03dd87
Revises: 751eb0ebfd2a
Create Date: 2026-07-12 13:32:18.869183

"""

from typing import Sequence, Union

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "defd8d03dd87"
down_revision: Union[str, Sequence[str], None] = "751eb0ebfd2a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("document_type", sa.String(50), nullable=False),
        sa.Column("subject", sa.String(100), nullable=False),
        sa.Column("level", sa.String(50), nullable=False),
        sa.Column("exam_board", sa.String(100), nullable=True),
        sa.Column("student_id", sa.Uuid(), nullable=True),
        sa.Column("source_url", sa.String(255), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_documents_id", "documents", ["id"])

    op.create_table(
        "chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("content", sa.String(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chunks_id", "chunks", ["id"])


def downgrade() -> None:
    op.drop_index("ix_chunks_id", table_name="chunks")
    op.drop_table("chunks")
    op.drop_index("ix_documents_id", table_name="documents")
    op.drop_table("documents")
