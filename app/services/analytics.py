import uuid
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import Interval, func, literal, select
from sqlalchemy import text as _text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.models.payee import Payee
from app.models.payment import Payment
from app.models.session import Session
from app.models.student import Student
from app.models.user import User, UserRole
from app.utils import pct_change

GRANULARITIES = ("day", "week", "month")

# A student is treated as having gone quiet once this long has passed since
# their most recent session. Matches the "no session in 4 weeks" rule the
# dashboard already uses for at-risk students.
CHURN_QUIET = timedelta(weeks=4)

# Above this many buckets the chart is unreadable and the payload gets silly, so
# the granularity is coarsened a step at a time until the range fits. The
# granularity actually used is reported back to the client.
MAX_BUCKETS = 400

_SQL_UNIT = {"day": "'day'", "week": "'week'", "month": "'month'"}
_KEY = "%Y-%m-%d"

_hours = func.extract("epoch", Session.session_end_time - Session.session_start_time) / 3600.0

# Chart layout is declared here rather than in the template so the page can be
# rendered from data alone. `axis` picks the left ("y") or right ("y1") scale.
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

# Cumulative series describe a level rather than a flow, so their headline number
# is the closing value, not the sum of the buckets.
_CUMULATIVE = {"students_roster"}


@dataclass(frozen=True)
class Filters:
    """A resolved, validated view of the query string."""

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
        # Postgres date_trunc('week') starts weeks on Monday; match it.
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


def _bucket_expr(column: ColumnElement, granularity: str) -> ColumnElement:
    return func.date_trunc(_text(_SQL_UNIT[granularity]), func.timezone(_text("'UTC'"), column))


# ── Range resolution ─────────────────────────────────────────────────────────


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
    """Turn the requested preset (or explicit dates) into a concrete UTC window.

    Explicit dates win over the preset, and an inverted pair is swapped rather
    than rejected. Returns the preset that was actually applied so the UI can
    keep its buttons in sync.
    """
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


async def get_earliest_activity(db: AsyncSession) -> datetime | None:
    """Oldest timestamp across the three tracked entities, for the "all time" preset."""
    moments = [
        await db.scalar(select(func.min(Student.created_at))),
        await db.scalar(select(func.min(Session.session_date))),
        await db.scalar(select(func.min(Payment.payment_date))),
    ]
    found = [m for m in moments if m is not None]
    return min(found) if found else None


# ── Filter predicates ────────────────────────────────────────────────────────


def _student_predicates(filters: Filters) -> list:
    predicates = []
    if filters.tutor_id:
        predicates.append(Student.user_id == filters.tutor_id)
    if filters.student_id:
        predicates.append(Student.id == filters.student_id)
    if filters.payee_id:
        predicates.append(Student.payee_id == filters.payee_id)
    return predicates


def _session_predicates(filters: Filters) -> list:
    predicates = []
    if filters.tutor_id:
        predicates.append(Session.user_id == filters.tutor_id)
    if filters.student_id:
        predicates.append(Session.student_id == filters.student_id)
    if filters.payee_id:
        predicates.append(Session.student_id.in_(select(Student.id).where(Student.payee_id == filters.payee_id)))
    return predicates


def _payment_predicates(filters: Filters) -> list:
    """Payments hang off a payee, so tutor/student filters resolve through students."""
    predicates = []
    if filters.payee_id:
        predicates.append(Payment.payee_id == filters.payee_id)
    if filters.student_id:
        predicates.append(Payment.payee_id.in_(select(Student.payee_id).where(Student.id == filters.student_id, Student.payee_id.isnot(None))))
    if filters.tutor_id:
        predicates.append(Payment.payee_id.in_(select(Student.payee_id).where(Student.user_id == filters.tutor_id, Student.payee_id.isnot(None))))
    return predicates


# ── Series builders ──────────────────────────────────────────────────────────


def _densify(rows, buckets: list[datetime], columns: int) -> list[list[float]]:
    """Spread grouped rows over the full bucket list, zero-filling the gaps."""
    lookup = {row[0].strftime(_KEY): row[1:] for row in rows}
    series = [[0.0] * len(buckets) for _ in range(columns)]
    for index, bucket in enumerate(buckets):
        values = lookup.get(bucket.strftime(_KEY))
        if values is None:
            continue
        for column in range(columns):
            series[column][index] = float(values[column] or 0)
    return series


