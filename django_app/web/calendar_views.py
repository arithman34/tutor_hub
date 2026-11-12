import logging
from urllib.parse import quote

from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from calendar_integration import services
from calendar_integration.models import GoogleCalendarToken
from students.models import Student

from .auth import login_required

logger = logging.getLogger(__name__)

_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


@login_required
def calendar_page(request):
    return redirect("/sessions")


@login_required
def calendar_create_index(request):
    """GET shows the form, POST creates the event(s) — matches the single
    `/calendar/create` path the original FastAPI router and the template's
    form action both use."""
    if request.method == "POST":
        return calendar_create(request)
    return calendar_create_page(request)


def calendar_create_page(request):
    user = request.user
    token = GoogleCalendarToken.objects.filter(user=user).first()
    if not (token and token.is_connected):
        return redirect("/connections?error=not_connected")

    students = Student.objects.filter(user=user, is_active=True).order_by("first_name", "last_name")
    return render(
        request,
        "calendar/create.html",
        {
            "user": user,
            "active_page": "sessions",
            "students": students,
            "days": _DAYS,
            "form_error": request.GET.get("error"),
        },
    )


def calendar_create(request):
    user = request.user
    data = request.POST
    session_type = data.get("session_type", "oneoff")

    student_id_raw = data.get("student_id", "").strip()
    if not student_id_raw:
        return redirect("/calendar/create?error=no_student")
    student = Student.objects.filter(id=student_id_raw, user=user).first()
    if not student:
        return redirect("/calendar/create?error=no_student")

    title = services.build_event_title(student.first_name)
    location = user.address

    try:
        if session_type == "oneoff":
            services.create_one_off_event(
                user,
                summary=title,
                date_str=data.get("date", ""),
                start_time=data.get("start_time", ""),
                end_time=data.get("end_time", ""),
                location=location,
            )
        else:
            day_configs = []
            for i in range(7):
                if data.get(f"day_{i}_enabled"):
                    day_configs.append(
                        {
                            "weekday": i,
                            "start": data.get(f"day_{i}_start", "09:00"),
                            "end": data.get(f"day_{i}_end", "10:00"),
                        }
                    )
            if not day_configs:
                return redirect("/calendar/create?error=no_days")

            services.create_recurring_events(
                user,
                summary=title,
                day_configs=day_configs,
                start_date_str=data.get("start_date", ""),
                end_date_str=data.get("end_date", "").strip() or None,
                interval_weeks=max(1, int(data.get("interval_weeks", "1") or 1)),
                location=location,
            )
    except Exception as exc:
        # Some exceptions stringify to "" (httpx.ReadTimeout is one), which used to
        # render as a blank error banner. Fall back to the class name, and log the
        # traceback — the redirect is all the user sees, so it can't be the only record.
        logger.exception("Calendar event creation failed for user %s", user.id)
        detail = str(exc) or type(exc).__name__
        return redirect(f"/calendar/create?error={quote(detail)}")

    return redirect("/sessions?created=1")


@login_required
def calendar_connect(request):
    # The same signed state the API's connect endpoint uses, so Google's
    # redirect lands on the one shared callback (calendar_integration.views.CallbackView).
    return redirect(services.build_connect_url(services.sign_connect_state(request.user)))


@login_required
@require_http_methods(["POST"])
def calendar_disconnect(request):
    token = GoogleCalendarToken.objects.filter(user=request.user).first()
    if token:
        services.disconnect_token(token)
    return redirect("/connections")
