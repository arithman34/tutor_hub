import uuid
from datetime import datetime, timezone

from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from students.models import Student
from tutoring_sessions.models import Session

from . import ai
from .auth import login_required


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
    """The simple logged-sessions list used by both roles (filtered to the
    tutor's own sessions unless admin). The FastAPI app shows tutors a
    separate view here backed by live Google Calendar events; that page
    depends on the /connections and /calendar web pages, which aren't ported
    yet, so this is the one list for now — see django_app/README.md."""
    user = request.user
    q = request.GET.get("q", "")

    qs = Session.objects.select_related("student", "user") if user.is_admin else Session.objects.filter(user=user).select_related("student")
    if q:
        qs = qs.filter(Q(student__first_name__icontains=q) | Q(student__last_name__icontains=q))
    sessions = qs.order_by("-session_date")

    return render(request, "sessions/index.html", {"user": user, "active_page": "sessions", "sessions": sessions, "q": q})


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
