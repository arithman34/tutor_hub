import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Student(Base):
    __tablename__ = "students"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    payee_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("payees.id"), nullable=True)
    first_name: Mapped[str] = mapped_column(String, nullable=False)
    last_name: Mapped[str] = mapped_column(String, nullable=False)
    level: Mapped[str | None] = mapped_column(String, nullable=True)
    hourly_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    zoom_meeting_id: Mapped[str | None] = mapped_column(String, nullable=True)
    google_doc_id: Mapped[str | None] = mapped_column(String, nullable=True)
    onedrive_shared_link: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="students")
    payee = relationship("Payee", back_populates="students")
    sessions = relationship("Session", back_populates="student")
    documents = relationship("Document", back_populates="student")
