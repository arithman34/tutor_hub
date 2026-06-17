from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.services import dashboard as dashboard_service
from app.web.deps import get_current_user_from_cookie

router = APIRouter(tags=["Web Dashboard"])
templates = Jinja2Templates(directory="templates")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_from_cookie),
):
    if not user.is_admin:
        stats = await dashboard_service.get_tutor_stats(db, user)
    else:
        stats = await dashboard_service.get_admin_stats(db)

    return templates.TemplateResponse(request, "dashboard/index.html", {
        "user": user,
        "active_page": "dashboard",
        **stats,
    })
