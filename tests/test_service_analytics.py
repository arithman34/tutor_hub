from datetime import date, datetime, timedelta, timezone

import pytest

from app.auth import hash_password
from app.models.payee import Payee
from app.models.payment import Payment
from app.models.session import Session
from app.models.student import Student
from app.models.user import User, UserRole
from app.services import analytics as analytics_service
from app.services.analytics import Filters

UTC = timezone.utc


def _at(year: int, month: int, day: int, hour: int = 12) -> datetime:
    return datetime(year, month, day, hour, tzinfo=UTC)


def _series(trends: dict, key: str) -> dict:
    for chart in trends["charts"]:
        for series in chart["series"]:
            if series["key"] == key:
                return series
    raise AssertionError(f"no series named {key}")


async def _make_tutor(db, email="tutor@test.com", first="Test", last="Tutor") -> User:
    tutor = User(
        email=email,
        hashed_password=hash_password("password"),
        first_name=first,
        last_name=last,
        role=UserRole.tutor,
        is_active=True,
    )
    db.add(tutor)
    await db.commit()
    await db.refresh(tutor)
    return tutor


async def _make_student(db, tutor, first="Test", last="Student", created_at=None, payee=None) -> Student:
    student = Student(
        user_id=tutor.id,
        payee_id=payee.id if payee else None,
        first_name=first,
        last_name=last,
        is_active=True,
        hourly_rate=50.0,
    )
    if created_at:
        student.created_at = created_at
    db.add(student)
    await db.commit()
    await db.refresh(student)
    return student


async def _make_payee(db, tutor, first="Test", last="Payee") -> Payee:
    payee = Payee(user_id=tutor.id, first_name=first, last_name=last)
    db.add(payee)
    await db.commit()
    await db.refresh(payee)
    return payee


async def _log_session(db, tutor, student, start: datetime, hours: float = 1.0, no_show: bool = False) -> None:
    db.add(
        Session(
            user_id=tutor.id,
            student_id=student.id,
            session_date=start,
            session_start_time=start,
            session_end_time=start + timedelta(hours=hours),
            is_no_show=no_show,
        )
    )
    await db.commit()


# ── Bucket maths ─────────────────────────────────────────────────────────────


def test_floor_bucket_day_strips_time():
    assert analytics_service.floor_bucket(_at(2026, 3, 17, 23), "day") == _at(2026, 3, 17, 0)


def test_floor_bucket_week_snaps_back_to_monday():
    # 2026-03-17 is a Tuesday.
    assert analytics_service.floor_bucket(_at(2026, 3, 17), "week") == _at(2026, 3, 16, 0)


def test_floor_bucket_month_snaps_to_first():
    assert analytics_service.floor_bucket(_at(2026, 3, 17), "month") == _at(2026, 3, 1, 0)


def test_floor_bucket_converts_to_utc():
    aware = datetime(2026, 3, 17, 1, tzinfo=timezone(timedelta(hours=5)))
    # 01:00+05:00 is 20:00 UTC the previous day.
    assert analytics_service.floor_bucket(aware, "day") == _at(2026, 3, 16, 0)


@pytest.mark.parametrize(
    "granularity,expected",
    [("day", _at(2026, 12, 2, 0)), ("week", _at(2026, 12, 8, 0)), ("month", _at(2027, 1, 1, 0))],
)
def test_step_bucket_forward_wraps_the_year(granularity, expected):
    assert analytics_service.step_bucket(_at(2026, 12, 1, 0), granularity, forward=True) == expected


@pytest.mark.parametrize(
    "granularity,expected",
    [("day", _at(2025, 12, 31, 0)), ("week", _at(2025, 12, 25, 0)), ("month", _at(2025, 12, 1, 0))],
)
def test_step_bucket_backward_wraps_the_year(granularity, expected):
    assert analytics_service.step_bucket(_at(2026, 1, 1, 0), granularity, forward=False) == expected


