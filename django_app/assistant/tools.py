"""Read-only tools that TutorHub AI can call to answer questions about your data.

Every tool takes the requesting `user` first and only ever reads rows that
user owns. An id that belongs to another account is reported exactly like an
id that does not exist, so nothing leaks between accounts.

Tool output is sent to the LLM provider, so it is kept to what is needed to
answer questions: no payee contact details, bank reference patterns, payment
references, raw Zoom transcripts or calendar/Zoom identifiers.

Dates in arguments are whole days in Europe/London, with both ends included.
Timestamps in results are ISO 8601 in Europe/London, and money is in GBP.
"""

import inspect
import uuid
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.db.models import Count, Max, Q

from billing.models import Payee, Payment
from billing.services import payee_balances
from students.models import Student
from tutoring_sessions.models import Session

LONDON = ZoneInfo("Europe/London")

DEFAULT_SESSIONS_LIMIT = 20
MAX_SESSIONS_LIMIT = 50
MAX_PAYMENTS = 100


class ToolError(Exception):
    """A bad argument or unknown id. The message is safe to pass back to the model."""


# --- argument parsing -------------------------------------------------------


def _parse_uuid(value, field: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        raise ToolError(f"{field} must be an id returned by another tool, got {value!r}.") from None


def _parse_date(value, field: str) -> date | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ToolError(f"{field} must be a date string in YYYY-MM-DD format.")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ToolError(f"{field} must be a date in YYYY-MM-DD format, got {value!r}.") from None


def _date_range(start, end) -> tuple[date | None, date | None, datetime | None, datetime | None]:
    """Parse inclusive London dates into a half-open [lower, upper) datetime range."""
    start_date = _parse_date(start, "start")
    end_date = _parse_date(end, "end")
    if start_date and end_date and start_date > end_date:
        raise ToolError("start must be on or before end.")
    lower = datetime.combine(start_date, time.min, tzinfo=LONDON) if start_date else None
    upper = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=LONDON) if end_date else None
    return start_date, end_date, lower, upper


def _parse_limit(value) -> int:
    if value is None:
        return DEFAULT_SESSIONS_LIMIT
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= MAX_SESSIONS_LIMIT:
        raise ToolError(f"limit must be a whole number from 1 to {MAX_SESSIONS_LIMIT}.")
    return value


# --- output helpers ---------------------------------------------------------


def _local(dt: datetime) -> str:
    return dt.astimezone(LONDON).isoformat(timespec="minutes")


def _hours(start: datetime, end: datetime) -> float:
    return (end - start).total_seconds() / 3600


def _name(person) -> str:
    return f"{person.first_name} {person.last_name}"


def _period(start_date: date | None, end_date: date | None) -> dict:
    return {
        "start": start_date.isoformat() if start_date else None,
        "end": end_date.isoformat() if end_date else None,
    }


def _student_for(user, student_id) -> Student:
    student = Student.objects.filter(user=user, id=_parse_uuid(student_id, "student_id")).first()
    if student is None:
        raise ToolError(f"No student found with id {student_id}.")
    return student


def _payee_for(user, payee_id) -> Payee:
    payee = Payee.objects.filter(user=user, id=_parse_uuid(payee_id, "payee_id")).first()
    if payee is None:
        raise ToolError(f"No payee found with id {payee_id}.")
    return payee


def _sessions_in_range(user, student_id, start, end):
    student = _student_for(user, student_id) if student_id is not None else None
    start_date, end_date, lower, upper = _date_range(start, end)

    sessions = Session.objects.filter(user=user)
    if student is not None:
        sessions = sessions.filter(student=student)
    if lower is not None:
        sessions = sessions.filter(session_date__gte=lower)
    if upper is not None:
        sessions = sessions.filter(session_date__lt=upper)

    student_info = {"id": str(student.id), "name": _name(student)} if student else None
    return sessions, student_info, _period(start_date, end_date)


# --- tools ------------------------------------------------------------------


def find_students(user, name: str) -> dict:
    """Students whose first or last name contains every word in `name`."""
    if not isinstance(name, str) or not name.strip():
        raise ToolError("name must be a non-empty string.")

    students = Student.objects.filter(user=user).select_related("payee").order_by("first_name", "last_name")
    for term in name.split():
        students = students.filter(Q(first_name__icontains=term) | Q(last_name__icontains=term))

    return {
        "students": [
            {
                "id": str(student.id),
                "name": _name(student),
                "level": student.level,
                "is_active": student.is_active,
                "payee": {"id": str(student.payee.id), "name": _name(student.payee)} if student.payee else None,
            }
            for student in students
        ]
    }


