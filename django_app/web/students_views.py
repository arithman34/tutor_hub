import re
import uuid

from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from billing.models import Payee
from students.models import Student
from tutoring_sessions.models import Session

from .auth import login_required


def _doc_id_from_url(url: str) -> str | None:
    match = re.search(r"/document/d/([a-zA-Z0-9_-]+)", url)
    return match.group(1) if match else None


def _owned_student_or_none(student_id, user) -> Student | None:
    return Student.objects.filter(id=student_id, user=user).first()


def _owned_payee_id(raw: str | None, user):
    """The payee id from a form, or None if blank or not one of the user's payees."""
    if not raw:
        return None
    try:
        payee_id = uuid.UUID(raw)
    except ValueError:
        return None
    return payee_id if Payee.objects.filter(id=payee_id, user=user).exists() else None


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

    qs = Student.objects.filter(user=user)
    if q:
        qs = qs.filter(first_name__icontains=q) | qs.filter(last_name__icontains=q)
    students = qs.order_by("-created_at")

    return render(request, "students/index.html", {"user": user, "active_page": "students", "students": students, "q": q})


@login_required
def students_new(request):
    user = request.user
    payees = Payee.objects.filter(user=user).order_by("first_name")
    return render(request, "students/new.html", {"user": user, "active_page": "students", "payees": payees})


def students_create(request):
    user = request.user
    hourly_rate = request.POST.get("hourly_rate") or None

    Student.objects.create(
        user=user,
        first_name=request.POST.get("first_name", "").strip().title(),
        last_name=request.POST.get("last_name", "").strip().title(),
        level=request.POST.get("level") or None,
        hourly_rate=float(hourly_rate) if hourly_rate else None,
        payee_id=_owned_payee_id(request.POST.get("payee_id"), user),
    )
    return redirect("/students")


@login_required
def student_detail(request, student_id):
    user = request.user
    student = _owned_student_or_none(student_id, user)
    if student is None:
        return redirect("/students")

    sessions = Session.objects.filter(student=student, user=user).order_by("-session_date")[:10]
    payees = Payee.objects.filter(user=user).order_by("first_name")

    return render(
        request,
        "students/detail.html",
        {"user": user, "active_page": "students", "student": student, "sessions": sessions, "payees": payees},
    )


@login_required
@require_http_methods(["POST"])
def student_update(request, student_id):
    user = request.user
    student = get_object_or_404(Student, id=student_id, user=user)

    first_name = request.POST.get("first_name", "").strip()
    last_name = request.POST.get("last_name", "").strip()
    hourly_rate = request.POST.get("hourly_rate") or None
    ilp_url = request.POST.get("ilp_url") or ""

    if first_name:
        student.first_name = first_name.title()
    if last_name:
        student.last_name = last_name.title()
    student.level = request.POST.get("level") or None
    student.hourly_rate = float(hourly_rate) if hourly_rate else None
    student.google_doc_id = _doc_id_from_url(ilp_url) if ilp_url else None
    student.payee_id = _owned_payee_id(request.POST.get("payee_id"), user)
    student.save()

    return redirect(f"/students/{student_id}")


@login_required
@require_http_methods(["POST"])
def student_toggle_active(request, student_id):
    student = _owned_student_or_none(student_id, request.user)
    if student is not None:
        student.is_active = not student.is_active
        student.save(update_fields=["is_active", "updated_at"])
    return redirect(f"/students/{student_id}")


@login_required
@require_http_methods(["POST"])
def student_delete(request, student_id):
    Student.objects.filter(id=student_id, user=request.user).delete()
    return redirect("/students")
