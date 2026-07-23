import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class UserRole(enum.Enum):
    admin = "admin"
    tutor = "tutor"
    admin_tutor = "admin_tutor"


class PayoutType(enum.Enum):
    percentage = "percentage"
    hourly = "hourly"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    first_name: Mapped[str] = mapped_column(String, nullable=False)
    last_name: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, values_callable=lambda x: [e.value for e in x], name="userrole"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    address: Mapped[str | None] = mapped_column(String, nullable=True)
    payout_type: Mapped[PayoutType | None] = mapped_column(
        Enum(PayoutType, values_callable=lambda x: [e.value for e in x], name="payouttype"), nullable=True
    )
    payout_percentage: Mapped[float | None] = mapped_column(Float, nullable=True)
    payout_hourly_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    @property
    def is_admin(self) -> bool:
        return self.role in (UserRole.admin, UserRole.admin_tutor)

    @property
    def is_tutor(self) -> bool:
        return self.role in (UserRole.tutor, UserRole.admin_tutor)

    students = relationship("Student", back_populates="user")
    payees = relationship("Payee", back_populates="user")
    sessions = relationship("Session", back_populates="user")
    payments = relationship("Payment", back_populates="user")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (Index("one_admin", "role", unique=True, postgresql_where=(role == UserRole.admin)),)
