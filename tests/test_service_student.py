import uuid

import pytest

from app.auth import hash_password
from app.exceptions import ForbiddenError, NotFoundError
from app.models.student import Student
from app.models.user import User, UserRole
from app.services import student as student_service


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


async def test_list_students_admin_with_search(db):
    admin = await _make_user(db, "admin@test.com", UserRole.admin)
    tutor = await _make_user(db, "tutor@test.com")
    await _make_student(db, tutor.id, "Alice", "Smith")
    await _make_student(db, tutor.id, "Bob", "Jones")

    results = await student_service.list_students(db, admin, q="alice")
    assert len(results) == 1
    assert results[0].first_name == "Alice"


async def test_list_students_tutor_with_search(db):
    tutor = await _make_user(db, "tutor@test.com")
    await _make_student(db, tutor.id, "Alice", "Smith")
    await _make_student(db, tutor.id, "Bob", "Jones")

    results = await student_service.list_students(db, tutor, q="Jones")
    assert len(results) == 1
    assert results[0].last_name == "Jones"


async def test_update_student_not_found(db):
    admin = await _make_user(db, "admin@test.com", UserRole.admin)
    with pytest.raises(NotFoundError):
        await student_service.update_student(db, uuid.uuid4(), admin, {"first_name": "New"})


async def test_update_student_forbidden_for_tutor(db):
    tutor = await _make_user(db, "tutor@test.com")
    student = await _make_student(db, tutor.id)
    with pytest.raises(ForbiddenError):
        await student_service.update_student(db, student.id, tutor, {"first_name": "New"})


async def test_update_student_capitalises_names(db):
    admin = await _make_user(db, "admin@test.com", UserRole.admin)
    tutor = await _make_user(db, "tutor@test.com")
    student = await _make_student(db, tutor.id, "jane", "doe")

    result = await student_service.update_student(db, student.id, admin, {"first_name": "alice", "last_name": "smith"})
    assert result.first_name == "Alice"
    assert result.last_name == "Smith"


async def test_toggle_active_not_found(db):
    admin = await _make_user(db, "admin@test.com", UserRole.admin)
    with pytest.raises(NotFoundError):
        await student_service.toggle_active(db, uuid.uuid4(), admin)


async def test_toggle_active_forbidden_for_tutor(db):
    tutor = await _make_user(db, "tutor@test.com")
    student = await _make_student(db, tutor.id)
    with pytest.raises(ForbiddenError):
        await student_service.toggle_active(db, student.id, tutor)


async def test_toggle_active_flips_status(db):
    admin = await _make_user(db, "admin@test.com", UserRole.admin)
    tutor = await _make_user(db, "tutor@test.com")
    student = await _make_student(db, tutor.id)
    assert student.is_active is True

    result = await student_service.toggle_active(db, student.id, admin)
    assert result.is_active is False


async def test_delete_student_not_found(db):
    admin = await _make_user(db, "admin@test.com", UserRole.admin)
    with pytest.raises(NotFoundError):
        await student_service.delete_student(db, uuid.uuid4(), admin)


async def test_delete_student_forbidden_for_tutor(db):
    tutor = await _make_user(db, "tutor@test.com")
    student = await _make_student(db, tutor.id)
    with pytest.raises(ForbiddenError):
        await student_service.delete_student(db, student.id, tutor)
