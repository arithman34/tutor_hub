import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.services import analytics as analytics_service
from app.web.deps import require_admin

router = APIRouter(tags=["Web Analytics"])
templates = Jinja2Templates(directory="templates")


def _uuid_or_none(value: str | None) -> uuid.UUID | None:
    """Empty selects post an empty string; treat anything unparseable as "no filter"."""
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


@router.get("/analytics", response_class=HTMLResponse)
async def analytics_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    options = await analytics_service.get_filter_options(db)
    return templates.TemplateResponse(
        request,
        "analytics/index.html",
        {
            "user": user,
            "active_page": "analytics",
            "granularities": analytics_service.GRANULARITIES,
            **options,
        },
    )


@router.get("/analytics/data", response_class=JSONResponse)
async def analytics_data(
    range: str = Query(default="12m"),
    granularity: str = Query(default="month"),
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    tutor_id: str | None = Query(default=None),
    student_id: str | None = Query(default=None),
    payee_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    now = datetime.now(timezone.utc)
    earliest = await analytics_service.get_earliest_activity(db) if range == "all" else None
    preset, window_start, window_end = analytics_service.resolve_range(range, start, end, earliest, now)

    filters = analytics_service.Filters(
        start=window_start,
        end=window_end,
        granularity=granularity if granularity in analytics_service.GRANULARITIES else "month",
        tutor_id=_uuid_or_none(tutor_id),
        student_id=_uuid_or_none(student_id),
        payee_id=_uuid_or_none(payee_id),
    )
    trends = await analytics_service.get_trends(db, filters, now=now)
    return JSONResponse({"range": preset, **trends})
