from fastapi import APIRouter

from app.web.routers import auth, dashboard, setup

router = APIRouter()

router.include_router(setup.router)
router.include_router(dashboard.router)
router.include_router(auth.router)
