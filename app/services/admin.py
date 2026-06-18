import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enrollment import Enrollment
from app.models.payee import Payee
from app.models.payment import Payment
from app.models.session import Session
from app.models.student import Student
from app.models.subject import Subject
from app.models.user import PayoutType, User, UserRole


def _serialize(obj) -> dict:
    out = {}
    for col in obj.__table__.columns:
        val = getattr(obj, col.name)
        if isinstance(val, datetime):
            val = val.isoformat()
        elif isinstance(val, uuid.UUID):
            val = str(val)
        elif isinstance(val, enum.Enum):
            val = val.value
        elif isinstance(val, Decimal):
            val = float(val)
        out[col.name] = val
    return out


async def export_data(db: AsyncSession) -> dict:
    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "version": "1",
        "users": [_serialize(r) for r in (await db.execute(select(User))).scalars().all()],
        "subjects": [_serialize(r) for r in (await db.execute(select(Subject))).scalars().all()],
        "payees": [_serialize(r) for r in (await db.execute(select(Payee))).scalars().all()],
        "students": [_serialize(r) for r in (await db.execute(select(Student))).scalars().all()],
        "enrollments": [_serialize(r) for r in (await db.execute(select(Enrollment))).scalars().all()],
        "sessions": [_serialize(r) for r in (await db.execute(select(Session))).scalars().all()],
        "payments": [_serialize(r) for r in (await db.execute(select(Payment))).scalars().all()],
    }


async def import_data(db: AsyncSession, data: dict) -> None:
    for tbl in ["payments", "enrollments", "sessions", "students", "payees", "subjects", "users"]:
        await db.execute(text(f"DELETE FROM {tbl}"))
    db.expunge_all()

    def _uuid(v):
        return uuid.UUID(v) if v else None

    def _dt(v):
        return datetime.fromisoformat(v) if v else None

    for row in data.get("users", []):
        db.add(
            User(
                id=_uuid(row["id"]),
                email=row["email"],
                hashed_password=row["hashed_password"],
                first_name=row["first_name"],
                last_name=row["last_name"],
                role=UserRole(row["role"]),
                is_active=row["is_active"],
                payout_type=PayoutType(row["payout_type"]) if row.get("payout_type") else None,
                payout_hourly_rate=row.get("payout_hourly_rate"),
                payout_percentage=row.get("payout_percentage"),
                created_at=_dt(row.get("created_at")),
                updated_at=_dt(row.get("updated_at")),
            )
        )
    await db.flush()

    for row in data.get("subjects", []):
        db.add(Subject(id=_uuid(row["id"]), name=row["name"]))
    await db.flush()

    for row in data.get("payees", []):
        db.add(
            Payee(
                id=_uuid(row["id"]),
                user_id=_uuid(row["user_id"]),
                first_name=row["first_name"],
                last_name=row["last_name"],
                email=row.get("email"),
                phone_number=row.get("phone_number"),
                bank_reference_pattern=row.get("bank_reference_pattern"),
                created_at=_dt(row.get("created_at")),
                updated_at=_dt(row.get("updated_at")),
            )
        )
    await db.flush()

    for row in data.get("students", []):
        db.add(
            Student(
                id=_uuid(row["id"]),
                user_id=_uuid(row["user_id"]),
                payee_id=_uuid(row.get("payee_id")),
                first_name=row["first_name"],
                last_name=row["last_name"],
                level=row.get("level"),
                hourly_rate=row.get("hourly_rate"),
                is_active=row.get("is_active", True),
                created_at=_dt(row.get("created_at")),
                updated_at=_dt(row.get("updated_at")),
            )
        )
    await db.flush()

    for row in data.get("enrollments", []):
        db.add(Enrollment(student_id=_uuid(row["student_id"]), subject_id=_uuid(row["subject_id"])))
    await db.flush()

    for row in data.get("sessions", []):
        db.add(
            Session(
                id=_uuid(row["id"]),
                user_id=_uuid(row["user_id"]),
                student_id=_uuid(row["student_id"]),
                session_date=_dt(row["session_date"]),
                session_start_time=_dt(row["session_start_time"]),
                session_end_time=_dt(row["session_end_time"]),
                is_no_show=row.get("is_no_show", False),
                zoom_meeting_uuid=row.get("zoom_meeting_uuid"),
                zoom_summary_raw=row.get("zoom_summary_raw"),
                work_covered=row.get("work_covered"),
                student_actions=row.get("student_actions"),
                tutor_actions=row.get("tutor_actions"),
                next_lesson_focus=row.get("next_lesson_focus"),
                topic_tags=row.get("topic_tags"),
                calendar_event_id=row.get("calendar_event_id"),
                calendar_recurring_id=row.get("calendar_recurring_id"),
                calendar_html_link=row.get("calendar_html_link"),
                ilp_generated_at=_dt(row.get("ilp_generated_at")),
                created_at=_dt(row.get("created_at")),
                updated_at=_dt(row.get("updated_at")),
            )
        )
    await db.flush()

    for row in data.get("payments", []):
        db.add(
            Payment(
                id=_uuid(row["id"]),
                user_id=_uuid(row["user_id"]),
                payee_id=_uuid(row["payee_id"]),
                amount=row["amount"],
                payment_date=_dt(row["payment_date"]),
                payment_reference=row.get("payment_reference"),
                created_at=_dt(row.get("created_at")),
                updated_at=_dt(row.get("updated_at")),
            )
        )

    await db.commit()
