import uuid

import pytest

from app.auth import hash_password
from app.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models.student import Student
from app.models.user import PayoutType, User, UserRole
from app.services import user as user_service


async def _make_tutor(db, email="tutor@test.com"):
    user = User(
        email=email,
        hashed_password=hash_password("password"),
        first_name="Test",
        last_name="Tutor",
        role=UserRole.tutor,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _make_admin(db, email="admin@test.com"):
    user = User(
        email=email,
        hashed_password=hash_password("password"),
        first_name="Test",
        last_name="Admin",
        role=UserRole.admin,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def test_list_tutors_returns_only_tutors(db):
    await _make_tutor(db, "tutor1@test.com")
    await _make_tutor(db, "tutor2@test.com")
    await _make_admin(db)
    tutors = await user_service.list_tutors(db)
    assert len(tutors) == 2
    assert all(u.role == UserRole.tutor for u in tutors)


async def test_create_second_admin_raises_conflict(db):
    admin = await _make_admin(db)
    with pytest.raises(ConflictError, match="admin user already exists"):
        await user_service.create_user(
            db,
            current_user=admin,
            email="admin2@test.com",
            password="password",
            first_name="Second",
            last_name="Admin",
            role="admin",
        )


async def test_create_tutor_capitalises_name(db):
    user = await user_service.create_tutor(
        db,
        email="newtutor@test.com",
        password="password",
        first_name="jane",
        last_name="smith",
    )
    assert user is not None
    assert user.first_name == "Jane"
    assert user.last_name == "Smith"
    assert user.role == UserRole.tutor


async def test_create_tutor_duplicate_email_returns_none(db):
    await user_service.create_tutor(db, email="dup@test.com", password="password", first_name="A", last_name="B")
    result = await user_service.create_tutor(db, email="dup@test.com", password="password", first_name="A", last_name="B")
    assert result is None


async def test_toggle_active_flips_status(db):
    tutor = await _make_tutor(db)
    assert tutor.is_active is True
    updated = await user_service.toggle_active(db, tutor.id)
    assert updated.is_active is False
    toggled_back = await user_service.toggle_active(db, tutor.id)
    assert toggled_back.is_active is True


async def test_toggle_active_nonexistent_raises(db):
    with pytest.raises(NotFoundError):
        await user_service.toggle_active(db, uuid.uuid4())


async def test_toggle_active_admin_raises_forbidden(db):
    admin = await _make_admin(db)
    with pytest.raises(ForbiddenError):
        await user_service.toggle_active(db, admin.id)


async def test_update_payout_hourly(db):
    tutor = await _make_tutor(db)
    updated = await user_service.update_payout(db, tutor.id, "hourly", 30.0, None)
    assert updated.payout_type == PayoutType.hourly
    assert updated.payout_hourly_rate == 30.0
    assert updated.payout_percentage is None


async def test_update_payout_percentage(db):
    tutor = await _make_tutor(db)
    updated = await user_service.update_payout(db, tutor.id, "percentage", None, 20.0)
    assert updated.payout_type == PayoutType.percentage
    assert updated.payout_percentage == 20.0
    assert updated.payout_hourly_rate is None


async def test_update_payout_nonexistent_raises(db):
    with pytest.raises(NotFoundError):
        await user_service.update_payout(db, uuid.uuid4(), "hourly", 30.0, None)


async def test_update_payout_admin_raises_forbidden(db):
    admin = await _make_admin(db)
    with pytest.raises(ForbiddenError):
        await user_service.update_payout(db, admin.id, "hourly", 30.0, None)


async def test_tutor_has_data_false_for_clean_tutor(db):
    tutor = await _make_tutor(db)
    assert await user_service.tutor_has_data(db, tutor.id) is False


async def test_tutor_has_data_true_with_student(db):
    tutor = await _make_tutor(db)
    student = Student(user_id=tutor.id, first_name="Alice", last_name="Brown")
    db.add(student)
    await db.commit()
    assert await user_service.tutor_has_data(db, tutor.id) is True


async def test_delete_tutor_removes_clean_tutor(db):
    tutor = await _make_tutor(db)
    await user_service.delete_tutor(db, tutor.id)
    with pytest.raises(NotFoundError):
        await user_service.get_user_by_id(db, tutor.id)


async def test_delete_tutor_nonexistent_raises_not_found(db):
    with pytest.raises(NotFoundError):
        await user_service.delete_tutor(db, uuid.uuid4())


async def test_delete_tutor_admin_raises_forbidden(db):
    admin = await _make_admin(db)
    with pytest.raises(ForbiddenError):
        await user_service.delete_tutor(db, admin.id)


async def test_delete_tutor_with_data_raises_forbidden(db):
    tutor = await _make_tutor(db)
    student = Student(user_id=tutor.id, first_name="Bob", last_name="Smith")
    db.add(student)
    await db.commit()
    with pytest.raises(ForbiddenError):
        await user_service.delete_tutor(db, tutor.id)


async def test_update_profile_sets_address(db):
    tutor = await _make_tutor(db)
    updated = await user_service.update_profile(db, tutor.id, address="10 Downing Street")
    assert updated.address == "10 Downing Street"


async def test_update_profile_blank_address_clears_it(db):
    tutor = await _make_tutor(db)
    await user_service.update_profile(db, tutor.id, address="10 Downing Street")
    updated = await user_service.update_profile(db, tutor.id, address="   ")
    assert updated.address is None


async def test_update_profile_omitting_address_leaves_it_unchanged(db):
    tutor = await _make_tutor(db)
    await user_service.update_profile(db, tutor.id, address="10 Downing Street")
    updated = await user_service.update_profile(db, tutor.id, first_name="Renamed")
    assert updated.first_name == "Renamed"
    assert updated.address == "10 Downing Street"