def test_bucket_range_is_inclusive_of_both_ends():
    buckets = analytics_service.bucket_range(_at(2026, 1, 15), _at(2026, 3, 2), "month")
    assert buckets == [_at(2026, 1, 1, 0), _at(2026, 2, 1, 0), _at(2026, 3, 1, 0)]


def test_fit_granularity_keeps_a_short_daily_range():
    assert analytics_service.fit_granularity(_at(2026, 1, 1), _at(2026, 2, 1), "day") == "day"


def test_fit_granularity_coarsens_one_step_at_a_time():
    # Five years is ~1,827 days (too many) but only ~261 weeks, so it stops at week.
    assert analytics_service.fit_granularity(_at(2021, 1, 1), _at(2026, 1, 1), "day") == "week"


def test_fit_granularity_coarsens_all_the_way_to_month():
    # Sixteen years overflows the cap in weeks too, so it falls through to month.
    assert analytics_service.fit_granularity(_at(2010, 1, 1), _at(2026, 1, 1), "day") == "month"


# ── Range resolution ─────────────────────────────────────────────────────────


def test_resolve_range_defaults_to_twelve_months():
    now = _at(2026, 8, 5)
    preset, start, end = analytics_service.resolve_range(None, None, None, None, now)
    assert preset == "12m"
    assert start == _at(2025, 9, 1, 0)
    assert end.date() == now.date()


def test_resolve_range_three_months_spans_three_buckets():
    preset, start, _ = analytics_service.resolve_range("3m", None, None, None, _at(2026, 8, 5))
    assert preset == "3m"
    assert start == _at(2026, 6, 1, 0)


def test_resolve_range_ytd_starts_in_january():
    _, start, _ = analytics_service.resolve_range("ytd", None, None, None, _at(2026, 8, 5))
    assert start == _at(2026, 1, 1, 0)


def test_resolve_range_all_uses_earliest_activity():
    _, start, _ = analytics_service.resolve_range("all", None, None, _at(2023, 4, 9), _at(2026, 8, 5))
    assert start == _at(2023, 4, 9)


def test_resolve_range_all_falls_back_when_there_is_no_data():
    _, start, _ = analytics_service.resolve_range("all", None, None, None, _at(2026, 8, 5))
    assert start == _at(2025, 9, 1, 0)


def test_resolve_range_explicit_dates_override_the_preset():
    preset, start, end = analytics_service.resolve_range("12m", date(2026, 2, 1), date(2026, 4, 30), None, _at(2026, 8, 5))
    assert preset == "custom"
    assert start == _at(2026, 2, 1, 0)
    assert end.date() == date(2026, 4, 30)


def test_resolve_range_swaps_inverted_dates():
    _, start, end = analytics_service.resolve_range(None, date(2026, 4, 30), date(2026, 2, 1), None, _at(2026, 8, 5))
    assert start.date() == date(2026, 2, 1)
    assert end.date() == date(2026, 4, 30)


async def test_get_earliest_activity_is_none_without_data(db):
    assert await analytics_service.get_earliest_activity(db) is None


async def test_get_earliest_activity_picks_the_oldest_across_tables(db):
    tutor = await _make_tutor(db)
    student = await _make_student(db, tutor, created_at=_at(2026, 5, 1))
    await _log_session(db, tutor, student, _at(2026, 3, 4))
    payee = await _make_payee(db, tutor)
    db.add(Payment(user_id=tutor.id, payee_id=payee.id, amount=100.0, payment_date=_at(2026, 4, 2)))
    await db.commit()

    assert await analytics_service.get_earliest_activity(db) == _at(2026, 3, 4)


# ── Trends ───────────────────────────────────────────────────────────────────


async def test_get_trends_returns_dense_zero_series_without_data(db):
    trends = await analytics_service.get_trends(db, Filters(start=_at(2026, 1, 1), end=_at(2026, 3, 31), granularity="month"))

    assert trends["granularity"] == "month"
    assert len(trends["labels"]) == 3
    for chart in trends["charts"]:
        for series in chart["series"]:
            assert series["data"] == [0.0, 0.0, 0.0], series["key"]
            assert series["total"] == 0
            assert series["change"] is None


