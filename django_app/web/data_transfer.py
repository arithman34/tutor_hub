"""JSON export/import of TutorHub data.

Two different jobs live here and must not be confused:

- Per-account ("My data"): what a logged-in user downloads or uploads from
  the web app. It only ever reads or replaces *that account's* rows, never
  includes account credentials, and ignores any `user_id` in the file.

- Full backup / restore: the operator's disaster-recovery path, run from
  management commands (`export_to_s3`, `import_legacy_export`), never from
  a web request. It covers every account, including password hashes, and a
  restore wipes and replaces the whole database.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from django.db import transaction

from accounts.models import User
from billing.models import Payee, Payment
from students.models import Student
from tutoring_sessions.models import Session

EXPORT_VERSION = "2"

_STUDENT_FIELDS = ("first_name", "last_name", "level", "hourly_rate", "zoom_meeting_id", "google_doc_id", "onedrive_shared_link")
_PAYEE_FIELDS = ("first_name", "last_name", "email", "phone_number", "bank_reference_pattern")
_SESSION_TEXT_FIELDS = (
    "zoom_meeting_uuid",
    "zoom_summary_raw",
    "work_covered",
    "student_actions",
    "tutor_actions",
    "next_lesson_focus",
    "topic_tags",
    "calendar_event_id",
    "calendar_recurring_id",
    "calendar_html_link",
)


def _serialize(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    return value


def _dt(value):
    return datetime.fromisoformat(value) if value else None


def _rows(queryset, exclude=()):
    fields = [f for f in queryset.model._meta.fields if f.attname not in exclude]
    return [{f.attname: _serialize(getattr(obj, f.attname)) for f in fields} for obj in queryset]


# ── Per-account ──────────────────────────────────────────────────────────────


def build_user_export(user: User) -> dict:
    """Everything the account owns, without any account or credential data."""
    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "version": EXPORT_VERSION,
        "payees": _rows(Payee.objects.filter(user=user), exclude=("user_id",)),
        "students": _rows(Student.objects.filter(user=user), exclude=("user_id",)),
        "sessions": _rows(Session.objects.filter(user=user), exclude=("user_id",)),
        "payments": _rows(Payment.objects.filter(user=user), exclude=("user_id",)),
    }


def _new_id_map(rows: list, kind: str) -> dict:
    ids = {}
    for row in rows:
        old = str(row.get("id", ""))
        if not old or old in ids:
            raise ValueError(f"Every {kind} needs a unique id")
        ids[old] = uuid.uuid4()
    return ids


def _lookup(ids: dict, old, kind: str, allow_none: bool = False):
    if old is None and allow_none:
        return None
    try:
        return ids[str(old)]
    except KeyError:
        raise ValueError(f"A row refers to a {kind} that is not in the file") from None


@transaction.atomic
def import_user_data(user: User, data: dict) -> dict:
    """Replace the account's payees, students, sessions and payments with the
    file's contents. Other accounts are never touched.

    Rows get fresh ids, so a file can't collide with (or overwrite) another
    account's rows, and every reference in the file must point at a row in
    the same file. Any problem raises ValueError and rolls the whole import
    back, leaving existing data in place.
    """
    payees, students = data.get("payees", []), data.get("students", [])
    sessions, payments = data.get("sessions", []), data.get("payments", [])

    payee_ids = _new_id_map(payees, "payee")
    student_ids = _new_id_map(students, "student")
    _new_id_map(sessions, "session")
    _new_id_map(payments, "payment")

    Payment.objects.filter(user=user).delete()
    Session.objects.filter(user=user).delete()
    Student.objects.filter(user=user).delete()
    Payee.objects.filter(user=user).delete()

    for row in payees:
        Payee.objects.create(id=payee_ids[str(row["id"])], user=user, **{f: row.get(f) for f in _PAYEE_FIELDS})

    for row in students:
        Student.objects.create(
            id=student_ids[str(row["id"])],
            user=user,
            payee_id=_lookup(payee_ids, row.get("payee_id"), "payee", allow_none=True),
            is_active=row.get("is_active", True),
            **{f: row.get(f) for f in _STUDENT_FIELDS},
        )

    for row in sessions:
        Session.objects.create(
            user=user,
            student_id=_lookup(student_ids, row.get("student_id"), "student"),
            session_date=_dt(row["session_date"]),
            session_start_time=_dt(row["session_start_time"]),
            session_end_time=_dt(row["session_end_time"]),
            is_no_show=row.get("is_no_show", False),
            ilp_generated_at=_dt(row.get("ilp_generated_at")),
            **{f: row.get(f) for f in _SESSION_TEXT_FIELDS},
        )

    for row in payments:
        Payment.objects.create(
            user=user,
            payee_id=_lookup(payee_ids, row.get("payee_id"), "payee"),
            amount=row["amount"],
            payment_date=_dt(row["payment_date"]),
            payment_reference=row.get("payment_reference"),
        )

    return {"payees": len(payees), "students": len(students), "sessions": len(sessions), "payments": len(payments)}


# ── Full backup / restore (operator only) ────────────────────────────────────


def build_full_backup() -> dict:
    """Every account and every row, password hashes included. Never serve this
    from a web view."""
    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "version": EXPORT_VERSION,
        "users": _rows(User.objects.all()),
        "payees": _rows(Payee.objects.all()),
        "students": _rows(Student.objects.all()),
        "sessions": _rows(Session.objects.all()),
        "payments": _rows(Payment.objects.all()),
    }


@transaction.atomic
def restore_full_backup(data: dict) -> None:
    """Wipe and replace every account and row from a full backup. Fields that
    no longer exist (e.g. the old `role` and `payout_*` columns) are ignored."""
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
            is_active=row["is_active"],
            is_staff=row.get("is_staff", False),
            is_superuser=row.get("is_superuser", False),
            address=row.get("address"),
        )

    for row in data.get("payees", []):
        Payee.objects.create(id=row["id"], user_id=row["user_id"], **{f: row.get(f) for f in _PAYEE_FIELDS})

    for row in data.get("students", []):
        Student.objects.create(
            id=row["id"],
            user_id=row["user_id"],
            payee_id=row.get("payee_id"),
            is_active=row.get("is_active", True),
            **{f: row.get(f) for f in _STUDENT_FIELDS},
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
            ilp_generated_at=_dt(row.get("ilp_generated_at")),
            **{f: row.get(f) for f in _SESSION_TEXT_FIELDS},
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
