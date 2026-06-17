async def _create_payee(client, headers):
    resp = await client.post(
        "/api/v1/payees/",
        json={"first_name": "John", "last_name": "Doe", "email": "john@example.com"},
        headers=headers,
    )
    return resp.json()


async def _create_payment(client, headers, payee_id, **overrides):
    payload = {
        "payee_id": payee_id,
        "amount": 50.00,
        "payment_date": "2026-01-01T00:00:00Z",
        **overrides,
    }
    resp = await client.post("/api/v1/payments/", json=payload, headers=headers)
    return resp.json()


async def test_create_payment(client, admin_headers):
    payee = await _create_payee(client, admin_headers)
    response = await client.post(
        "/api/v1/payments/",
        json={
            "payee_id": payee["id"],
            "amount": 50.00,
            "payment_date": "2026-01-01T00:00:00Z",
        },
        headers=admin_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["amount"] == 50.0


async def test_get_payments(client, admin_headers):
    payee = await _create_payee(client, admin_headers)
    await _create_payment(client, admin_headers, payee["id"])
    response = await client.get("/api/v1/payments/", headers=admin_headers)
    assert response.status_code == 200
    assert len(response.json()) == 1


async def test_get_empty_payments(client, admin_headers):
    response = await client.get("/api/v1/payments/", headers=admin_headers)
    assert response.status_code == 200
    assert response.json() == []


async def test_get_payment_by_id(client, admin_headers):
    payee = await _create_payee(client, admin_headers)
    payment = await _create_payment(client, admin_headers, payee["id"])
    response = await client.get(f"/api/v1/payments/{payment['id']}", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["id"] == payment["id"]


async def test_get_nonexistent_payment(client, admin_headers):
    response = await client.get(
        "/api/v1/payments/00000000-0000-0000-0000-000000000000",
        headers=admin_headers,
    )
    assert response.status_code == 404


async def test_update_payment_amount(client, admin_headers):
    payee = await _create_payee(client, admin_headers)
    payment = await _create_payment(client, admin_headers, payee["id"])
    response = await client.patch(
        f"/api/v1/payments/{payment['id']}",
        json={"amount": 75.00},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["amount"] == 75.0


async def test_delete_payment(client, admin_headers):
    payee = await _create_payee(client, admin_headers)
    payment = await _create_payment(client, admin_headers, payee["id"])
    response = await client.delete(f"/api/v1/payments/{payment['id']}", headers=admin_headers)
    assert response.status_code == 204


async def test_get_payments_requires_auth(client):
    response = await client.get("/api/v1/payments/")
    assert response.status_code == 401


async def test_tutor_cannot_list_payments(client, tutor_headers):
    response = await client.get("/api/v1/payments/", headers=tutor_headers)
    assert response.status_code == 403


async def test_tutor_cannot_create_payment(client, admin_headers, tutor_headers):
    payee = await _create_payee(client, admin_headers)
    response = await client.post(
        "/api/v1/payments/",
        json={"payee_id": payee["id"], "amount": 50.0, "payment_date": "2026-01-01T00:00:00Z"},
        headers=tutor_headers,
    )
    assert response.status_code == 403


async def test_tutor_cannot_get_payment(client, admin_headers, tutor_headers):
    payee = await _create_payee(client, admin_headers)
    payment = await _create_payment(client, admin_headers, payee["id"])
    response = await client.get(f"/api/v1/payments/{payment['id']}", headers=tutor_headers)
    assert response.status_code == 403


async def test_tutor_cannot_update_payment(client, admin_headers, tutor_headers):
    payee = await _create_payee(client, admin_headers)
    payment = await _create_payment(client, admin_headers, payee["id"])
    response = await client.patch(
        f"/api/v1/payments/{payment['id']}",
        json={"amount": 75.0},
        headers=tutor_headers,
    )
    assert response.status_code == 403


async def test_tutor_cannot_delete_payment(client, admin_headers, tutor_headers):
    payee = await _create_payee(client, admin_headers)
    payment = await _create_payment(client, admin_headers, payee["id"])
    response = await client.delete(f"/api/v1/payments/{payment['id']}", headers=tutor_headers)
    assert response.status_code == 403


async def test_update_nonexistent_payment(client, admin_headers):
    response = await client.patch(
        "/api/v1/payments/00000000-0000-0000-0000-000000000000",
        json={"amount": 75.00},
        headers=admin_headers,
    )
    assert response.status_code == 404


async def test_delete_nonexistent_payment(client, admin_headers):
    response = await client.delete(
        "/api/v1/payments/00000000-0000-0000-0000-000000000000",
        headers=admin_headers,
    )
    assert response.status_code == 404