def list_students(user, include_inactive: bool = False, start: str | None = None, end: str | None = None) -> dict:
    """Every student, with how many sessions each had in a date range and when they were last taught."""
    if not isinstance(include_inactive, bool):
        raise ToolError("include_inactive must be true or false.")
    start_date, end_date, lower, upper = _date_range(start, end)

    in_period = Q()
    if lower is not None:
        in_period &= Q(sessions__session_date__gte=lower)
    if upper is not None:
        in_period &= Q(sessions__session_date__lt=upper)

    students = (
        Student.objects.filter(user=user)
        .select_related("payee")
        .annotate(
            sessions_in_period=Count("sessions", filter=in_period),
            last_session=Max("sessions__session_start_time"),
        )
        .order_by("first_name", "last_name")
    )
    if not include_inactive:
        students = students.filter(is_active=True)

    return {
        "period": _period(start_date, end_date),
        "students": [
            {
                "id": str(student.id),
                "name": _name(student),
                "level": student.level,
                "is_active": student.is_active,
                "payee": {"id": str(student.payee.id), "name": _name(student.payee)} if student.payee else None,
                "sessions_in_period": student.sessions_in_period,
                "last_session": _local(student.last_session) if student.last_session else None,
            }
            for student in students
        ],
    }


def count_sessions(user, student_id: str | None = None, start: str | None = None, end: str | None = None) -> dict:
    """Session counts and hours, for one student or all students."""
    sessions, student_info, period = _sessions_in_range(user, student_id, start, end)

    total = no_shows = 0
    hours_booked = hours_attended = 0.0
    for session_start, session_end, is_no_show in sessions.values_list("session_start_time", "session_end_time", "is_no_show"):
        hours = _hours(session_start, session_end)
        total += 1
        hours_booked += hours
        if is_no_show:
            no_shows += 1
        else:
            hours_attended += hours

    return {
        "student": student_info,
        "period": period,
        "sessions": total,
        "no_shows": no_shows,
        "hours_booked": round(hours_booked, 2),
        "hours_attended": round(hours_attended, 2),
    }


def get_sessions(
    user,
    student_id: str | None = None,
    start: str | None = None,
    end: str | None = None,
    limit: int | None = None,
) -> dict:
    """Session notes, newest first, for one student or all students."""
    limit = _parse_limit(limit)
    sessions, student_info, period = _sessions_in_range(user, student_id, start, end)
    rows = list(sessions.select_related("student").order_by("-session_date")[:limit])

    return {
        "student": student_info,
        "period": period,
        "total_matching": sessions.count() if len(rows) == limit else len(rows),
        "sessions": [
            {
                "student": {"id": str(session.student.id), "name": _name(session.student)},
                "start": _local(session.session_start_time),
                "duration_minutes": session.minutes,
                "is_no_show": session.is_no_show,
                "work_covered": session.work_covered,
                "student_actions": session.student_actions,
                "tutor_actions": session.tutor_actions,
                "next_lesson_focus": session.next_lesson_focus,
                "topic_tags": session.topic_tags,
            }
            for session in rows
        ],
    }


def list_payee_balances(user, only_owing: bool = False) -> dict:
    """Every payee's balance. Negative means the payee owes money."""
    if not isinstance(only_owing, bool):
        raise ToolError("only_owing must be true or false.")

    payees = list(Payee.objects.filter(user=user).prefetch_related("students"))
    balances = payee_balances(payees)

    rows = [
        {
            "id": str(payee.id),
            "name": _name(payee),
            "students": sorted(_name(student) for student in payee.students.all()),
            "balance": balances[payee.id],
            "owes": balances[payee.id] < 0,
        }
        for payee in payees
    ]
    if only_owing:
        rows = [row for row in rows if row["owes"]]
    rows.sort(key=lambda row: (row["balance"], row["name"]))

    return {"currency": "GBP", "payees": rows}


def get_payments(user, payee_id: str | None = None, start: str | None = None, end: str | None = None) -> dict:
    """Payments received, newest first, from one payee or all payees."""
    payee = _payee_for(user, payee_id) if payee_id is not None else None
    start_date, end_date, lower, upper = _date_range(start, end)

    payments = Payment.objects.filter(user=user)
    if payee is not None:
        payments = payments.filter(payee=payee)
    if lower is not None:
        payments = payments.filter(payment_date__gte=lower)
    if upper is not None:
        payments = payments.filter(payment_date__lt=upper)

    rows = list(payments.select_related("payee").order_by("-payment_date"))
    total = sum((payment.amount for payment in rows), start=0)

    return {
        "payee": {"id": str(payee.id), "name": _name(payee)} if payee else None,
        "period": _period(start_date, end_date),
        "currency": "GBP",
        "count": len(rows),
        "total": float(round(total, 2)),
        "payments": [
            {
                "payee": {"id": str(payment.payee.id), "name": _name(payment.payee)},
                "date": _local(payment.payment_date),
                "amount": float(payment.amount),
            }
            for payment in rows[:MAX_PAYMENTS]
        ],
    }


