import json
import uuid

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.exceptions import NotFoundError
from app.models.user import PayoutType, User
from app.services import admin as admin_service
from app.services import user as user_service
from app.web.deps import require_admin

router = APIRouter(prefix="/admin", tags=["Web Admin"])
templates = Jinja2Templates(directory="templates")


@router.get("/users", response_class=HTMLResponse)
async def admin_users(request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(require_admin)):
    tutors = await user_service.list_tutors(db)
    return templates.TemplateResponse(request, "admin/users.html", {
        "user": user, "active_page": "admin_users", "tutors": tutors,
    })


@router.get("/users/new", response_class=HTMLResponse)
async def admin_users_new(request: Request, user: User = Depends(require_admin)):
    return templates.TemplateResponse(request, "admin/users_new.html", {
        "user": user, "active_page": "admin_users", "PayoutType": PayoutType,
    })


@router.post("/users")
async def admin_users_create(
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    payout_type: str = Form(default=""),
    payout_hourly_rate: float = Form(default=None),
    payout_percentage: float = Form(default=None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    result = await user_service.create_tutor(
        db,
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
        payout_type=payout_type or None,
        payout_hourly_rate=payout_hourly_rate,
        payout_percentage=payout_percentage,
    )
    if result is None:
        return RedirectResponse(url="/admin/users/new", status_code=303)
    return RedirectResponse(url="/admin/users", status_code=303)


@router.post("/users/{user_id}/toggle-active")
async def admin_toggle_active(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    try:
        await user_service.toggle_active(db, user_id)
    except (NotFoundError, Exception):
        pass
    return RedirectResponse(url="/admin/users", status_code=303)


@router.post("/users/{user_id}/update-payout")
async def admin_update_payout(
    user_id: uuid.UUID,
    payout_type: str = Form(default=""),
    payout_hourly_rate: float = Form(default=None),
    payout_percentage: float = Form(default=None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    try:
        await user_service.update_payout(db, user_id, payout_type or None, payout_hourly_rate, payout_percentage)
    except (NotFoundError, Exception):
        pass
    return RedirectResponse(url="/admin/users", status_code=303)


@router.get("/data", response_class=HTMLResponse)
async def admin_data(request: Request, user: User = Depends(require_admin)):
    return templates.TemplateResponse(request, "admin/data.html", {"user": user, "active_page": "admin_data"})


@router.get("/data/export")
async def admin_export(db: AsyncSession = Depends(get_db), user: User = Depends(require_admin)):
    from datetime import datetime
    data = await admin_service.export_data(db)
    filename = f"tutorhub_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    return Response(
        content=json.dumps(data, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/data/import")
async def admin_import(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    raw = await file.read()
    data = json.loads(raw)
    await admin_service.import_data(db, data)
    return RedirectResponse(url="/admin/data?imported=1", status_code=303)
