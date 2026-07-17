async def test_login_success(client, admin_user):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "adminpassword"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


async def test_login_wrong_password(client, admin_user):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401


async def test_login_unknown_email(client):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "adminpassword"},
    )
    assert response.status_code == 401


async def test_login_invalid_email_format(client):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "not-an-email", "password": "adminpassword"},
    )
    assert response.status_code == 422


async def test_protected_route_no_token(client):
    response = await client.get("/api/v1/students/")
    assert response.status_code == 401


async def test_protected_route_invalid_token(client):
    response = await client.get(
        "/api/v1/students/",
        headers={"Authorization": "Bearer invalidtoken"},
    )
    assert response.status_code == 401


async def test_hash_and_verify_password():
    from app.auth import hash_password, verify_password

    hashed = hash_password("mysecretpassword")
    assert hashed != "mysecretpassword"
    assert verify_password("mysecretpassword", hashed) is True
    assert verify_password("wrongpassword", hashed) is False


async def test_create_access_token():
    from app.auth import create_access_token

    token = create_access_token({"sub": "test@example.com"})
    assert isinstance(token, str)
    assert len(token) > 0


async def test_login_deactivated_account(client, admin_headers, tutor_user):
    user_id = tutor_user["id"]
    await client.patch(f"/api/v1/users/{user_id}/deactivate", headers=admin_headers)
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "tutor@example.com", "password": "tutorpassword"},
    )
    assert response.status_code == 403


async def test_protected_route_token_no_sub(client):
    from app.auth import create_access_token

    token = create_access_token({"not_sub": "test@example.com"})
    response = await client.get(
        "/api/v1/me/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401


async def test_protected_route_deleted_user(client):
    from app.auth import create_access_token

    token = create_access_token({"sub": "ghost@example.com"})
    response = await client.get(
        "/api/v1/me/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401


async def test_refresh_token_success(client, admin_user):
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "adminpassword"},
    )
    refresh_token = login.json()["refresh_token"]

    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["refresh_token"] != refresh_token


async def test_refresh_token_invalid(client):
    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": "notavalidtoken"})
    assert response.status_code == 401


async def test_refresh_token_rotation_revokes_old(client, admin_user):
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "adminpassword"},
    )
    old_token = login.json()["refresh_token"]

    await client.post("/api/v1/auth/refresh", json={"refresh_token": old_token})

    # Using the old token a second time should fail
    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_token})
    assert response.status_code == 401


async def test_logout_revokes_refresh_token(client, admin_user):
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "adminpassword"},
    )
    refresh_token = login.json()["refresh_token"]

    logout = await client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})
    assert logout.status_code == 204

    # Token should be revoked now
    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 401
