import uuid
from datetime import date, datetime, timezone

from django.http import JsonResponse
from django.shortcuts import render

from analytics import services as analytics_service

from .auth import admin_required


def _uuid_or_none(value: str | None):
    """Empty selects post an empty string; treat anything unparseable as "no filter"."""
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


def _date_or_none(value: str | None):
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


@admin_required
def analytics_page(request):
    options = analytics_service.get_filter_options()
    return render(
        request,
        "analytics/index.html",
        {
            "user": request.user,
            "active_page": "analytics",
            "granularities": analytics_service.GRANULARITIES,
            **options,
        },
    )


@admin_required
def analytics_data(request):
    range_ = request.GET.get("range", "12m")
    granularity = request.GET.get("granularity", "month")
    start = _date_or_none(request.GET.get("start"))
    end = _date_or_none(request.GET.get("end"))

    now = datetime.now(timezone.utc)
    earliest = analytics_service.get_earliest_activity() if range_ == "all" else None
    preset, window_start, window_end = analytics_service.resolve_range(range_, start, end, earliest, now)

    filters = analytics_service.Filters(
        start=window_start,
        end=window_end,
        granularity=granularity if granularity in analytics_service.GRANULARITIES else "month",
        tutor_id=_uuid_or_none(request.GET.get("tutor_id")),
        student_id=_uuid_or_none(request.GET.get("student_id")),
        payee_id=_uuid_or_none(request.GET.get("payee_id")),
    )
    trends = analytics_service.get_trends(filters, now=now)
    return JsonResponse({"range": preset, **trends})
