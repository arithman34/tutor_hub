async def test_get_my_profile(client, tutor_headers, tutor_user):
    response = await client.get("/api/v1/me/", headers=tutor_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "tutor@example.com"
    assert data["first_name"] == "John"


async def test_get_my_profile_requires_auth(client):
    response = await client.get("/api/v1/me/")
    assert response.status_code == 401


async def test_update_my_profile(client, tutor_headers):
    response = await client.patch(
        "/api/v1/me/",
        json={"first_name": "Jane"},
        headers=tutor_headers,
    )
    assert response.status_code == 200
    assert response.json()["first_name"] == "Jane"


async def test_update_my_email(client, tutor_headers):
    response = await client.patch(
        "/api/v1/me/",
        json={"email": "newemail@example.com"},
        headers=tutor_headers,
    )
    assert response.status_code == 200
    assert response.json()["email"] == "newemail@example.com"


async def test_update_my_password(client, tutor_headers):
    response = await client.patch(
        "/api/v1/me/",
        json={"password": "newpassword123"},
        headers=tutor_headers,
    )
    assert response.status_code == 200

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": "tutor@example.com", "password": "newpassword123"},
    )
    assert login_response.status_code == 200


async def test_update_my_last_name(client, tutor_headers):
    response = await client.patch(
        "/api/v1/me/",
        json={"last_name": "Smith"},
        headers=tutor_headers,
    )
    assert response.status_code == 200
    assert response.json()["last_name"] == "Smith"