async def test_get_trends_buckets_new_students_by_created_at(db):
    tutor = await _make_tutor(db)
    await _make_student(db, tutor, first="Ann", created_at=_at(2026, 1, 10))
    await _make_student(db, tutor, first="Ben", created_at=_at(2026, 3, 5))
    await _make_student(db, tutor, first="Cat", created_at=_at(2026, 3, 20))

    trends = await analytics_service.get_trends(db, Filters(start=_at(2026, 1, 1), end=_at(2026, 3, 31), granularity="month"))

    assert _series(trends, "students_new")["data"] == [1.0, 0.0, 2.0]
    assert _series(trends, "students_new")["total"] == 3


async def test_get_trends_roster_is_cumulative_and_includes_earlier_students(db):
    tutor = await _make_tutor(db)
    await _make_student(db, tutor, first="Old", created_at=_at(2025, 6, 1))
    await _make_student(db, tutor, first="Ann", created_at=_at(2026, 1, 10))
    await _make_student(db, tutor, first="Ben", created_at=_at(2026, 3, 5))

    trends = await analytics_service.get_trends(db, Filters(start=_at(2026, 1, 1), end=_at(2026, 3, 31), granularity="month"))

    roster = _series(trends, "students_roster")
    assert roster["data"] == [2.0, 2.0, 3.0]
    # A level, not a flow: the headline is the closing value rather than the sum.
    assert roster["total"] == 3.0


async def test_get_trends_students_taught_counts_each_student_once_per_bucket(db):
    tutor = await _make_tutor(db)
    ann = await _make_student(db, tutor, first="Ann", created_at=_at(2025, 12, 1))
    ben = await _make_student(db, tutor, first="Ben", created_at=_at(2025, 12, 1))
    await _log_session(db, tutor, ann, _at(2026, 1, 5))
    await _log_session(db, tutor, ann, _at(2026, 1, 19))
    await _log_session(db, tutor, ben, _at(2026, 1, 20))
    await _log_session(db, tutor, ben, _at(2026, 2, 3))

    trends = await analytics_service.get_trends(db, Filters(start=_at(2026, 1, 1), end=_at(2026, 3, 31), granularity="month"))

    assert _series(trends, "students_taught")["data"] == [2.0, 1.0, 0.0]


async def test_get_trends_students_taught_ignores_no_shows(db):
    tutor = await _make_tutor(db)
    ann = await _make_student(db, tutor, created_at=_at(2025, 12, 1))
    await _log_session(db, tutor, ann, _at(2026, 1, 5), no_show=True)

    trends = await analytics_service.get_trends(db, Filters(start=_at(2026, 1, 1), end=_at(2026, 2, 28), granularity="month"))

    assert _series(trends, "students_taught")["data"] == [0.0, 0.0]
    assert _series(trends, "sessions_count")["data"] == [1.0, 0.0]
    assert _series(trends, "sessions_no_shows")["data"] == [1.0, 0.0]


async def test_get_trends_counts_a_student_as_quiet_four_weeks_after_their_last_session(db):
    tutor = await _make_tutor(db)
    ann = await _make_student(db, tutor, created_at=_at(2025, 12, 1))
    await _log_session(db, tutor, ann, _at(2026, 1, 5))
    await _log_session(db, tutor, ann, _at(2026, 1, 12))  # last session; quiet from 2026-02-09

    trends = await analytics_service.get_trends(db, Filters(start=_at(2026, 1, 1), end=_at(2026, 3, 31), granularity="month"))

    assert _series(trends, "students_churned")["data"] == [0.0, 1.0, 0.0]


async def test_get_trends_does_not_project_churn_into_the_future(db):
    tutor = await _make_tutor(db)
    ann = await _make_student(db, tutor, created_at=_at(2025, 12, 1))
    # Last session two weeks before "now", so the four-week mark has not arrived.
    await _log_session(db, tutor, ann, _at(2026, 2, 15))

    trends = await analytics_service.get_trends(
        db,
        Filters(start=_at(2026, 1, 1), end=_at(2026, 3, 31), granularity="month"),
        now=_at(2026, 3, 1),
    )

    assert _series(trends, "students_churned")["data"] == [0.0, 0.0, 0.0]


