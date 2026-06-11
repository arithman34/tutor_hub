import uuid

from sqlalchemy import ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Enrollment(Base):
    __tablename__ = "enrollments"

    student_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("students.id"), primary_key=True, nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("subjects.id"), primary_key=True, nullable=False)

    student = relationship("Student", back_populates="enrollments")
    subject = relationship("Subject", back_populates="enrollments")
