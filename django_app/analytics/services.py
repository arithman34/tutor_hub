"""Admin dashboard trend analytics.

Aggregation happens in Python rather than via backend-specific SQL (the
FastAPI version used Postgres's `date_trunc`): TutorHub's data volumes are
small (hundreds to low thousands of rows per tutor), so the portability and
testability of bucketing in Python — identical behavior on SQLite in tests
and Postgres in production — is worth more here than shaving a DB round
trip.
"""

import uuid
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone

from django.db.models import Q

from billing.models import Payee, Payment
from students.models import Student
from tutoring_sessions.models import Session

from accounts.models import User, UserRole

GRANULARITIES = ("day", "week", "month")

# A student is treated as having gone quiet once this long has passed since
# their most recent session.
CHURN_QUIET = timedelta(weeks=4)

MAX_BUCKETS = 400

CHARTS = (
    {
        "key": "students",
        "title": "Students",
        "series": (
            {"key": "students_new", "label": "New students", "unit": "count", "type": "bar", "axis": "y"},
            {"key": "students_taught", "label": "Students taught", "unit": "count", "type": "line", "axis": "y"},
            {"key": "students_churned", "label": "Gone quiet", "unit": "count", "type": "line", "axis": "y"},
            {"key": "students_roster", "label": "On the books", "unit": "count", "type": "line", "axis": "y1"},
        ),
    },
    {
        "key": "sessions",
        "title": "Sessions",
        "series": (
            {"key": "sessions_count", "label": "Sessions", "unit": "count", "type": "bar", "axis": "y"},
            {"key": "sessions_no_shows", "label": "No-shows", "unit": "count", "type": "line", "axis": "y"},
            {"key": "sessions_hours", "label": "Hours taught", "unit": "hours", "type": "line", "axis": "y1"},
        ),
    },
    {
        "key": "payments",
        "title": "Payments",
        "series": (
            {"key": "payments_amount", "label": "Received", "unit": "currency", "type": "bar", "axis": "y"},
            {"key": "payments_count", "label": "Payments recorded", "unit": "count", "type": "line", "axis": "y1"},
        ),
    },
)

_CUMULATIVE = {"students_roster"}


def pct_change(current: float, previous: float) -> float | None:
    if not previous:
        return None
    return round((current - previous) / previous * 100, 1)


@dataclass(frozen=True)
class Filters:
    start: datetime
    end: datetime
    granularity: str = "month"
    tutor_id: uuid.UUID | None = None
    student_id: uuid.UUID | None = None
    payee_id: uuid.UUID | None = None


# ── Bucket maths ─────────────────────────────────────────────────────────────


def floor_bucket(moment: datetime, granularity: str) -> datetime:
    """Snap a moment back to the start of its bucket, in UTC."""
    moment = moment.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    if granularity == "week":
        return moment - timedelta(days=moment.weekday())
    if granularity == "month":
        return moment.replace(day=1)
    return moment


def step_bucket(moment: datetime, granularity: str, forward: bool = True) -> datetime:
    if granularity == "day":
        return moment + timedelta(days=1 if forward else -1)
    if granularity == "week":
        return moment + timedelta(weeks=1 if forward else -1)
    if forward:
        return moment.replace(year=moment.year + 1, month=1) if moment.month == 12 else moment.replace(month=moment.month + 1)
    return moment.replace(year=moment.year - 1, month=12) if moment.month == 1 else moment.replace(month=moment.month - 1)


def bucket_range(start: datetime, end: datetime, granularity: str) -> list[datetime]:
    """Every bucket start from `start`'s bucket through `end`'s bucket."""
    buckets, current, last = [], floor_bucket(start, granularity), floor_bucket(end, granularity)
    while current <= last:
        buckets.append(current)
        current = step_bucket(current, granularity)
    return buckets


def fit_granularity(start: datetime, end: datetime, granularity: str) -> str:
    """Coarsen the granularity until the range produces a sane number of buckets."""
    order = list(GRANULARITIES)
    index = order.index(granularity)
    while index < len(order) - 1 and len(bucket_range(start, end, order[index])) > MAX_BUCKETS:
        index += 1
    return order[index]


def _months_back(moment: datetime, months: int) -> datetime:
    month, year = moment.month - months, moment.year
    while month <= 0:
        month += 12
        year -= 1
    return moment.replace(year=year, month=month, day=1, hour=0, minute=0, second=0, microsecond=0)


