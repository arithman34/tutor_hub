async def _create_student(client, headers):
    resp = await client.post(
        "/api/v1/students/",
        json={"first_name": "John", "last_name": "Doe", "level": "GCSE", "hourly_rate": 50.0},
        headers=headers,
    )
    return resp.json()


async def _create_session(client, headers, student_id, **overrides):
    payload = {
        "student_id": student_id,
        "session_date": "2024-01-15T00:00:00Z",
        "session_start_time": "2024-01-15T09:00:00Z",
        "session_end_time": "2024-01-15T10:00:00Z",
        "planned_minutes": 60,
        **overrides,
    }
    resp = await client.post("/api/v1/sessions/", json=payload, headers=headers)
    return resp.json()


async def test_create_session(client, tutor_headers):
    student = await _create_student(client, tutor_headers)
    response = await client.post(
        "/api/v1/sessions/",
        json={
            "student_id": student["id"],
            "session_date": "2024-01-15T00:00:00Z",
            "session_start_time": "2024-01-15T09:00:00Z",
            "session_end_time": "2024-01-15T10:00:00Z",
            "planned_minutes": 60,
        },
        headers=tutor_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["planned_minutes"] == 60
    assert data["is_paid"] is False


async def test_get_sessions(client, tutor_headers):
    student = await _create_student(client, tutor_headers)
    await _create_session(client, tutor_headers, student["id"])
    response = await client.get("/api/v1/sessions/", headers=tutor_headers)
    assert response.status_code == 200
    assert len(response.json()) == 1


async def test_get_empty_sessions(client, tutor_headers):
    response = await client.get("/api/v1/sessions/", headers=tutor_headers)
    assert response.status_code == 200
    assert response.json() == []


async def test_get_session_by_id(client, tutor_headers):
    student = await _create_student(client, tutor_headers)
    session = await _create_session(client, tutor_headers, student["id"])
    response = await client.get(f"/api/v1/sessions/{session['id']}", headers=tutor_headers)
    assert response.status_code == 200
    assert response.json()["id"] == session["id"]


async def test_get_nonexistent_session(client, tutor_headers):
    response = await client.get(
        "/api/v1/sessions/00000000-0000-0000-0000-000000000000",
        headers=tutor_headers,
    )
    assert response.status_code == 404


async def test_update_session(client, tutor_headers):
    student = await _create_student(client, tutor_headers)
    session = await _create_session(client, tutor_headers, student["id"])
    response = await client.patch(
        f"/api/v1/sessions/{session['id']}",
        json={"actual_minutes": 55, "is_paid": True},
        headers=tutor_headers,
    )
    assert response.status_code == 200
    assert response.json()["actual_minutes"] == 55
    assert response.json()["is_paid"] is True


async def test_delete_session(client, tutor_headers):
    student = await _create_student(client, tutor_headers)
    session = await _create_session(client, tutor_headers, student["id"])
    response = await client.delete(f"/api/v1/sessions/{session['id']}", headers=tutor_headers)
    assert response.status_code == 204


async def test_get_sessions_requires_auth(client):
    response = await client.get("/api/v1/sessions/")
    assert response.status_code == 401


async def test_cannot_access_other_tutors_session(client, admin_headers, tutor_headers):
    student = await _create_student(client, tutor_headers)
    session = await _create_session(client, tutor_headers, student["id"])

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

    response = await client.get(f"/api/v1/sessions/{session['id']}", headers=headers2)
    assert response.status_code == 404


async def test_update_nonexistent_session(client, tutor_headers):
    response = await client.patch(
        "/api/v1/sessions/00000000-0000-0000-0000-000000000000",
        json={"actual_minutes": 55},
        headers=tutor_headers,
    )
    assert response.status_code == 404


async def test_delete_nonexistent_session(client, tutor_headers):
    response = await client.delete(
        "/api/v1/sessions/00000000-0000-0000-0000-000000000000",
        headers=tutor_headers,
    )
    assert response.status_code == 404
