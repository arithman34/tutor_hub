from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import create_access_token, create_refresh_token, revoke_refresh_token, verify_password
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User

router = APIRouter(tags=["Web Auth"])
templates = Jinja2Templates(directory="templates")

_REFRESH_COOKIE_MAX_AGE = settings.refresh_token_expire_days * 86400


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(func.count()).select_from(User))
    if result.scalar() == 0:
        return RedirectResponse(url="/setup", status_code=303)
    return templates.TemplateResponse(request, "auth/login.html")


@router.post("/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(password, user.hashed_password) or not user.is_active:
        return templates.TemplateResponse(request, "auth/login.html", {"error": "Invalid email or password"}, status_code=400)

    access_token = create_access_token({"sub": user.email})
    refresh_token = await create_refresh_token(db, user.id)

    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(key="access_token", value=access_token, httponly=True, samesite="lax")
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True, samesite="lax", max_age=_REFRESH_COOKIE_MAX_AGE)
    return response


@router.post("/logout")
async def logout(request: Request, db: AsyncSession = Depends(get_db)):
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        await revoke_refresh_token(db, refresh_token)

    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return response
