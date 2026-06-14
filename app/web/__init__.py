from fastapi import APIRouter

from app.web.routers import admin, auth, dashboard, payees, payments, sessions, setup, students

router = APIRouter()

router.include_router(setup.router)
router.include_router(auth.router)
router.include_router(dashboard.router)
router.include_router(students.router)
router.include_router(sessions.router)
router.include_router(payments.router)
router.include_router(payees.router)
router.include_router(admin.router)