async def test_get_trends_counts_churn_once_the_quiet_period_has_elapsed(db):
    tutor = await _make_tutor(db)
    ann = await _make_student(db, tutor, created_at=_at(2025, 12, 1))
    await _log_session(db, tutor, ann, _at(2026, 2, 15))  # quiet from 2026-03-15

    trends = await analytics_service.get_trends(
        db,
        Filters(start=_at(2026, 1, 1), end=_at(2026, 3, 31), granularity="month"),
        now=_at(2026, 3, 20),
    )

    assert _series(trends, "students_churned")["data"] == [0.0, 0.0, 1.0]


async def test_get_trends_sums_session_hours(db):
    tutor = await _make_tutor(db)
    ann = await _make_student(db, tutor, created_at=_at(2025, 12, 1))
    await _log_session(db, tutor, ann, _at(2026, 1, 5), hours=1.5)
    await _log_session(db, tutor, ann, _at(2026, 1, 6), hours=2.0)

    trends = await analytics_service.get_trends(db, Filters(start=_at(2026, 1, 1), end=_at(2026, 2, 28), granularity="month"))

    assert _series(trends, "sessions_hours")["data"] == [3.5, 0.0]
    assert _series(trends, "sessions_hours")["total"] == 3.5


async def test_get_trends_sums_payments(db):
    tutor = await _make_tutor(db)
    payee = await _make_payee(db, tutor)
    db.add(Payment(user_id=tutor.id, payee_id=payee.id, amount=120.50, payment_date=_at(2026, 1, 9)))
    db.add(Payment(user_id=tutor.id, payee_id=payee.id, amount=80.00, payment_date=_at(2026, 1, 25)))
    db.add(Payment(user_id=tutor.id, payee_id=payee.id, amount=60.00, payment_date=_at(2026, 2, 2)))
    await db.commit()

    trends = await analytics_service.get_trends(db, Filters(start=_at(2026, 1, 1), end=_at(2026, 2, 28), granularity="month"))

    assert _series(trends, "payments_amount")["data"] == [200.50, 60.00]
    assert _series(trends, "payments_count")["data"] == [2.0, 1.0]
    assert _series(trends, "payments_amount")["total"] == 260.50


async def test_get_trends_compares_against_the_preceding_window(db):
    tutor = await _make_tutor(db)
    ann = await _make_student(db, tutor, created_at=_at(2025, 10, 1))
    # Prior window is Nov-Dec 2025, visible window is Jan-Feb 2026.
    await _log_session(db, tutor, ann, _at(2025, 11, 4))
    await _log_session(db, tutor, ann, _at(2025, 12, 4))
    await _log_session(db, tutor, ann, _at(2026, 1, 6))
    await _log_session(db, tutor, ann, _at(2026, 1, 7))
    await _log_session(db, tutor, ann, _at(2026, 2, 9))

    trends = await analytics_service.get_trends(db, Filters(start=_at(2026, 1, 1), end=_at(2026, 2, 28), granularity="month"))

    sessions = _series(trends, "sessions_count")
    assert sessions["data"] == [2.0, 1.0]
    assert sessions["total"] == 3
    assert sessions["change"] == 50.0  # 3 this window vs 2 in the preceding one


async def test_get_trends_filters_by_tutor(db):
    alice = await _make_tutor(db, email="alice@test.com", first="Alice")
    bob = await _make_tutor(db, email="bob@test.com", first="Bob")
    alice_student = await _make_student(db, alice, first="Ann", created_at=_at(2026, 1, 5))
    bob_student = await _make_student(db, bob, first="Ben", created_at=_at(2026, 1, 6))
    await _log_session(db, alice, alice_student, _at(2026, 1, 10))
    await _log_session(db, bob, bob_student, _at(2026, 1, 11))
    await _log_session(db, bob, bob_student, _at(2026, 1, 12))

    trends = await analytics_service.get_trends(
        db, Filters(start=_at(2026, 1, 1), end=_at(2026, 1, 31), granularity="month", tutor_id=alice.id)
    )

    assert _series(trends, "students_new")["data"] == [1.0]
    assert _series(trends, "sessions_count")["data"] == [1.0]


