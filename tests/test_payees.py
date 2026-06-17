async def _create_payee(client, headers, **overrides):
    payload = {
        "first_name": "John",
        "last_name": "Doe",
        "email": "john@example.com",
        "phone_number": "+447700900000",
        **overrides,
    }
    resp = await client.post("/api/v1/payees/", json=payload, headers=headers)
    return resp.json()


async def test_create_payee(client, admin_headers):
    response = await client.post(
        "/api/v1/payees/",
        json={"first_name": "John", "last_name": "Doe", "email": "john@example.com", "phone_number": "+447700900000"},
        headers=admin_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["first_name"] == "John"
    assert data["email"] == "john@example.com"


async def test_get_payees(client, admin_headers):
    await _create_payee(client, admin_headers)
    response = await client.get("/api/v1/payees/", headers=admin_headers)
    assert response.status_code == 200
    assert len(response.json()) == 1


async def test_get_empty_payees(client, admin_headers):
    response = await client.get("/api/v1/payees/", headers=admin_headers)
    assert response.status_code == 200
    assert response.json() == []


async def test_get_payee_by_id(client, admin_headers):
    payee = await _create_payee(client, admin_headers)
    response = await client.get(f"/api/v1/payees/{payee['id']}", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["id"] == payee["id"]


async def test_get_nonexistent_payee(client, admin_headers):
    response = await client.get(
        "/api/v1/payees/00000000-0000-0000-0000-000000000000",
        headers=admin_headers,
    )
    assert response.status_code == 404


async def test_update_payee(client, admin_headers):
    payee = await _create_payee(client, admin_headers)
    response = await client.patch(
        f"/api/v1/payees/{payee['id']}",
        json={"phone_number": "+447700900001"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["phone_number"] == "+447700900001"


async def test_delete_payee(client, admin_headers):
    payee = await _create_payee(client, admin_headers)
    response = await client.delete(f"/api/v1/payees/{payee['id']}", headers=admin_headers)
    assert response.status_code == 204


async def test_get_payees_requires_auth(client):
    response = await client.get("/api/v1/payees/")
    assert response.status_code == 401


async def test_tutor_cannot_list_payees(client, tutor_headers):
    response = await client.get("/api/v1/payees/", headers=tutor_headers)
    assert response.status_code == 403


async def test_tutor_cannot_create_payee(client, tutor_headers):
    response = await client.post(
        "/api/v1/payees/",
        json={"first_name": "Test", "last_name": "Payee", "email": "test@example.com"},
        headers=tutor_headers,
    )
    assert response.status_code == 403


async def test_tutor_cannot_get_payee(client, admin_headers, tutor_headers):
    payee = await _create_payee(client, admin_headers)
    response = await client.get(f"/api/v1/payees/{payee['id']}", headers=tutor_headers)
    assert response.status_code == 403


async def test_tutor_cannot_update_payee(client, admin_headers, tutor_headers):
    payee = await _create_payee(client, admin_headers)
    response = await client.patch(
        f"/api/v1/payees/{payee['id']}",
        json={"phone_number": "+447700900001"},
        headers=tutor_headers,
    )
    assert response.status_code == 403


async def test_tutor_cannot_delete_payee(client, admin_headers, tutor_headers):
    payee = await _create_payee(client, admin_headers)
    response = await client.delete(f"/api/v1/payees/{payee['id']}", headers=tutor_headers)
    assert response.status_code == 403


async def test_payee_balance_zero_with_no_activity(client, admin_headers):
    payee = await _create_payee(client, admin_headers)
    response = await client.get(f"/api/v1/payees/{payee['id']}/balance", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["balance"] == 0.0


async def test_update_nonexistent_payee(client, admin_headers):
    response = await client.patch(
        "/api/v1/payees/00000000-0000-0000-0000-000000000000",
        json={"phone_number": "+447700900001"},
        headers=admin_headers,
    )
    assert response.status_code == 404


async def test_delete_nonexistent_payee(client, admin_headers):
    response = await client.delete(
        "/api/v1/payees/00000000-0000-0000-0000-000000000000",
        headers=admin_headers,
    )
    assert response.status_code == 404


async def test_search_payees(client, admin_headers):
    await _create_payee(client, admin_headers)
    await _create_payee(client, admin_headers, first_name="Jane", last_name="Smith", email="jane@example.com")
    response = await client.get("/api/v1/payees/?q=john", headers=admin_headers)
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["first_name"] == "John"


async def test_update_payee_capitalises_name(client, admin_headers):
    payee = await _create_payee(client, admin_headers)
    response = await client.patch(
        f"/api/v1/payees/{payee['id']}",
        json={"first_name": "alice", "last_name": "jones"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["first_name"] == "Alice"
    assert response.json()["last_name"] == "Jones"


async def test_payee_balance_with_payment(client, admin_headers):
    payee = await _create_payee(client, admin_headers)
    await client.post(
        "/api/v1/payments/",
        json={"payee_id": payee["id"], "amount": 100.0, "payment_date": "2026-06-01T00:00:00Z"},
        headers=admin_headers,
    )
    response = await client.get(f"/api/v1/payees/{payee['id']}/balance", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["balance"] == 100.0
