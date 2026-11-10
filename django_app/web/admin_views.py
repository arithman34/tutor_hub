import json
import logging
import secrets
import string
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from urllib.parse import quote

import resend
from django.conf import settings
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from accounts.models import User, UserRole
from billing.models import Payee, Payment
from students.models import Student
from tutoring_sessions.models import Session

from .auth import admin_required

logger = logging.getLogger(__name__)


def _generate_temp_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _tutor_has_data(user_id) -> bool:
    return (
        Student.objects.filter(user_id=user_id).exists()
        or Session.objects.filter(user_id=user_id).exists()
        or Payment.objects.filter(user_id=user_id).exists()
        or Payee.objects.filter(user_id=user_id).exists()
    )


@admin_required
def admin_users_index(request):
    """GET lists tutors, POST creates one — matches the single `/admin/users`
    path the original FastAPI router and `users_new.html`'s form both use."""
    if request.method == "POST":
        return admin_users_create(request)
    return admin_users(request)


def admin_users(request):
    tutors = User.objects.filter(role=UserRole.TUTOR).order_by("-created_at")
    deletable = {t.id: not _tutor_has_data(t.id) for t in tutors}
    return render(request, "admin/users.html", {"user": request.user, "active_page": "admin_users", "tutors": tutors, "deletable": deletable})


@admin_required
def admin_users_new(request):
    return render(
        request,
        "admin/users_new.html",
        {"user": request.user, "active_page": "admin_users", "error": request.GET.get("error", "")},
    )


def admin_users_create(request):
    data = request.POST
    email = data.get("email", "")
    if User.objects.filter(email=email).exists():
        return redirect("/admin/users/new?error=email_taken")

    temp_password = _generate_temp_password()
    payout_type = data.get("payout_type") or None
    payout_hourly_rate = data.get("payout_hourly_rate") or None
    payout_percentage = data.get("payout_percentage") or None

    tutor = User.objects.create_user(
        email=email,
        password=temp_password,
        first_name=data.get("first_name", "").strip().title(),
        last_name=data.get("last_name", "").strip().title(),
        role=UserRole.TUTOR,
        is_active=True,
        payout_type=payout_type,
        payout_hourly_rate=float(payout_hourly_rate) if payout_hourly_rate else None,
        payout_percentage=float(payout_percentage) if payout_percentage else None,
    )

    try:
        resend.api_key = settings.RESEND_API_KEY
        resend.Emails.send(
            {
                "from": settings.FROM_EMAIL,
                "to": [email],
                "subject": "Welcome to TutorHub — your account details",
                "text": (
                    f"Hi {tutor.first_name},\n\n"
                    f"An account has been created for you on TutorHub.\n\n"
                    f"Email: {email}\n"
                    f"Temporary password: {temp_password}\n\n"
                    "Please log in and change your password as soon as possible.\n"
                ),
            }
        )
    except Exception:
        logger.exception("Failed to send welcome email to %s", email)

    return redirect("/admin/users")


@admin_required
@require_http_methods(["POST"])
def admin_toggle_active(request, user_id):
    tutor = User.objects.filter(id=user_id, role=UserRole.TUTOR).first()
    if tutor is not None:
        tutor.is_active = not tutor.is_active
        tutor.save(update_fields=["is_active", "updated_at"])
    return redirect("/admin/users")


@admin_required
@require_http_methods(["POST"])
def admin_update_payout(request, user_id):
    tutor = User.objects.filter(id=user_id, role=UserRole.TUTOR).first()
    if tutor is not None:
        data = request.POST
        payout_type = data.get("payout_type") or None
        payout_hourly_rate = data.get("payout_hourly_rate") or None
        payout_percentage = data.get("payout_percentage") or None
        tutor.payout_type = payout_type
        tutor.payout_hourly_rate = float(payout_hourly_rate) if payout_hourly_rate else None
        tutor.payout_percentage = float(payout_percentage) if payout_percentage else None
        tutor.save()
    return redirect("/admin/users")


