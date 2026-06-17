from datetime import datetime, timedelta, timezone

from app.auth import hash_password
from app.models.payee import Payee
from app.models.payment import Payment
from app.models.session import Session
from app.models.student import Student
from app.models.user import PayoutType, User, UserRole
from app.services import dashboard as dashboard_service
from app.services.dashboard import _pct_change


def test_pct_change_increase():
    assert _pct_change(10.0, 5.0) == 100.0


def test_pct_change_decrease():
    assert _pct_change(5.0, 10.0) == -50.0


def test_pct_change_zero_previous_returns_none():
    assert _pct_change(10.0, 0.0) is None


async def test_get_tutor_stats_with_no_data(db):
    tutor = User(
        email="tutor@test.com",
        hashed_password=hash_password("password"),
        first_name="Test",
        last_name="Tutor",
        role=UserRole.tutor,
        is_active=True,
    )
    db.add(tutor)
    await db.commit()
    await db.refresh(tutor)

    stats = await dashboard_service.get_tutor_stats(db, tutor)
    assert stats["active_students"] == 0
    assert stats["sessions_this_week"] == 0
    assert stats["sessions_this_month"] == 0
    assert stats["amount_owed"] == 0.0


async def test_get_tutor_stats_with_student_and_session(db):
    now = datetime.now(timezone.utc)
    tutor = User(
        email="tutor@test.com",
        hashed_password=hash_password("password"),
        first_name="Test",
        last_name="Tutor",
        role=UserRole.tutor,
        is_active=True,
        payout_type=PayoutType.hourly,
        payout_hourly_rate=30.0,
    )
    db.add(tutor)
    await db.commit()
    await db.refresh(tutor)

    student = Student(user_id=tutor.id, first_name="Test", last_name="Student", is_active=True, hourly_rate=50.0)
    db.add(student)
    await db.commit()
    await db.refresh(student)

    session_start = now.replace(minute=0, second=0, microsecond=0)
    db.add(Session(
        user_id=tutor.id,
        student_id=student.id,
        session_date=now,
        session_start_time=session_start,
        session_end_time=session_start + timedelta(hours=1),
    ))
    await db.commit()

    stats = await dashboard_service.get_tutor_stats(db, tutor)
    assert stats["active_students"] == 1
    assert stats["sessions_this_month"] == 1
    assert stats["sessions_this_week"] == 1
    assert stats["amount_owed"] == 30.0  # 1 hr × £30 payout rate


async def test_get_admin_stats_with_no_data(db):
    stats = await dashboard_service.get_admin_stats(db)
    assert stats["revenue_alltime"] == 0.0
    assert stats["revenue_this_month"] == 0.0
    assert stats["active_tutors"] == 0
    assert stats["active_students"] == 0
    assert stats["sessions_this_month"] == 0
    assert stats["top_by_hours"] == []
    assert stats["at_risk_students"] == []
    assert stats["new_students"] == []


async def test_get_admin_stats_counts_tutors_and_students(db):
    tutor = User(
        email="tutor@test.com",
        hashed_password=hash_password("password"),
        first_name="Test",
        last_name="Tutor",
        role=UserRole.tutor,
        is_active=True,
    )
    db.add(tutor)
    await db.commit()
    await db.refresh(tutor)

    db.add(Student(user_id=tutor.id, first_name="Test", last_name="Student", is_active=True))
    await db.commit()

    stats = await dashboard_service.get_admin_stats(db)
    assert stats["active_tutors"] == 1
    assert stats["active_students"] == 1


async def test_get_admin_stats_revenue(db):
    now = datetime.now(timezone.utc)
    tutor = User(
        email="tutor@test.com",
        hashed_password=hash_password("password"),
        first_name="Test",
        last_name="Tutor",
        role=UserRole.tutor,
        is_active=True,
    )
    db.add(tutor)
    await db.commit()
    await db.refresh(tutor)

    payee = Payee(user_id=tutor.id, first_name="Test", last_name="Payee")
    db.add(payee)
    await db.commit()
    await db.refresh(payee)

    db.add(Payment(user_id=tutor.id, payee_id=payee.id, amount=150.0, payment_date=now))
    await db.commit()

    stats = await dashboard_service.get_admin_stats(db)
    assert stats["revenue_alltime"] == 150.0
    assert stats["revenue_this_month"] == 150.0


async def test_get_admin_stats_top_by_hours(db):
    now = datetime.now(timezone.utc)
    tutor = User(
        email="tutor@test.com",
        hashed_password=hash_password("password"),
        first_name="Alice",
        last_name="Smith",
        role=UserRole.tutor,
        is_active=True,
    )
    db.add(tutor)
    await db.commit()
    await db.refresh(tutor)

    student = Student(user_id=tutor.id, first_name="Test", last_name="Student", is_active=True, hourly_rate=50.0)
    db.add(student)
    await db.commit()
    await db.refresh(student)

    session_start = now.replace(minute=0, second=0, microsecond=0)
    db.add(Session(
        user_id=tutor.id,
        student_id=student.id,
        session_date=now,
        session_start_time=session_start,
        session_end_time=session_start + timedelta(hours=2),
    ))
    await db.commit()

    stats = await dashboard_service.get_admin_stats(db)
    assert len(stats["top_by_hours"]) == 1
    assert stats["top_by_hours"][0]["name"] == "Alice Smith"
    assert stats["top_by_hours"][0]["hours"] == 2.0
