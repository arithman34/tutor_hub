import re
import uuid

from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from accounts.models import User, UserRole
from billing.models import Payee
from students.models import Student
from tutoring_sessions.models import Session

from .auth import login_required


def _doc_id_from_url(url: str) -> str | None:
    match = re.search(r"/document/d/([a-zA-Z0-9_-]+)", url)
    return match.group(1) if match else None


def _visible_student_or_none(student_id, user) -> Student | None:
    try:
        student = Student.objects.select_related("user").get(id=student_id)
    except (Student.DoesNotExist, ValueError, TypeError):
        return None
    if not user.is_admin and student.user_id != user.id:
        return None
    return student


@login_required
def students_index(request):
    """GET lists students, POST creates one — matches the single `/students`
    path the original FastAPI router and the `new.html` form both use."""
    if request.method == "POST":
        return students_create(request)
    return students_list(request)


def students_list(request):
    user = request.user
    q = request.GET.get("q", "")

    qs = Student.objects.select_related("user") if user.is_admin else Student.objects.filter(user=user)
    if q:
        qs = qs.filter(first_name__icontains=q) | qs.filter(last_name__icontains=q)
    students = qs.order_by("-created_at")

    return render(request, "students/index.html", {"user": user, "active_page": "students", "students": students, "q": q})


@login_required
def students_new(request):
    user = request.user
    if not user.is_admin:
        return redirect("/students")

    tutors = User.objects.filter(role__in=(UserRole.TUTOR, UserRole.ADMIN_TUTOR), is_active=True).order_by("first_name")
    payees = Payee.objects.order_by("first_name")
    return render(request, "students/new.html", {"user": user, "active_page": "students", "tutors": tutors, "payees": payees})


def students_create(request):
    user = request.user
    if not user.is_admin:
        return redirect("/students")

    payee_id = request.POST.get("payee_id") or None
    hourly_rate = request.POST.get("hourly_rate") or None

    Student.objects.create(
        user_id=uuid.UUID(request.POST["tutor_id"]),
        first_name=request.POST.get("first_name", "").strip().title(),
        last_name=request.POST.get("last_name", "").strip().title(),
        level=request.POST.get("level") or None,
        hourly_rate=float(hourly_rate) if hourly_rate else None,
        payee_id=uuid.UUID(payee_id) if payee_id else None,
    )
    return redirect("/students")


@login_required
def student_detail(request, student_id):
    user = request.user
    student = _visible_student_or_none(student_id, user)
    if student is None:
        return redirect("/students")

    sessions = Session.objects.filter(student_id=student_id).order_by("-session_date")[:10]
    payees = Payee.objects.order_by("first_name") if user.is_admin else []

    return render(
        request,
        "students/detail.html",
        {"user": user, "active_page": "students", "student": student, "sessions": sessions, "payees": payees},
    )


@login_required
@require_http_methods(["POST"])
def student_update(request, student_id):
    user = request.user
    # Mirrors the DRF StudentViewSet: only admins may update a student.
    if not user.is_admin:
        return redirect(f"/students/{student_id}")

    student = get_object_or_404(Student, id=student_id)

    first_name = request.POST.get("first_name", "").strip()
    last_name = request.POST.get("last_name", "").strip()
    hourly_rate = request.POST.get("hourly_rate") or None
    ilp_url = request.POST.get("ilp_url") or ""
    payee_id = request.POST.get("payee_id") or None

    if first_name:
        student.first_name = first_name.title()
    if last_name:
        student.last_name = last_name.title()
    student.level = request.POST.get("level") or None
    student.hourly_rate = float(hourly_rate) if hourly_rate else None
    student.google_doc_id = _doc_id_from_url(ilp_url) if ilp_url else None
    student.payee_id = uuid.UUID(payee_id) if payee_id else None
    student.save()

    return redirect(f"/students/{student_id}")


@login_required
@require_http_methods(["POST"])
def student_toggle_active(request, student_id):
    # Mirrors the DRF StudentViewSet: only admins may toggle. The detail page
    # shows this button to the owning tutor too (matching the original FastAPI
    # app), but for a non-admin it's a no-op redirect rather than an error.
    if request.user.is_admin:
        student = Student.objects.filter(id=student_id).first()
        if student is not None:
            student.is_active = not student.is_active
            student.save(update_fields=["is_active", "updated_at"])
    return redirect(f"/students/{student_id}")


@login_required
@require_http_methods(["POST"])
def student_delete(request, student_id):
    if request.user.is_admin:
        Student.objects.filter(id=student_id).delete()
    return redirect("/students")
