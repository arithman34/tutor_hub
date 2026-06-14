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


async def test_create_payment(client, tutor_headers):
    payee = await _create_payee(client, tutor_headers)
    response = await client.post(
        "/api/v1/payments/",
        json={
            "payee_id": payee["id"],
            "amount": 50.00,
            "payment_date": "2026-01-01T00:00:00Z",
        },
        headers=tutor_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["amount"] == 50.0


async def test_get_payments(client, tutor_headers):
    payee = await _create_payee(client, tutor_headers)
    await _create_payment(client, tutor_headers, payee["id"])
    response = await client.get("/api/v1/payments/", headers=tutor_headers)
    assert response.status_code == 200
    assert len(response.json()) == 1


async def test_get_empty_payments(client, tutor_headers):
    response = await client.get("/api/v1/payments/", headers=tutor_headers)
    assert response.status_code == 200
    assert response.json() == []


async def test_get_payment_by_id(client, tutor_headers):
    payee = await _create_payee(client, tutor_headers)
    payment = await _create_payment(client, tutor_headers, payee["id"])
    response = await client.get(f"/api/v1/payments/{payment['id']}", headers=tutor_headers)
    assert response.status_code == 200
    assert response.json()["id"] == payment["id"]


async def test_get_nonexistent_payment(client, tutor_headers):
    response = await client.get(
        "/api/v1/payments/00000000-0000-0000-0000-000000000000",
        headers=tutor_headers,
    )
    assert response.status_code == 404


async def test_update_payment_amount(client, tutor_headers):
    payee = await _create_payee(client, tutor_headers)
    payment = await _create_payment(client, tutor_headers, payee["id"])
    response = await client.patch(
        f"/api/v1/payments/{payment['id']}",
        json={"amount": 75.00},
        headers=tutor_headers,
    )
    assert response.status_code == 200
    assert response.json()["amount"] == 75.0


async def test_delete_payment(client, tutor_headers):
    payee = await _create_payee(client, tutor_headers)
    payment = await _create_payment(client, tutor_headers, payee["id"])
    response = await client.delete(f"/api/v1/payments/{payment['id']}", headers=tutor_headers)
    assert response.status_code == 204


async def test_get_payments_requires_auth(client):
    response = await client.get("/api/v1/payments/")
    assert response.status_code == 401


async def test_cannot_access_other_tutors_payment(client, admin_headers, tutor_headers):
    payee = await _create_payee(client, tutor_headers)
    payment = await _create_payment(client, tutor_headers, payee["id"])

    await client.post(
        "/api/v1/users/",
        json={
            "email": "tutor2@example.com",
            "password": "tutor2password",
            "first_name": "Jane",
            "last_name": "Smith",
            "role": "tutor",
        },
        headers=admin_headers,
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "tutor2@example.com", "password": "tutor2password"},
    )
    headers2 = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    response = await client.get(f"/api/v1/payments/{payment['id']}", headers=headers2)
    assert response.status_code == 404


async def test_update_nonexistent_payment(client, tutor_headers):
    response = await client.patch(
        "/api/v1/payments/00000000-0000-0000-0000-000000000000",
        json={"amount": 75.00},
        headers=tutor_headers,
    )
    assert response.status_code == 404


async def test_delete_nonexistent_payment(client, tutor_headers):
    response = await client.delete(
        "/api/v1/payments/00000000-0000-0000-0000-000000000000",
        headers=tutor_headers,
    )
    assert response.status_code == 404
