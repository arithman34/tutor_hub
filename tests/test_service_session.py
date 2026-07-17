import uuid
from datetime import datetime, timezone

import pytest

from app.auth import hash_password
from app.exceptions import ForbiddenError, NotFoundError
from app.models.session import Session
from app.models.student import Student
from app.models.user import User, UserRole
from app.services import session as session_service


async def _make_user(db, email, role=UserRole.tutor):
    user = User(
        email=email,
        hashed_password=hash_password("pw"),
        first_name="Test",
        last_name="User",
        role=role,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _make_student(db, user_id, first_name="Jane", last_name="Doe"):
    student = Student(user_id=user_id, first_name=first_name, last_name=last_name)
    db.add(student)
    await db.commit()
    await db.refresh(student)
    return student


async def _make_session(db, user_id, student_id, **kwargs):
    defaults = dict(
        session_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
        session_start_time=datetime(2024, 1, 15, 9, 0, tzinfo=timezone.utc),
        session_end_time=datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc),
    )
    s = Session(user_id=user_id, student_id=student_id, **{**defaults, **kwargs})
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return s


async def test_list_sessions_admin_with_search(db):
    admin = await _make_user(db, "admin@test.com", UserRole.admin)
    tutor = await _make_user(db, "tutor@test.com")
    alice = await _make_student(db, tutor.id, "Alice", "Wonder")
    bob = await _make_student(db, tutor.id, "Bob", "Builder")
    await _make_session(db, tutor.id, alice.id)
    await _make_session(db, tutor.id, bob.id)

    results = await session_service.list_sessions(db, admin, q="Alice")
    assert len(results) == 1


async def test_list_sessions_tutor_with_search(db):
    tutor = await _make_user(db, "tutor@test.com")
    alice = await _make_student(db, tutor.id, "Alice", "Wonder")
    bob = await _make_student(db, tutor.id, "Bob", "Builder")
    await _make_session(db, tutor.id, alice.id)
    await _make_session(db, tutor.id, bob.id)

    results = await session_service.list_sessions(db, tutor, q="Bob")
    assert len(results) == 1


async def test_update_session_no_show_nulls_content_fields(db):
    tutor = await _make_user(db, "tutor@test.com")
    student = await _make_student(db, tutor.id)
    session = await _make_session(
        db, tutor.id, student.id,
        work_covered="Some work",
        tutor_actions="Some actions",
        student_actions="Some student actions",
        next_lesson_focus="Algebra",
        topic_tags="algebra, equations",
    )

    updated = await session_service.update_session(db, session.id, tutor, {"is_no_show": True})

    assert updated.is_no_show is True
    assert updated.work_covered is None
    assert updated.tutor_actions is None
    assert updated.student_actions is None
    assert updated.next_lesson_focus is None
    assert updated.topic_tags is None


async def test_update_session_not_found(db):
    tutor = await _make_user(db, "tutor@test.com")
    with pytest.raises(NotFoundError):
        await session_service.update_session(db, uuid.uuid4(), tutor, {"work_covered": "x"})


async def test_update_session_forbidden_for_other_tutor(db):
    tutor1 = await _make_user(db, "t1@test.com")
    tutor2 = await _make_user(db, "t2@test.com")
    student = await _make_student(db, tutor1.id)
    session = await _make_session(db, tutor1.id, student.id)

    with pytest.raises(ForbiddenError):
        await session_service.update_session(db, session.id, tutor2, {"work_covered": "x"})


async def test_delete_session_forbidden_for_other_tutor(db):
    tutor1 = await _make_user(db, "t1@test.com")
    tutor2 = await _make_user(db, "t2@test.com")
    student = await _make_student(db, tutor1.id)
    session = await _make_session(db, tutor1.id, student.id)

    with pytest.raises(ForbiddenError):
        await session_service.delete_session(db, session.id, tutor2)


