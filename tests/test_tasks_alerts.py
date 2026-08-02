import asyncio
from datetime import datetime, timezone

import pytest

from app.models.payee import Payee
from app.models.payment import Payment
from app.models.session import Session
from app.models.student import Student
from app.tasks import alerts as alerts_task


@pytest.fixture()
def sent(monkeypatch):
    captured: list[dict] = []
    monkeypatch.setattr(alerts_task.resend.Emails, "send", lambda params: captured.append(params))
    return captured


async def _run_task() -> None:
    """The task calls asyncio.run(), so it needs a thread without a running loop."""
    await asyncio.to_thread(alerts_task.send_overdue_alerts)


async def _make_payee(db, user_id, first_name="Pat", last_name="Payer"):
    payee = Payee(user_id=user_id, first_name=first_name, last_name=last_name)
    db.add(payee)
    await db.commit()
    await db.refresh(payee)
    return payee


async def _make_student(db, user_id, payee_id=None, hourly_rate=50.0):
    student = Student(
        user_id=user_id,
        payee_id=payee_id,
        first_name="Jane",
        last_name="Doe",
        hourly_rate=hourly_rate,
    )
    db.add(student)
    await db.commit()
    await db.refresh(student)
    return student


async def _make_session(db, user_id, student_id, hours=1):
    start = datetime(2024, 1, 15, 9, 0, tzinfo=timezone.utc)
    end = datetime(2024, 1, 15, 9 + hours, 0, tzinfo=timezone.utc)
    s = Session(
        user_id=user_id,
        student_id=student_id,
        session_date=start,
        session_start_time=start,
        session_end_time=end,
    )
    db.add(s)
    await db.commit()
    return s


async def _make_payment(db, user_id, payee_id, amount):
    p = Payment(
        user_id=user_id,
        payee_id=payee_id,
        amount=amount,
        payment_date=datetime(2024, 1, 20, tzinfo=timezone.utc),
    )
    db.add(p)
    await db.commit()
    return p


async def test_fetch_returns_none_without_admin(db):
    email, overdue = await alerts_task._fetch_overdue_data()
    assert email is None
    assert overdue == []


async def test_fetch_returns_admin_email_with_no_overdue(db, admin_user):
    email, overdue = await alerts_task._fetch_overdue_data()
    assert email == "admin@example.com"
    assert overdue == []


async def test_fetch_reports_unpaid_balance(db, admin_user):
    payee = await _make_payee(db, admin_user.id)
    student = await _make_student(db, admin_user.id, payee.id, hourly_rate=50.0)
    await _make_session(db, admin_user.id, student.id, hours=2)

    email, overdue = await alerts_task._fetch_overdue_data()

    assert email == "admin@example.com"
    assert overdue == [{"name": "Pat Payer", "balance": 100.0}]


async def test_fetch_subtracts_payments_from_cost(db, admin_user):
    payee = await _make_payee(db, admin_user.id)
    student = await _make_student(db, admin_user.id, payee.id, hourly_rate=50.0)
    await _make_session(db, admin_user.id, student.id, hours=2)
    await _make_payment(db, admin_user.id, payee.id, 30)

    _, overdue = await alerts_task._fetch_overdue_data()

    assert overdue == [{"name": "Pat Payer", "balance": 70.0}]


async def test_fetch_excludes_fully_paid_payee(db, admin_user):
    payee = await _make_payee(db, admin_user.id)
    student = await _make_student(db, admin_user.id, payee.id, hourly_rate=50.0)
    await _make_session(db, admin_user.id, student.id, hours=1)
    await _make_payment(db, admin_user.id, payee.id, 50)

    _, overdue = await alerts_task._fetch_overdue_data()

    assert overdue == []


async def test_fetch_ignores_student_without_payee(db, admin_user):
    student = await _make_student(db, admin_user.id, payee_id=None, hourly_rate=50.0)
    await _make_session(db, admin_user.id, student.id, hours=1)

    _, overdue = await alerts_task._fetch_overdue_data()

    assert overdue == []


async def test_fetch_ignores_student_without_hourly_rate(db, admin_user):
    payee = await _make_payee(db, admin_user.id)
    student = await _make_student(db, admin_user.id, payee.id, hourly_rate=None)
    await _make_session(db, admin_user.id, student.id, hours=1)

    _, overdue = await alerts_task._fetch_overdue_data()

    assert overdue == []


async def test_no_email_without_admin(db, sent):
    await _run_task()
    assert sent == []


async def test_no_email_when_nothing_overdue(db, admin_user, sent):
    await _run_task()
    assert sent == []


async def test_sends_alert_listing_each_overdue_payee(db, admin_user, sent):
    payee = await _make_payee(db, admin_user.id)
    student = await _make_student(db, admin_user.id, payee.id, hourly_rate=50.0)
    await _make_session(db, admin_user.id, student.id, hours=2)

    await _run_task()

    assert len(sent) == 1
    assert sent[0]["to"] == ["admin@example.com"]
    assert sent[0]["subject"] == "TutorHub: 1 overdue payment(s)"
    body = sent[0]["text"]
    assert "Pat Payer" in body
    assert "£100.00 outstanding" in body
    assert "1 payee(s)" in body


async def test_alert_covers_multiple_payees(db, admin_user, sent):
    first = await _make_payee(db, admin_user.id, "Ann", "Adams")
    second = await _make_payee(db, admin_user.id, "Ben", "Brown")
    s1 = await _make_student(db, admin_user.id, first.id, hourly_rate=40.0)
    s2 = await _make_student(db, admin_user.id, second.id, hourly_rate=60.0)
    await _make_session(db, admin_user.id, s1.id, hours=1)
    await _make_session(db, admin_user.id, s2.id, hours=1)

    await _run_task()

    body = sent[0]["text"]
    assert sent[0]["subject"] == "TutorHub: 2 overdue payment(s)"
    assert "Ann Adams: £40.00 outstanding" in body
    assert "Ben Brown: £60.00 outstanding" in body
