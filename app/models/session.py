import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    student_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("students.id"), nullable=False)
    session_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    session_start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    session_end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    planned_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    zoom_meeting_uuid: Mapped[str | None] = mapped_column(String, nullable=True)
    zoom_summary_raw: Mapped[str | None] = mapped_column(String, nullable=True)
    work_covered: Mapped[str | None] = mapped_column(String, nullable=True)
    student_actions: Mapped[str | None] = mapped_column(String, nullable=True)
    tutor_actions: Mapped[str | None] = mapped_column(String, nullable=True)
    next_lesson_focus: Mapped[str | None] = mapped_column(String, nullable=True)
    topic_tags: Mapped[str | None] = mapped_column(String, nullable=True)
    calendar_event_id: Mapped[str | None] = mapped_column(String, nullable=True)
    calendar_recurring_id: Mapped[str | None] = mapped_column(String, nullable=True)
    calendar_html_link: Mapped[str | None] = mapped_column(String, nullable=True)
    is_paid: Mapped[bool] = mapped_column(Boolean, default=False)
    ilp_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="sessions")
    student = relationship("Student", back_populates="sessions")
