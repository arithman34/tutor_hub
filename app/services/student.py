import uuid
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.exceptions import ForbiddenError, NotFoundError
from app.models.payee import Payee
from app.models.student import Student
from app.models.user import User
from app.services import google_docs as gdocs_service
from app.utils import cap_name


async def list_students(db: AsyncSession, user: User, q: str = "") -> list[Student]:
    stmt = select(Student).order_by(Student.created_at.desc())
    if user.is_admin:
        stmt = stmt.options(joinedload(Student.user))
    else:
        stmt = stmt.where(Student.user_id == user.id)
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(or_(Student.first_name.ilike(pattern), Student.last_name.ilike(pattern)))
    return list((await db.execute(stmt)).scalars().all())


async def get_student(db: AsyncSession, student_id: uuid.UUID, user: User) -> Student:
    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()
    if not student:
        raise NotFoundError("Student not found")
    if not user.is_admin and student.user_id != user.id:
        raise ForbiddenError("Not authorized to access this student")
    return student


async def create_student(
    db: AsyncSession,
    calling_user: User,
    user_id: uuid.UUID,
    first_name: str,
    last_name: str,
    level: str | None = None,
    hourly_rate: float | None = None,
    payee_id: uuid.UUID | None = None,
    zoom_meeting_id: str | None = None,
    google_doc_id: str | None = None,
    onedrive_shared_link: str | None = None,
) -> Student:
    if not calling_user.is_admin:
        raise ForbiddenError("Only admins can create students")
    student = Student(
        user_id=user_id,
        first_name=cap_name(first_name),
        last_name=cap_name(last_name),
        level=level or None,
        hourly_rate=hourly_rate or None,
        payee_id=payee_id or None,
        zoom_meeting_id=zoom_meeting_id or None,
        google_doc_id=google_doc_id or None,
        onedrive_shared_link=onedrive_shared_link or None,
    )
    db.add(student)
    await db.commit()
    await db.refresh(student)

    if not student.google_doc_id:
        try:
            payee = None
            if student.payee_id:
                payee = (await db.execute(select(Payee).where(Payee.id == student.payee_id))).scalar_one_or_none()
            doc_id = await gdocs_service.create_ilp_document(user_id, student, payee, db)
            student.google_doc_id = doc_id
            await db.commit()
        except Exception:
            pass

    return student


async def update_student(
    db: AsyncSession,
    student_id: uuid.UUID,
    user: User,
    updates: dict,
) -> Student:
    if not user.is_admin:
        raise ForbiddenError("Only admins can update students")
    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()
    if not student:
        raise NotFoundError("Student not found")

    if updates.get("first_name"):
        updates["first_name"] = cap_name(updates["first_name"])
    if updates.get("last_name"):
        updates["last_name"] = cap_name(updates["last_name"])

    for key, value in updates.items():
        setattr(student, key, value)

    student.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(student)
    return student


async def toggle_active(db: AsyncSession, student_id: uuid.UUID, user: User) -> Student:
    if not user.is_admin:
        raise ForbiddenError("Only admins can toggle student active status")
    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()
    if not student:
        raise NotFoundError("Student not found")
    student.is_active = not student.is_active
    await db.commit()
    await db.refresh(student)
    return student


async def delete_student(db: AsyncSession, student_id: uuid.UUID, user: User) -> None:
    if not user.is_admin:
        raise ForbiddenError("Only admins can delete students")
    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()
    if not student:
        raise NotFoundError("Student not found")
    await db.delete(student)
    await db.commit()
