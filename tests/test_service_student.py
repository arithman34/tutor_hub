import uuid
from unittest.mock import AsyncMock

import pytest

from app.auth import hash_password
from app.exceptions import ForbiddenError, NotFoundError
from app.models.payee import Payee
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


async def test_create_student_generates_ilp_document(db, monkeypatch):
    admin = await _make_user(db, "admin@test.com", UserRole.admin)
    tutor = await _make_user(db, "tutor@test.com")
    payee = Payee(user_id=tutor.id, first_name="Pat", last_name="Payer")
    db.add(payee)
    await db.commit()
    await db.refresh(payee)

    create = AsyncMock(return_value="new-doc-id")
    monkeypatch.setattr(student_service.gdocs_service, "create_ilp_document", create)

    student = await student_service.create_student(db, admin, user_id=tutor.id, first_name="jane", last_name="doe", payee_id=payee.id)

    assert student.google_doc_id == "new-doc-id"
    assert student.first_name == "Jane"
    assert create.await_args.args[2].id == payee.id


async def test_create_student_keeps_existing_google_doc(db, monkeypatch):
    admin = await _make_user(db, "admin@test.com", UserRole.admin)
    tutor = await _make_user(db, "tutor@test.com")

    create = AsyncMock()
    monkeypatch.setattr(student_service.gdocs_service, "create_ilp_document", create)

    student = await student_service.create_student(db, admin, user_id=tutor.id, first_name="Jane", last_name="Doe", google_doc_id="existing-doc")

    assert student.google_doc_id == "existing-doc"
    create.assert_not_awaited()


async def test_create_student_survives_ilp_failure(db, monkeypatch):
    admin = await _make_user(db, "admin@test.com", UserRole.admin)
    tutor = await _make_user(db, "tutor@test.com")

    create = AsyncMock(side_effect=RuntimeError("google is down"))
    monkeypatch.setattr(student_service.gdocs_service, "create_ilp_document", create)

    student = await student_service.create_student(db, admin, user_id=tutor.id, first_name="Jane", last_name="Doe")

    assert student.id is not None
    assert student.google_doc_id is None


async def test_create_student_forbidden_for_tutor(db):
    tutor = await _make_user(db, "tutor@test.com")
    with pytest.raises(ForbiddenError):
        await student_service.create_student(db, tutor, user_id=tutor.id, first_name="Jane", last_name="Doe")