# --- registry and specs -----------------------------------------------------

TOOLS = {
    "find_students": find_students,
    "list_students": list_students,
    "count_sessions": count_sessions,
    "get_sessions": get_sessions,
    "list_payee_balances": list_payee_balances,
    "get_payments": get_payments,
}

_STUDENT_ID = {"type": "string", "description": "A student id from find_students or list_students. Leave out to cover all students."}
_START = {"type": "string", "format": "date", "description": "First day to include, YYYY-MM-DD (UK time). Leave out for no lower bound."}
_END = {"type": "string", "format": "date", "description": "Last day to include, YYYY-MM-DD (UK time). Leave out for no upper bound."}

# Provider-neutral JSON-schema definitions; the LLM client adapts them to its API's format.
TOOL_SPECS = [
    {
        "name": "find_students",
        "description": (
            "Look up students by name. Returns every match, including inactive students, with their payee. "
            "If more than one student matches, ask the user which one they mean."
        ),
        "parameters": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "Full or partial first and/or last name."}},
            "required": ["name"],
            "additionalProperties": False,
        },
    },
    {
        "name": "list_students",
        "description": (
            "List all of the tutor's students (active only, unless include_inactive is true), with level, payee, "
            "the number of sessions each had in the date range, and the start of their most recent session ever. "
            "Use for questions about all students, such as who has not been taught yet this month, "
            "who was taught most, or how many students the tutor has."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "include_inactive": {"type": "boolean", "description": "Also include students marked inactive (default false)."},
                "start": _START,
                "end": _END,
            },
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "name": "count_sessions",
        "description": (
            "Count sessions in a date range, with no-shows, hours booked (including no-shows) and hours attended. "
            "Covers one student, or all students if student_id is left out."
        ),
        "parameters": {
            "type": "object",
            "properties": {"student_id": _STUDENT_ID, "start": _START, "end": _END},
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_sessions",
        "description": (
            "Session notes (work covered, actions, next lesson focus, topics), newest first. "
            "Covers one student, or all students if student_id is left out. "
            "total_matching shows how many sessions matched in all, which can exceed the number returned."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "student_id": _STUDENT_ID,
                "start": _START,
                "end": _END,
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": MAX_SESSIONS_LIMIT,
                    "description": f"Most sessions to return (default {DEFAULT_SESSIONS_LIMIT}).",
                },
            },
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "name": "list_payee_balances",
        "description": (
            "Each payee's balance in GBP with the students they pay for: payments received minus the cost of sessions. "
            "A negative balance means the payee owes that amount; positive means they are in credit."
        ),
        "parameters": {
            "type": "object",
            "properties": {"only_owing": {"type": "boolean", "description": "Only return payees who owe money."}},
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_payments",
        "description": (
            "Payments received in GBP in a date range, newest first, with the total. "
            f"Covers one payee, or all payees if payee_id is left out. At most {MAX_PAYMENTS} payments are listed; "
            "count and total always cover every match."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "payee_id": {"type": "string", "description": "A payee id from find_students or list_payee_balances. Leave out for all payees."},
                "start": _START,
                "end": _END,
            },
            "required": [],
            "additionalProperties": False,
        },
    },
]


def run_tool(user, name: str, arguments: dict) -> dict:
    """Run a tool by name for `user`. Bad calls come back as {"error": ...} for the model to correct."""
    tool = TOOLS.get(name)
    if tool is None:
        return {"error": f"Unknown tool {name!r}."}
    if not isinstance(arguments, dict):
        return {"error": "Arguments must be a JSON object."}

    signature = inspect.signature(tool)
    unexpected = sorted(set(arguments) - (set(signature.parameters) - {"user"}))
    if unexpected:
        return {"error": f"Unexpected arguments for {name}: {', '.join(unexpected)}."}
    try:
        signature.bind(user, **arguments)
    except TypeError:
        return {"error": f"Missing required arguments for {name}."}

    try:
        return tool(user, **arguments)
    except ToolError as exc:
        return {"error": str(exc)}