def resolve_range(
    preset: str | None,
    start: date | None,
    end: date | None,
    earliest: datetime | None,
    now: datetime,
) -> tuple[str, datetime, datetime]:
    """Turn the requested preset (or explicit dates) into a concrete UTC window."""
    end_of_today = now.replace(hour=23, minute=59, second=59, microsecond=0)

    if start or end:
        resolved_start = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc) if start else _months_back(now, 11)
        resolved_end = datetime.combine(end, datetime.max.time().replace(microsecond=0), tzinfo=timezone.utc) if end else end_of_today
        if resolved_start > resolved_end:
            resolved_start, resolved_end = resolved_end, resolved_start
        return "custom", resolved_start, resolved_end

    if preset == "3m":
        return preset, _months_back(now, 2), end_of_today
    if preset == "6m":
        return preset, _months_back(now, 5), end_of_today
    if preset == "ytd":
        return preset, now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0), end_of_today
    if preset == "all":
        return preset, (earliest or _months_back(now, 11)).astimezone(timezone.utc), end_of_today
    return "12m", _months_back(now, 11), end_of_today


def get_earliest_activity() -> datetime | None:
    """Oldest timestamp across the three tracked entities, for the "all time" preset."""
    moments = [
        Student.objects.order_by("created_at").values_list("created_at", flat=True).first(),
        Session.objects.order_by("session_date").values_list("session_date", flat=True).first(),
        Payment.objects.order_by("payment_date").values_list("payment_date", flat=True).first(),
    ]
    found = [m for m in moments if m is not None]
    return min(found) if found else None


# ── Filter predicates ────────────────────────────────────────────────────────


def _student_filter_kwargs(filters: Filters) -> dict:
    kwargs = {}
    if filters.tutor_id:
        kwargs["user_id"] = filters.tutor_id
    if filters.student_id:
        kwargs["id"] = filters.student_id
    if filters.payee_id:
        kwargs["payee_id"] = filters.payee_id
    return kwargs


def _session_filter_kwargs(filters: Filters) -> dict:
    kwargs = {}
    if filters.tutor_id:
        kwargs["user_id"] = filters.tutor_id
    if filters.student_id:
        kwargs["student_id"] = filters.student_id
    if filters.payee_id:
        kwargs["student__payee_id"] = filters.payee_id
    return kwargs


def _payment_filters(filters: Filters) -> list:
    """Payments hang off a payee, so tutor/student filters resolve through students.

    Each condition narrows to payee ids via a subquery rather than joining
    through the reverse `students` relation, so a payee with several matching
    students can't multiply a single payment row. Independent conditions (as
    in the original) rather than mutually exclusive, so combining filters
    still ANDs them.
    """
    conditions = []
    if filters.payee_id:
        conditions.append(Q(payee_id=filters.payee_id))
    if filters.student_id:
        conditions.append(Q(payee_id__in=Student.objects.filter(id=filters.student_id, payee_id__isnull=False).values("payee_id")))
    if filters.tutor_id:
        conditions.append(Q(payee_id__in=Student.objects.filter(user_id=filters.tutor_id, payee_id__isnull=False).values("payee_id")))
    return conditions


# ── Bucketing helpers ────────────────────────────────────────────────────────


def _bucket_index(buckets: list[datetime]) -> dict[datetime, int]:
    return {b: i for i, b in enumerate(buckets)}


def _empty_series(count: int, buckets: list[datetime]) -> list[list[float]]:
    return [[0.0] * len(buckets) for _ in range(count)]


# ── Series builders ──────────────────────────────────────────────────────────


def _student_series(filters: Filters, buckets: list[datetime], window_end: datetime, now: datetime) -> dict[str, list[float]]:
    granularity = filters.granularity
    index = _bucket_index(buckets)
    student_kwargs = _student_filter_kwargs(filters)
    session_kwargs = _session_filter_kwargs(filters)

    new_students, taught, churned = _empty_series(3, buckets)

    created_at_values = Student.objects.filter(created_at__gte=buckets[0], created_at__lt=window_end, **student_kwargs).values_list(
        "created_at", flat=True
    )
    for created_at in created_at_values:
        i = index.get(floor_bucket(created_at, granularity))
        if i is not None:
            new_students[i] += 1

    baseline = Student.objects.filter(created_at__lt=buckets[0], **student_kwargs).count()
    roster, running = [], float(baseline)
    for added in new_students:
        running += added
        roster.append(running)

    taught_rows = (
        Session.objects.filter(session_date__gte=buckets[0], session_date__lt=window_end, is_no_show=False, **session_kwargs)
        .values_list("session_date", "student_id")
    )
    taught_sets: dict[int, set] = {}
    for session_date, student_id in taught_rows:
        i = index.get(floor_bucket(session_date, granularity))
        if i is not None:
            taught_sets.setdefault(i, set()).add(student_id)
    for i, student_ids in taught_sets.items():
        taught[i] = len(student_ids)

    last_seen: dict = {}
    for student_id, session_date in Session.objects.filter(is_no_show=False, **session_kwargs).values_list("student_id", "session_date"):
        if student_id not in last_seen or session_date > last_seen[student_id]:
            last_seen[student_id] = session_date

    for last_date in last_seen.values():
        quiet_moment = last_date + CHURN_QUIET
        if buckets[0] <= quiet_moment < window_end and quiet_moment <= now:
            i = index.get(floor_bucket(quiet_moment, granularity))
            if i is not None:
                churned[i] += 1

    return {
        "students_new": new_students,
        "students_roster": roster,
        "students_taught": taught,
        "students_churned": churned,
    }


