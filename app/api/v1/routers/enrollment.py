import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.core.database import get_db
from app.exceptions import NotFoundError
from app.models.user import User
from app.schemas.enrollment import EnrollmentCreate, EnrollmentResponse
from app.services import enrollment as enrollment_service

router = APIRouter(prefix="/enrollments", tags=["enrollments"])


@router.post("/", response_model=EnrollmentResponse, status_code=status.HTTP_201_CREATED)
async def enroll_student(
    enrollment_in: EnrollmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await enrollment_service.enroll_student(db, current_user, enrollment_in.student_id, enrollment_in.subject_id)
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")


@router.get("/students/{student_id}", response_model=list[EnrollmentResponse])
async def get_student_enrollments(
    student_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await enrollment_service.list_enrollments(db, current_user, student_id)
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")


@router.delete("/students/{student_id}/subjects/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_enrollment(
    student_id: uuid.UUID,
    subject_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        await enrollment_service.remove_enrollment(db, current_user, student_id, subject_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
