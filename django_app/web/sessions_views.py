import logging
import uuid
from datetime import datetime, timedelta, timezone

from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from calendar_integration import services as calendar_service
from calendar_integration.models import GoogleCalendarToken
from students.models import Student
from tutoring_sessions.models import Session

from . import ai
from .auth import login_required

logger = logging.getLogger(__name__)

_PERIOD_WINDOWS: dict[str, tuple[int, int]] = {
    "past": (-90, 0),
    "today": (-1, 1),
    "future": (0, 90),
    "all": (-180, 180),
}

# Calendar rows rendered per page. The filtered list still lives in memory; this
# caps how much HTML the browser has to parse and paint.
_PAGE_SIZE = 50


def _parse_dt(date_str: str, time_str: str) -> datetime:
    return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)


def _visible_session_or_none(session_id, user) -> Session | None:
    try:
        session = Session.objects.select_related("student", "user").get(id=session_id)
    except (Session.DoesNotExist, ValueError, TypeError):
        return None
    if not user.is_admin and session.user_id != user.id:
        return None
    return session


@login_required
def sessions_list(request):
    user = request.user
    q = request.GET.get("q", "")

    if not user.is_tutor:
        # Admins only see sessions that originated from a Google Calendar
        # event — the simple logged-sessions list, not the live calendar view.
        qs = Session.objects.select_related("student", "user").filter(calendar_event_id__isnull=False)
        if q:
            qs = qs.filter(Q(student__first_name__icontains=q) | Q(student__last_name__icontains=q))
        sessions = qs.order_by("-session_date")
        return render(request, "sessions/index.html", {"user": user, "active_page": "sessions", "sessions": sessions, "q": q})

    return _sessions_calendar_view(request, user, q)


