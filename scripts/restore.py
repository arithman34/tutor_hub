import asyncio
import json
import sys
import uuid
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(".env")

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models import Enrollment, Payee, Payment, Session, Student, Subject, User
from app.models.user import PayoutType, UserRole


def _uuid(v):
    return uuid.UUID(v) if v else None


def _dt(v):
    return datetime.fromisoformat(v) if v else None


async def restore(path: Path) -> None:
    data = json.loads(path.read_text())

    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as db:
        print("Clearing existing data...")
        for tbl in ["payments", "enrollments", "sessions", "students", "payees", "subjects", "users"]:
            await db.execute(text(f"DELETE FROM {tbl}"))
        await db.flush()

        print(f"Inserting {len(data.get('users', []))} users...")
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

        print(f"Inserting {len(data.get('subjects', []))} subjects...")
        for row in data.get("subjects", []):
            db.add(Subject(id=_uuid(row["id"]), name=row["name"]))
        await db.flush()

        print(f"Inserting {len(data.get('payees', []))} payees...")
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

        print(f"Inserting {len(data.get('students', []))} students...")
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

        print(f"Inserting {len(data.get('enrollments', []))} enrollments...")
        for row in data.get("enrollments", []):
            db.add(
                Enrollment(
                    student_id=_uuid(row["student_id"]),
                    subject_id=_uuid(row["subject_id"]),
                )
            )
        await db.flush()

        print(f"Inserting {len(data.get('sessions', []))} sessions...")
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

        print(f"Inserting {len(data.get('payments', []))} payments...")
        for row in data.get("payments", []):
            db.add(
                Payment(
                    id=_uuid(row["id"]),
                    user_id=_uuid(row["user_id"]),
                    payee_id=_uuid(row["payee_id"]),
                    amount=Decimal(str(row["amount"])),
                    payment_date=_dt(row["payment_date"]),
                    payment_reference=row.get("payment_reference"),
                    created_at=_dt(row.get("created_at")),
                    updated_at=_dt(row.get("updated_at")),
                )
            )

        await db.commit()
        print("Restore complete.")

    await engine.dispose()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/restore.py <export_file.json>")
        sys.exit(1)

    export_path = Path(sys.argv[1])
    if not export_path.exists():
        print(f"File not found: {export_path}")
        sys.exit(1)

    asyncio.run(restore(export_path))