def _session_series(filters: Filters, buckets: list[datetime], window_end: datetime) -> dict[str, list[float]]:
    index = _bucket_index(buckets)
    granularity = filters.granularity
    counts, hours, no_shows = _empty_series(3, buckets)

    rows = Session.objects.filter(session_date__gte=buckets[0], session_date__lt=window_end, **_session_filter_kwargs(filters)).values_list(
        "session_date", "session_start_time", "session_end_time", "is_no_show"
    )
    for session_date, start, end, is_no_show in rows:
        i = index.get(floor_bucket(session_date, granularity))
        if i is None:
            continue
        counts[i] += 1
        hours[i] += (end - start).total_seconds() / 3600.0
        if is_no_show:
            no_shows[i] += 1

    return {
        "sessions_count": counts,
        "sessions_hours": [round(value, 2) for value in hours],
        "sessions_no_shows": no_shows,
    }


def _payment_series(filters: Filters, buckets: list[datetime], window_end: datetime) -> dict[str, list[float]]:
    index = _bucket_index(buckets)
    granularity = filters.granularity
    amounts, counts = _empty_series(2, buckets)

    rows = Payment.objects.filter(
        Q(payment_date__gte=buckets[0]), Q(payment_date__lt=window_end), *_payment_filters(filters)
    ).values_list("payment_date", "amount")
    for payment_date, amount in rows:
        i = index.get(floor_bucket(payment_date, granularity))
        if i is not None:
            amounts[i] += float(amount)
            counts[i] += 1

    return {
        "payments_amount": [round(value, 2) for value in amounts],
        "payments_count": counts,
    }


# ── Entry point ──────────────────────────────────────────────────────────────


def get_trends(filters: Filters, now: datetime | None = None) -> dict:
    """Build every trend series for `filters`, plus totals and prior-period deltas."""
    now = now or datetime.now(timezone.utc)
    filters = replace(filters, granularity=fit_granularity(filters.start, filters.end, filters.granularity))
    granularity = filters.granularity

    visible = bucket_range(filters.start, filters.end, granularity)
    prior, cursor = [], visible[0]
    for _ in range(len(visible)):
        cursor = step_bucket(cursor, granularity, forward=False)
        prior.insert(0, cursor)
    buckets = prior + visible
    split = len(prior)
    window_end = step_bucket(visible[-1], granularity)

    raw: dict[str, list[float]] = {}
    raw.update(_student_series(filters, buckets, window_end, now))
    raw.update(_session_series(filters, buckets, window_end))
    raw.update(_payment_series(filters, buckets, window_end))

    series = {}
    for chart in CHARTS:
        for meta in chart["series"]:
            key = meta["key"]
            values = raw[key]
            current, previous = values[split:], values[:split]
            if key in _CUMULATIVE:
                total = current[-1] if current else 0.0
                baseline = previous[-1] if previous else 0.0
            else:
                total = round(sum(current), 2)
                baseline = sum(previous)
            series[key] = {
                **meta,
                "data": current,
                "total": total,
                "change": pct_change(total, baseline),
            }

    return {
        "granularity": granularity,
        "start": filters.start.isoformat(),
        "end": filters.end.isoformat(),
        "labels": [bucket.isoformat() for bucket in visible],
        "charts": [{"key": c["key"], "title": c["title"], "series": [series[m["key"]] for m in c["series"]]} for c in CHARTS],
    }


def get_filter_options() -> dict:
    """Dropdown contents for the filter bar."""
    tutors = User.objects.filter(role__in=(UserRole.TUTOR, UserRole.ADMIN_TUTOR)).order_by("first_name", "last_name")
    students = Student.objects.order_by("first_name", "last_name")
    payees = Payee.objects.order_by("first_name", "last_name")

    def _options(rows):
        return [{"id": str(row.id), "name": f"{row.first_name} {row.last_name}"} for row in rows]

    return {"tutors": _options(tutors), "students": _options(students), "payees": _options(payees)}