def _sessions_calendar_view(request, user, q):
    """Tutors see their live Google Calendar ("Tutoring") events merged with
    which ones have already been logged as a Session — not the plain
    logged-sessions list admins get."""
    token = GoogleCalendarToken.objects.filter(user=user).first()
    if not token:
        return redirect("/connections?error=not_connected")

    status = request.GET.get("status")
    period = request.GET.get("period")
    page = max(1, int(request.GET.get("page", 1) or 1))

    if status is None and period is None:
        saved_status = request.COOKIES.get("sessions_status", "all")
        saved_period = request.COOKIES.get("sessions_period", "all")
        if saved_status != "all" or saved_period != "all":
            redirect_url = f"/sessions?status={saved_status}&period={saved_period}"
            if q:
                redirect_url += f"&q={q}"
            return redirect(redirect_url)

    status = status or "all"
    period = period or "all"

    now = datetime.now(timezone.utc)
    days_before, days_after = _PERIOD_WINDOWS.get(period, _PERIOD_WINDOWS["all"])
    time_min = now + timedelta(days=days_before)
    time_max = now + timedelta(days=days_after)

    error = None
    events = []
    try:
        events = calendar_service.fetch_events(user, time_min, time_max)
    except Exception as exc:
        logger.exception("Fetching Google Calendar events failed for user %s", user.id)
        error = str(exc) or type(exc).__name__

    logged_by_event = dict(Session.objects.filter(user=user, calendar_event_id__isnull=False).values_list("calendar_event_id", "id"))

    students = Student.objects.filter(user=user, is_active=True)
    student_by_name = {f"{s.first_name} {s.last_name}": s for s in students}
    student_by_first = {s.first_name: s for s in students}

    items = []
    for event in events:
        parsed = calendar_service.parse_event(event)
        session_id = logged_by_event.get(parsed["event_id"])
        student = student_by_name.get(parsed["student_name"]) or student_by_first.get(parsed["student_name"])
        items.append(
            {
                **parsed,
                "logged": session_id is not None,
                "session_id": str(session_id) if session_id else None,
                "student_id": str(student.id) if student else None,
            }
        )

    today_str = now.strftime("%Y-%m-%d")
    past = sorted((i for i in items if i["date"] <= today_str), key=lambda i: f"{i['date']}T{i['start_time'] or '00:00'}", reverse=True)
    future = sorted((i for i in items if i["date"] > today_str), key=lambda i: f"{i['date']}T{i['start_time'] or '00:00'}")
    items = past + future

    if q:
        q_lower = q.lower()
        items = [i for i in items if q_lower in (i.get("summary") or "").lower()]
    if status == "logged":
        items = [i for i in items if i["logged"]]
    elif status == "unlogged":
        items = [i for i in items if not i["logged"]]
    if period == "past":
        items = [i for i in items if i["date"] < today_str]
    elif period == "today":
        items = [i for i in items if i["date"] == today_str]
    elif period == "future":
        items = [i for i in items if i["date"] > today_str]

    # Paginate last, so counts and page bounds reflect the filtered set.
    total_items = len(items)
    total_pages = max(1, -(-total_items // _PAGE_SIZE))
    page = min(page, total_pages)
    page_start = (page - 1) * _PAGE_SIZE
    items = items[page_start : page_start + _PAGE_SIZE]

    response = render(
        request,
        "sessions/google.html",
        {
            "user": user,
            "active_page": "sessions",
            "items": items,
            "status": status,
            "period": period,
            "q": q,
            "error": error,
            "page": page,
            "total_pages": total_pages,
            "total_items": total_items,
            "page_start": page_start + 1 if total_items else 0,
            "page_end": page_start + len(items),
        },
    )
    response.set_cookie("sessions_status", status, max_age=60 * 60 * 24 * 30, httponly=True, samesite="Lax")
    response.set_cookie("sessions_period", period, max_age=60 * 60 * 24 * 30, httponly=True, samesite="Lax")
    return response


@login_required
def sessions_new(request):
    user = request.user
    if not user.is_tutor:
        return redirect("/sessions")

    students = Student.objects.filter(user=user, is_active=True).order_by("first_name")
    return render(
        request,
        "sessions/new.html",
        {
            "user": user,
            "active_page": "sessions",
            "students": students,
            "prefill_student_id": request.GET.get("student_id", ""),
            "prefill_date": request.GET.get("date", ""),
            "prefill_start": request.GET.get("start_time", ""),
            "prefill_end": request.GET.get("end_time", ""),
            "prefill_event_id": request.GET.get("event_id", ""),
            "prefill_html_link": request.GET.get("html_link", ""),
        },
    )


def sessions_create(request):
    user = request.user
    if not user.is_tutor:
        return redirect("/sessions")

    start_dt = _parse_dt(request.POST["session_date"], request.POST["start_time"])
    end_dt = _parse_dt(request.POST["session_date"], request.POST["end_time"])

    Session.objects.create(
        user=user,
        student_id=uuid.UUID(request.POST["student_id"]),
        session_date=start_dt,
        session_start_time=start_dt,
        session_end_time=end_dt,
        is_no_show=bool(request.POST.get("is_no_show")),
        zoom_summary_raw=request.POST.get("zoom_summary_raw") or None,
        work_covered=request.POST.get("work_covered") or None,
        student_actions=request.POST.get("student_actions") or None,
        tutor_actions=request.POST.get("tutor_actions") or None,
        next_lesson_focus=request.POST.get("next_lesson_focus") or None,
        topic_tags=request.POST.get("topic_tags") or None,
        calendar_event_id=request.POST.get("calendar_event_id") or None,
        calendar_html_link=request.POST.get("calendar_html_link") or None,
    )
    return redirect("/sessions")


@login_required
def sessions_index(request):
    """GET lists sessions, POST creates one — same `/sessions` path used by
    the original FastAPI router and by `new.html`'s form action."""
    if request.method == "POST":
        return sessions_create(request)
    return sessions_list(request)


@login_required
@require_http_methods(["POST"])
def sessions_zoom_parse(request):
    if not request.user.is_tutor:
        return JsonResponse({"error": "Admins cannot log sessions"}, status=403)

    zoom_summary = request.POST.get("zoom_summary", "")
    try:
        parsed = ai.parse_zoom_summary(zoom_summary)
    except Exception:
        return JsonResponse({"error": "Could not parse summary"}, status=502)

    return JsonResponse(
        {
            "work_covered": parsed.work_covered,
            "student_actions": parsed.student_actions,
            "tutor_actions": parsed.tutor_actions,
            "next_lesson_focus": parsed.next_lesson_focus,
            "topic_tags": parsed.topic_tags,
        }
    )


@login_required
def session_detail(request, session_id):
    user = request.user
    session = _visible_session_or_none(session_id, user)
    if session is None:
        return redirect("/sessions")

    students = Student.objects.filter(user=user, is_active=True).order_by("first_name") if user.is_tutor else []

    return render(
        request, "sessions/detail.html", {"user": user, "active_page": "sessions", "session": session, "students": students}
    )


@login_required
@require_http_methods(["POST"])
def session_update(request, session_id):
    user = request.user
    session = _visible_session_or_none(session_id, user)
    if session is None:
        return redirect("/sessions")

    data = request.POST
    session.is_no_show = bool(data.get("is_no_show"))

    if data.get("student_id"):
        session.student_id = uuid.UUID(data["student_id"])
    if data.get("session_date") and data.get("start_time") and data.get("end_time"):
        start_dt = _parse_dt(data["session_date"], data["start_time"])
        end_dt = _parse_dt(data["session_date"], data["end_time"])
        session.session_date = start_dt
        session.session_start_time = start_dt
        session.session_end_time = end_dt

    # The "Details" form (date/time/no-show) doesn't include these fields —
    # only the separate notes form does. Only touch them when present, so
    # fixing a session's time doesn't silently wipe its notes.
    for field in ("work_covered", "student_actions", "tutor_actions", "next_lesson_focus", "topic_tags"):
        if field in data:
            setattr(session, field, data.get(field) or None)

    session.save()
    return redirect(f"/sessions/{session_id}")


@login_required
@require_http_methods(["POST"])
def session_delete(request, session_id):
    session = _visible_session_or_none(session_id, request.user)
    if session is not None:
        session.delete()
    return redirect("/sessions")
