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


async def test_create_payee(client, tutor_headers):
    response = await client.post(
        "/api/v1/payees/",
        json={"first_name": "John", "last_name": "Doe", "email": "john@example.com", "phone_number": "+447700900000"},
        headers=tutor_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["first_name"] == "John"
    assert data["email"] == "john@example.com"


async def test_get_payees(client, tutor_headers):
    await _create_payee(client, tutor_headers)
    response = await client.get("/api/v1/payees/", headers=tutor_headers)
    assert response.status_code == 200
    assert len(response.json()) == 1


async def test_get_empty_payees(client, tutor_headers):
    response = await client.get("/api/v1/payees/", headers=tutor_headers)
    assert response.status_code == 200
    assert response.json() == []


async def test_get_payee_by_id(client, tutor_headers):
    payee = await _create_payee(client, tutor_headers)
    response = await client.get(f"/api/v1/payees/{payee['id']}", headers=tutor_headers)
    assert response.status_code == 200
    assert response.json()["id"] == payee["id"]


async def test_get_nonexistent_payee(client, tutor_headers):
    response = await client.get(
        "/api/v1/payees/00000000-0000-0000-0000-000000000000",
        headers=tutor_headers,
    )
    assert response.status_code == 404


async def test_update_payee(client, tutor_headers):
    payee = await _create_payee(client, tutor_headers)
    response = await client.patch(
        f"/api/v1/payees/{payee['id']}",
        json={"phone_number": "+447700900001"},
        headers=tutor_headers,
    )
    assert response.status_code == 200
    assert response.json()["phone_number"] == "+447700900001"


async def test_delete_payee(client, tutor_headers):
    payee = await _create_payee(client, tutor_headers)
    response = await client.delete(f"/api/v1/payees/{payee['id']}", headers=tutor_headers)
    assert response.status_code == 204


async def test_get_payees_requires_auth(client):
    response = await client.get("/api/v1/payees/")
    assert response.status_code == 401


async def test_cannot_access_other_tutors_payee(client, admin_headers, tutor_headers):
    payee = await _create_payee(client, tutor_headers)

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

    response = await client.get(f"/api/v1/payees/{payee['id']}", headers=headers2)
    assert response.status_code == 404


async def test_update_nonexistent_payee(client, tutor_headers):
    response = await client.patch(
        "/api/v1/payees/00000000-0000-0000-0000-000000000000",
        json={"phone_number": "+447700900001"},
        headers=tutor_headers,
    )
    assert response.status_code == 404


async def test_delete_nonexistent_payee(client, tutor_headers):
    response = await client.delete(
        "/api/v1/payees/00000000-0000-0000-0000-000000000000",
        headers=tutor_headers,
    )
    assert response.status_code == 404