async def test_get_trends_filters_by_student(db):
    tutor = await _make_tutor(db)
    ann = await _make_student(db, tutor, first="Ann", created_at=_at(2026, 1, 5))
    ben = await _make_student(db, tutor, first="Ben", created_at=_at(2026, 1, 6))
    await _log_session(db, tutor, ann, _at(2026, 1, 10), hours=2.0)
    await _log_session(db, tutor, ben, _at(2026, 1, 11), hours=3.0)

    trends = await analytics_service.get_trends(db, Filters(start=_at(2026, 1, 1), end=_at(2026, 1, 31), granularity="month", student_id=ann.id))

    assert _series(trends, "sessions_count")["data"] == [1.0]
    assert _series(trends, "sessions_hours")["data"] == [2.0]
    assert _series(trends, "students_new")["data"] == [1.0]


async def test_get_trends_filters_by_payee_across_all_three_metrics(db):
    tutor = await _make_tutor(db)
    smiths = await _make_payee(db, tutor, first="Smith")
    joneses = await _make_payee(db, tutor, first="Jones")
    ann = await _make_student(db, tutor, first="Ann", created_at=_at(2026, 1, 5), payee=smiths)
    ben = await _make_student(db, tutor, first="Ben", created_at=_at(2026, 1, 6), payee=joneses)
    await _log_session(db, tutor, ann, _at(2026, 1, 10))
    await _log_session(db, tutor, ben, _at(2026, 1, 11))
    db.add(Payment(user_id=tutor.id, payee_id=smiths.id, amount=100.0, payment_date=_at(2026, 1, 20)))
    db.add(Payment(user_id=tutor.id, payee_id=joneses.id, amount=250.0, payment_date=_at(2026, 1, 21)))
    await db.commit()

    trends = await analytics_service.get_trends(db, Filters(start=_at(2026, 1, 1), end=_at(2026, 1, 31), granularity="month", payee_id=smiths.id))

    assert _series(trends, "students_new")["data"] == [1.0]
    assert _series(trends, "sessions_count")["data"] == [1.0]
    assert _series(trends, "payments_amount")["data"] == [100.0]


async def test_get_trends_coarsens_granularity_for_a_long_range(db):
    trends = await analytics_service.get_trends(db, Filters(start=_at(2010, 1, 1), end=_at(2026, 1, 1), granularity="day"))

    assert trends["granularity"] == "month"
    assert len(trends["labels"]) == 193


async def test_get_trends_supports_weekly_buckets(db):
    tutor = await _make_tutor(db)
    ann = await _make_student(db, tutor, created_at=_at(2025, 12, 1))
    await _log_session(db, tutor, ann, _at(2026, 1, 6))  # Tuesday, week of Mon 5 Jan
    await _log_session(db, tutor, ann, _at(2026, 1, 14))  # Wednesday, week of Mon 12 Jan

    trends = await analytics_service.get_trends(db, Filters(start=_at(2026, 1, 5), end=_at(2026, 1, 18), granularity="week"))

    assert trends["granularity"] == "week"
    assert trends["labels"] == [_at(2026, 1, 5, 0).isoformat(), _at(2026, 1, 12, 0).isoformat()]
    assert _series(trends, "sessions_count")["data"] == [1.0, 1.0]


async def test_get_filter_options_lists_tutors_students_and_payees(db):
    tutor = await _make_tutor(db, first="Alice", last="Smith")
    await _make_student(db, tutor, first="Ann", last="Brown")
    await _make_payee(db, tutor, first="Pat", last="Green")

    options = await analytics_service.get_filter_options(db)

    assert [t["name"] for t in options["tutors"]] == ["Alice Smith"]
    assert [s["name"] for s in options["students"]] == ["Ann Brown"]
    assert [p["name"] for p in options["payees"]] == ["Pat Green"]
