from app.services import payee as payee_service


async def test_get_balances_empty_list_returns_empty_dict(db):
    result = await payee_service.get_balances(db, [])
    assert result == {}
