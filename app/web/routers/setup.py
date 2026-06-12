import secrets

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import hash_password
from app.core.database import get_db
from app.models.user import User, UserRole

router = APIRouter(tags=["Setup"])
templates = Jinja2Templates(directory="templates")


async def _has_users(db: AsyncSession) -> bool:
    result = await db.execute(select(func.count()).select_from(User))
    return result.scalar() > 0


@router.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request, db: AsyncSession = Depends(get_db)):
    if await _has_users(db):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request, "setup/index.html")


@router.post("/setup")
async def setup_submit(
    request: Request,
    email: str = Form(...),
    first_name: str = Form(...),
    last_name: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    if await _has_users(db):
        return RedirectResponse(url="/login", status_code=303)

    user = User(
        email=email,
        hashed_password=hash_password(password),
        first_name=first_name,
        last_name=last_name,
        role=UserRole.admin,
        is_active=True,
    )
    db.add(user)
    await db.commit()

    return RedirectResponse(url="/login", status_code=303)
