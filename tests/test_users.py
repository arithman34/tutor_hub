async def test_create_user_as_admin(client, admin_headers):
    response = await client.post(
        "/api/v1/users/",
        json={
            "email": "tutor@example.com",
            "password": "tutorpassword",
            "first_name": "John",
            "last_name": "Doe",
            "role": "tutor",
        },
        headers=admin_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "tutor@example.com"
    assert data["role"] == "tutor"
    assert "hashed_password" not in data


async def test_create_user_as_tutor_forbidden(client, tutor_headers):
    response = await client.post(
        "/api/v1/users/",
        json={
            "email": "other@example.com",
            "password": "otherpassword",
            "first_name": "Jane",
            "last_name": "Smith",
            "role": "tutor",
        },
        headers=tutor_headers,
    )
    assert response.status_code == 403


async def test_create_duplicate_user(client, admin_headers, tutor_user):
    response = await client.post(
        "/api/v1/users/",
        json={
            "email": "tutor@example.com",
            "password": "tutorpassword",
            "first_name": "John",
            "last_name": "Doe",
            "role": "tutor",
        },
        headers=admin_headers,
    )
    assert response.status_code == 400


async def test_get_users_as_admin(client, admin_headers, tutor_user):
    response = await client.get("/api/v1/users/", headers=admin_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) >= 1


async def test_get_users_as_tutor_forbidden(client, tutor_headers):
    response = await client.get("/api/v1/users/", headers=tutor_headers)
    assert response.status_code == 403


async def test_get_user_by_id_as_admin(client, admin_headers, tutor_user):
    user_id = tutor_user["id"]
    response = await client.get(f"/api/v1/users/{user_id}", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["id"] == user_id


async def test_get_nonexistent_user(client, admin_headers):
    response = await client.get(
        "/api/v1/users/00000000-0000-0000-0000-000000000000",
        headers=admin_headers,
    )
    assert response.status_code == 404


async def test_deactivate_user(client, admin_headers, tutor_user):
    user_id = tutor_user["id"]
    response = await client.patch(f"/api/v1/users/{user_id}/deactivate", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["is_active"] is False


async def test_activate_user(client, admin_headers, tutor_user):
    user_id = tutor_user["id"]
    await client.patch(f"/api/v1/users/{user_id}/deactivate", headers=admin_headers)
    response = await client.patch(f"/api/v1/users/{user_id}/activate", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["is_active"] is True


async def test_deactivate_user_as_tutor_forbidden(client, tutor_headers, tutor_user):
    user_id = tutor_user["id"]
    response = await client.patch(f"/api/v1/users/{user_id}/deactivate", headers=tutor_headers)
    assert response.status_code == 403


async def test_activate_user_as_tutor_forbidden(client, tutor_headers, tutor_user):
    user_id = tutor_user["id"]
    await client.patch(f"/api/v1/users/{user_id}/deactivate", headers=tutor_headers)
    response = await client.patch(f"/api/v1/users/{user_id}/activate", headers=tutor_headers)
    assert response.status_code == 403


async def test_get_own_profile_as_tutor(client, tutor_headers, tutor_user):
    user_id = tutor_user["id"]
    response = await client.get(f"/api/v1/users/{user_id}", headers=tutor_headers)
    assert response.status_code == 200
    assert response.json()["id"] == user_id


async def test_get_other_users_profile_as_tutor_forbidden(client, tutor_headers, admin_headers):
    admin_resp = await client.get("/api/v1/users/", headers=admin_headers)
    admin_id = next(u["id"] for u in admin_resp.json() if u["role"] == "admin")
    response = await client.get(f"/api/v1/users/{admin_id}", headers=tutor_headers)
    assert response.status_code == 403


async def test_deactivate_nonexistent_user(client, admin_headers):
    response = await client.patch(
        "/api/v1/users/00000000-0000-0000-0000-000000000000/deactivate",
        headers=admin_headers,
    )
    assert response.status_code == 404


async def test_activate_nonexistent_user(client, admin_headers):
    response = await client.patch(
        "/api/v1/users/00000000-0000-0000-0000-000000000000/activate",
        headers=admin_headers,
    )
    assert response.status_code == 404


async def test_create_second_admin_returns_400(client, admin_headers):
    response = await client.post(
        "/api/v1/users/",
        json={
            "email": "admin2@example.com",
            "password": "adminpassword",
            "first_name": "Second",
            "last_name": "Admin",
            "role": "admin",
        },
        headers=admin_headers,
    )
    assert response.status_code == 400
