from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.google_calendar_token import GoogleCalendarToken
from app.models.user import User
from app.web.deps import get_current_user_from_cookie

router = APIRouter(prefix="/connections", tags=["Connections"])
templates = Jinja2Templates(directory="templates")


@router.get("", response_class=HTMLResponse)
async def connections_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_from_cookie),
):
    result = await db.execute(
        select(GoogleCalendarToken).where(GoogleCalendarToken.user_id == user.id)
    )
    token = result.scalar_one_or_none()
    google_connected = token is not None

    error = request.query_params.get("error")
    error_msg = None
    if error == "access_denied":
        error_msg = "Google access was denied. Please try connecting again."
    elif error == "invalid_state":
        error_msg = "Security check failed. Please try connecting again."
    elif error == "token_exchange_failed":
        error_msg = "Failed to complete Google authentication. Please try again."
    elif error == "not_connected":
        error_msg = "Connect Google Calendar before creating sessions."

    return templates.TemplateResponse(
        request,
        "connections/index.html",
        {
            "user": user,
            "active_page": "connections",
            "google_connected": google_connected,
            "connected_flash": request.query_params.get("connected"),
            "error_msg": error_msg,
        },
    )