@admin_required
@require_http_methods(["POST"])
def admin_delete_tutor(request, user_id):
    tutor = User.objects.filter(id=user_id, role=UserRole.TUTOR).first()
    if tutor is not None and not _tutor_has_data(tutor.id):
        tutor.delete()
    return redirect("/admin/users")


@admin_required
def admin_data(request):
    return render(request, "admin/data.html", {"user": request.user, "active_page": "admin_data"})


def _serialize(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    return value


def build_export_data() -> dict:
    def rows(model):
        return [{f.attname: _serialize(getattr(obj, f.attname)) for f in model._meta.fields} for obj in model.objects.all()]

    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "version": "1",
        "users": rows(User),
        "payees": rows(Payee),
        "students": rows(Student),
        "sessions": rows(Session),
        "payments": rows(Payment),
    }


@admin_required
def admin_export(request):
    data = build_export_data()
    filename = f"tutorhub_export_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    response = HttpResponse(json.dumps(data, indent=2), content_type="application/json")
    response["Content-Disposition"] = f"attachment; filename={filename}"
    return response


def _dt(value):
    return datetime.fromisoformat(value) if value else None


@admin_required
@require_http_methods(["POST"])
def admin_import(request):
    file = request.FILES.get("file")
    try:
        data = json.loads(file.read())
        _import_data(data)
    except Exception as exc:
        return redirect(f"/admin/data?error={quote(str(exc))}")
    return redirect("/admin/data?imported=1")


@transaction.atomic
def _import_data(data: dict) -> None:
    Payment.objects.all().delete()
    Session.objects.all().delete()
    Student.objects.all().delete()
    Payee.objects.all().delete()
    User.objects.all().delete()

    for row in data.get("users", []):
        User.objects.create(
            id=row["id"],
            email=row["email"],
            password=row["password"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            role=row["role"],
            is_active=row["is_active"],
            is_staff=row.get("is_staff", False),
            address=row.get("address"),
            payout_type=row.get("payout_type") or None,
            payout_hourly_rate=row.get("payout_hourly_rate"),
            payout_percentage=row.get("payout_percentage"),
        )

    for row in data.get("payees", []):
        Payee.objects.create(
            id=row["id"],
            user_id=row["user_id"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            email=row.get("email"),
            phone_number=row.get("phone_number"),
            bank_reference_pattern=row.get("bank_reference_pattern"),
        )

    for row in data.get("students", []):
        Student.objects.create(
            id=row["id"],
            user_id=row["user_id"],
            payee_id=row.get("payee_id"),
            first_name=row["first_name"],
            last_name=row["last_name"],
            level=row.get("level"),
            hourly_rate=row.get("hourly_rate"),
            zoom_meeting_id=row.get("zoom_meeting_id"),
            google_doc_id=row.get("google_doc_id"),
            onedrive_shared_link=row.get("onedrive_shared_link"),
            is_active=row.get("is_active", True),
        )

    for row in data.get("sessions", []):
        Session.objects.create(
            id=row["id"],
            user_id=row["user_id"],
            student_id=row["student_id"],
            session_date=_dt(row["session_date"]),
            session_start_time=_dt(row["session_start_time"]),
            session_end_time=_dt(row["session_end_time"]),
            is_no_show=row.get("is_no_show", False),
            zoom_meeting_uuid=row.get("zoom_meeting_uuid"),
            zoom_summary_raw=row.get("zoom_summary_raw"),
            work_covered=row.get("work_covered"),
            student_actions=row.get("student_actions"),
            tutor_actions=row.get("tutor_actions"),
            next_lesson_focus=row.get("next_lesson_focus"),
            topic_tags=row.get("topic_tags"),
            calendar_event_id=row.get("calendar_event_id"),
            calendar_recurring_id=row.get("calendar_recurring_id"),
            calendar_html_link=row.get("calendar_html_link"),
            ilp_generated_at=_dt(row.get("ilp_generated_at")),
        )

    for row in data.get("payments", []):
        Payment.objects.create(
            id=row["id"],
            user_id=row["user_id"],
            payee_id=row["payee_id"],
            amount=row["amount"],
            payment_date=_dt(row["payment_date"]),
            payment_reference=row.get("payment_reference"),
        )
