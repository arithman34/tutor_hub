from fastapi import APIRouter

from app.api.v1.routers import (
    auth,
    enrollment,
    me,
    payee,
    payment,
    session,
    student,
    subject,
    user,
)
from app.core.config import settings

router = APIRouter(prefix=settings.api_prefix)

router.include_router(auth.router)
router.include_router(me.router)
router.include_router(user.router)
router.include_router(student.router)
router.include_router(payee.router)
router.include_router(session.router)
router.include_router(payment.router)
router.include_router(subject.router)
router.include_router(enrollment.router)