async def _student_series(db: AsyncSession, filters: Filters, buckets: list[datetime], window_end: datetime, now: datetime) -> dict[str, list[float]]:
    predicates = _student_predicates(filters)
    granularity = filters.granularity

    created_bucket = _bucket_expr(Student.created_at, granularity)
    created_rows = (
        await db.execute(
            select(created_bucket.label("bucket"), func.count().label("value"))
            .where(Student.created_at >= buckets[0], Student.created_at < window_end, *predicates)
            .group_by(created_bucket)
        )
    ).all()
    (new_students,) = _densify(created_rows, buckets, 1)

    # The roster line is a level, so it needs everyone signed up before the window.
    baseline = float(await db.scalar(select(func.count()).select_from(Student).where(Student.created_at < buckets[0], *predicates)) or 0)
    roster, running = [], baseline
    for added in new_students:
        running += added
        roster.append(running)

    session_predicates = _session_predicates(filters)
    taught_bucket = _bucket_expr(Session.session_date, granularity)
    taught_rows = (
        await db.execute(
            select(taught_bucket.label("bucket"), func.count(func.distinct(Session.student_id)).label("value"))
            .where(
                Session.session_date >= buckets[0],
                Session.session_date < window_end,
                Session.is_no_show.is_(False),
                *session_predicates,
            )
            .group_by(taught_bucket)
        )
    ).all()
    (taught,) = _densify(taught_rows, buckets, 1)

    # A student "goes quiet" in the bucket containing (last session + CHURN_QUIET).
    # Taking the max means each student is counted at most once. The `<= now` bound
    # matters: without it a student whose last session was only a fortnight ago
    # would already be plotted as churned in a bucket that hasn't happened yet.
    last_seen = (
        select(Session.student_id, func.max(Session.session_date).label("last_date"))
        .where(Session.is_no_show.is_(False), *session_predicates)
        .group_by(Session.student_id)
        .subquery()
    )
    quiet_moment = last_seen.c.last_date + literal(CHURN_QUIET, Interval)
    quiet_bucket = _bucket_expr(quiet_moment, granularity)
    quiet_rows = (
        await db.execute(
            select(quiet_bucket.label("bucket"), func.count().label("value"))
            .where(quiet_moment >= buckets[0], quiet_moment < window_end, quiet_moment <= now)
            .group_by(quiet_bucket)
        )
    ).all()
    (churned,) = _densify(quiet_rows, buckets, 1)

    return {
        "students_new": new_students,
        "students_roster": roster,
        "students_taught": taught,
        "students_churned": churned,
    }


async def _session_series(db: AsyncSession, filters: Filters, buckets: list[datetime], window_end: datetime) -> dict[str, list[float]]:
    bucket = _bucket_expr(Session.session_date, filters.granularity)
    rows = (
        await db.execute(
            select(
                bucket.label("bucket"),
                func.count().label("sessions"),
                func.sum(_hours).label("hours"),
                func.count().filter(Session.is_no_show).label("no_shows"),
            )
            .where(Session.session_date >= buckets[0], Session.session_date < window_end, *_session_predicates(filters))
            .group_by(bucket)
        )
    ).all()
    counts, hours, no_shows = _densify(rows, buckets, 3)
    return {
        "sessions_count": counts,
        "sessions_hours": [round(value, 2) for value in hours],
        "sessions_no_shows": no_shows,
    }


async def _payment_series(db: AsyncSession, filters: Filters, buckets: list[datetime], window_end: datetime) -> dict[str, list[float]]:
    bucket = _bucket_expr(Payment.payment_date, filters.granularity)
    rows = (
        await db.execute(
            select(bucket.label("bucket"), func.sum(Payment.amount).label("amount"), func.count().label("count"))
            .where(Payment.payment_date >= buckets[0], Payment.payment_date < window_end, *_payment_predicates(filters))
            .group_by(bucket)
        )
    ).all()
    amounts, counts = _densify(rows, buckets, 2)
    return {
        "payments_amount": [round(value, 2) for value in amounts],
        "payments_count": counts,
    }


# ── Entry point ──────────────────────────────────────────────────────────────


async def get_trends(db: AsyncSession, filters: Filters, now: datetime | None = None) -> dict:
    """Build every trend series for `filters`, plus totals and prior-period deltas."""
    now = now or datetime.now(timezone.utc)
    filters = replace(filters, granularity=fit_granularity(filters.start, filters.end, filters.granularity))
    granularity = filters.granularity

    visible = bucket_range(filters.start, filters.end, granularity)
    # Prepend an equally long window so each metric has something to compare to.
    prior, cursor = [], visible[0]
    for _ in range(len(visible)):
        cursor = step_bucket(cursor, granularity, forward=False)
        prior.insert(0, cursor)
    buckets = prior + visible
    split = len(prior)
    window_end = step_bucket(visible[-1], granularity)

    raw: dict[str, list[float]] = {}
    raw.update(await _student_series(db, filters, buckets, window_end, now))
    raw.update(await _session_series(db, filters, buckets, window_end))
    raw.update(await _payment_series(db, filters, buckets, window_end))

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


async def get_filter_options(db: AsyncSession) -> dict:
    """Dropdown contents for the filter bar."""
    tutors = (
        await db.execute(
            select(User.id, User.first_name, User.last_name)
            .where(User.role.in_((UserRole.tutor, UserRole.admin_tutor)))
            .order_by(User.first_name, User.last_name)
        )
    ).all()
    students = (await db.execute(select(Student.id, Student.first_name, Student.last_name).order_by(Student.first_name, Student.last_name))).all()
    payees = (await db.execute(select(Payee.id, Payee.first_name, Payee.last_name).order_by(Payee.first_name, Payee.last_name))).all()

    def _options(rows):
        return [{"id": str(row.id), "name": f"{row.first_name} {row.last_name}"} for row in rows]

    return {"tutors": _options(tutors), "students": _options(students), "payees": _options(payees)}
