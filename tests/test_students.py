async def _create_student(client, headers, **overrides):
    payload = {
        "first_name": "John",
        "last_name": "Doe",
        "level": "GCSE",
        "hourly_rate": 50.0,
        **overrides,
    }
    resp = await client.post("/api/v1/students/", json=payload, headers=headers)
    return resp.json()


async def test_create_student(client, tutor_headers):
    response = await client.post(
        "/api/v1/students/",
        json={"first_name": "John", "last_name": "Doe", "level": "GCSE", "hourly_rate": 50.0},
        headers=tutor_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["first_name"] == "John"
    assert data["last_name"] == "Doe"
    assert data["level"] == "GCSE"
    assert data["hourly_rate"] == 50.0
    assert data["is_active"] is True


async def test_get_students(client, tutor_headers):
    await _create_student(client, tutor_headers)
    response = await client.get("/api/v1/students/", headers=tutor_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) == 1


async def test_get_empty_students(client, tutor_headers):
    response = await client.get("/api/v1/students/", headers=tutor_headers)
    assert response.status_code == 200
    assert response.json() == []


async def test_get_student_by_id(client, tutor_headers):
    student = await _create_student(client, tutor_headers)
    response = await client.get(f"/api/v1/students/{student['id']}", headers=tutor_headers)
    assert response.status_code == 200
    assert response.json()["id"] == student["id"]


async def test_get_nonexistent_student(client, tutor_headers):
    response = await client.get(
        "/api/v1/students/00000000-0000-0000-0000-000000000000",
        headers=tutor_headers,
    )
    assert response.status_code == 404


async def test_update_student(client, tutor_headers):
    student = await _create_student(client, tutor_headers)
    response = await client.patch(
        f"/api/v1/students/{student['id']}",
        json={"level": "A-Level", "hourly_rate": 60.0},
        headers=tutor_headers,
    )
    assert response.status_code == 200
    assert response.json()["level"] == "A-Level"
    assert response.json()["hourly_rate"] == 60.0


async def test_delete_student(client, tutor_headers):
    student = await _create_student(client, tutor_headers)
    response = await client.delete(f"/api/v1/students/{student['id']}", headers=tutor_headers)
    assert response.status_code == 204


async def test_get_students_requires_auth(client):
    response = await client.get("/api/v1/students/")
    assert response.status_code == 401


async def test_cannot_access_other_tutors_student(client, admin_headers, tutor_headers):
    student = await _create_student(client, tutor_headers)

    second_tutor_resp = await client.post(
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

    response = await client.get(f"/api/v1/students/{student['id']}", headers=headers2)
    assert response.status_code == 404


async def test_update_nonexistent_student(client, tutor_headers):
    response = await client.patch(
        "/api/v1/students/00000000-0000-0000-0000-000000000000",
        json={"level": "A-Level"},
        headers=tutor_headers,
    )
    assert response.status_code == 404


async def test_delete_nonexistent_student(client, tutor_headers):
    response = await client.delete(
        "/api/v1/students/00000000-0000-0000-0000-000000000000",
        headers=tutor_headers,
    )
    assert response.status_code == 404
