from app.auth import hash_password
from app.models.payee import Payee
from app.models.user import User, UserRole
from app.services import payee as payee_service


async def _make_admin(db):
    user = User(
        email="admin@test.com",
        hashed_password=hash_password("pw"),
        first_name="Admin",
        last_name="User",
        role=UserRole.admin,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _make_payee(db, user_id, first_name="John", last_name="Doe"):
    payee = Payee(user_id=user_id, first_name=first_name, last_name=last_name)
    db.add(payee)
    await db.commit()
    await db.refresh(payee)
    return payee


async def test_get_balances_empty_list_returns_empty_dict(db):
    result = await payee_service.get_balances(db, [])
    assert result == {}


async def test_get_balances_with_payee_no_activity(db):
    admin = await _make_admin(db)
    payee = await _make_payee(db, admin.id)

    result = await payee_service.get_balances(db, [payee.id])
    assert result == {str(payee.id): 0.0}


async def test_list_payees_with_search(db):
    admin = await _make_admin(db)
    await _make_payee(db, admin.id, "Alice", "Smith")
    await _make_payee(db, admin.id, "Bob", "Jones")

    results = await payee_service.list_payees(db, admin, q="alice")
    assert len(results) == 1
    assert results[0].first_name == "Alice"


async def test_update_payee_capitalises_names(db):
    import uuid
    from app.exceptions import NotFoundError
    import pytest

    admin = await _make_admin(db)
    payee = await _make_payee(db, admin.id, "john", "doe")

    result = await payee_service.update_payee(db, payee.id, admin, {"first_name": "james", "last_name": "smith"})
    assert result.first_name == "James"
    assert result.last_name == "Smith"


async def test_update_payee_not_found(db):
    import uuid
    import pytest
    from app.exceptions import NotFoundError

    admin = await _make_admin(db)
    with pytest.raises(NotFoundError):
        await payee_service.update_payee(db, uuid.uuid4(), admin, {"first_name": "New"})
