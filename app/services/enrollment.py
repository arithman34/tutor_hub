import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundError
from app.models.enrollment import Enrollment
from app.models.student import Student
from app.models.user import User


async def _assert_student_access(db: AsyncSession, student_id: uuid.UUID, user: User) -> None:
    if user.is_admin:
        stmt = select(Student).where(Student.id == student_id)
    else:
        stmt = select(Student).where(Student.id == student_id, Student.user_id == user.id)
    if (await db.execute(stmt)).scalar_one_or_none() is None:
        raise NotFoundError("Student not found")


async def enroll_student(
    db: AsyncSession,
    user: User,
    student_id: uuid.UUID,
    subject_id: uuid.UUID,
) -> Enrollment:
    await _assert_student_access(db, student_id, user)
    enrollment = Enrollment(student_id=student_id, subject_id=subject_id)
    db.add(enrollment)
    await db.commit()
    await db.refresh(enrollment)
    return enrollment


async def list_enrollments(db: AsyncSession, user: User, student_id: uuid.UUID) -> list[Enrollment]:
    await _assert_student_access(db, student_id, user)
    result = await db.execute(select(Enrollment).where(Enrollment.student_id == student_id))
    return list(result.scalars().all())


async def remove_enrollment(
    db: AsyncSession,
    user: User,
    student_id: uuid.UUID,
    subject_id: uuid.UUID,
) -> None:
    await _assert_student_access(db, student_id, user)
    result = await db.execute(select(Enrollment).where(Enrollment.student_id == student_id, Enrollment.subject_id == subject_id))
    enrollment = result.scalar_one_or_none()
    if not enrollment:
        raise NotFoundError("Enrollment not found")
    await db.delete(enrollment)
    await db.commit()
