import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4, index=True)
    document_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("documents.id"), nullable=False)
    content: Mapped[str] = mapped_column(String, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)
    page_number: Mapped[int | None] = mapped_column(nullable=True)
    chunk_index: Mapped[int] = mapped_column(nullable=False)

    document: Mapped["Document"] = relationship("Document", back_populates="chunks")
