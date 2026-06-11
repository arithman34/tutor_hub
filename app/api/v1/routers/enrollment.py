import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.core.database import get_db
from app.models.enrollment import Enrollment
from app.models.student import Student
from app.models.user import User
from app.schemas.enrollment import EnrollmentCreate, EnrollmentResponse

router = APIRouter(prefix="/enrollments", tags=["enrollments"])


@router.post("/", response_model=EnrollmentResponse, status_code=status.HTTP_201_CREATED)
async def enroll_student(
    enrollment_in: EnrollmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify the student belongs to the current tutor
    student_result = await db.execute(
        select(Student).where(
            Student.id == enrollment_in.student_id,
            Student.user_id == current_user.id,
        )
    )
    if student_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    enrollment = Enrollment(
        student_id=enrollment_in.student_id,
        subject_id=enrollment_in.subject_id,
    )
    db.add(enrollment)
    await db.commit()
    await db.refresh(enrollment)
    return enrollment


@router.get("/students/{student_id}", response_model=list[EnrollmentResponse])
async def get_student_enrollments(
    student_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    student_result = await db.execute(
        select(Student).where(Student.id == student_id, Student.user_id == current_user.id)
    )
    if student_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    result = await db.execute(
        select(Enrollment).where(Enrollment.student_id == student_id)
    )
    return result.scalars().all()


@router.delete("/students/{student_id}/subjects/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_enrollment(
    student_id: uuid.UUID,
    subject_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    student_result = await db.execute(
        select(Student).where(Student.id == student_id, Student.user_id == current_user.id)
    )
    if student_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    result = await db.execute(
        select(Enrollment).where(
            Enrollment.student_id == student_id,
            Enrollment.subject_id == subject_id,
        )
    )
    enrollment = result.scalar_one_or_none()
    if enrollment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment not found")

    await db.delete(enrollment)
    await db.commit()
