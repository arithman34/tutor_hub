from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import verify_password
from app.core.database import get_db
from app.models.user import User, UserRole
from app.services import user as user_service
from app.web.deps import get_current_user_from_cookie

router = APIRouter(tags=["Web Profile"])
templates = Jinja2Templates(directory="templates")


@router.get("/profile", response_class=HTMLResponse)
async def profile_page(
    request: Request,
    success: str = Query(default=""),
    error: str = Query(default=""),
    user: User = Depends(get_current_user_from_cookie),
):
    return templates.TemplateResponse(request, "profile/index.html", {
        "user": user,
        "active_page": "profile",
        "success": success,
        "error": error,
    })


@router.post("/profile/update")
async def profile_update(
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    role: str = Form(""),
    address: str = Form(""),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_from_cookie),
):
    if email != user.email:
        result = await db.execute(select(User).where(User.email == email))
        if result.scalar_one_or_none():
            return RedirectResponse(url="/profile?error=email_taken", status_code=303)

    new_role: UserRole | None = None
    if user.is_admin and role in ("admin", "admin_tutor"):
        new_role = UserRole(role)

    await user_service.update_profile(db, user_id=user.id, email=email, first_name=first_name, last_name=last_name, role=new_role, address=address)
    return RedirectResponse(url="/profile?success=details", status_code=303)


@router.post("/profile/password")
async def profile_password(
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_from_cookie),
):
    if not verify_password(current_password, user.hashed_password):
        return RedirectResponse(url="/profile?error=wrong_password", status_code=303)
    if new_password != confirm_password:
        return RedirectResponse(url="/profile?error=password_mismatch", status_code=303)
    await user_service.update_profile(db, user_id=user.id, password=new_password)
    return RedirectResponse(url="/profile?success=password", status_code=303)
