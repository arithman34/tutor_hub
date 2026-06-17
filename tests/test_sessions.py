async def _create_session(client, headers, student_id, **overrides):
    payload = {
        "student_id": student_id,
        "session_date": "2024-01-15T00:00:00Z",
        "session_start_time": "2024-01-15T09:00:00Z",
        "session_end_time": "2024-01-15T10:00:00Z",
        **overrides,
    }
    resp = await client.post("/api/v1/sessions/", json=payload, headers=headers)
    return resp.json()


async def test_create_session(client, tutor_headers, student):
    response = await client.post(
        "/api/v1/sessions/",
        json={
            "student_id": student["id"],
            "session_date": "2024-01-15T00:00:00Z",
            "session_start_time": "2024-01-15T09:00:00Z",
            "session_end_time": "2024-01-15T10:00:00Z",
        },
        headers=tutor_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["minutes"] == 60
    assert data["is_no_show"] is False


async def test_create_no_show_session(client, tutor_headers, student):
    response = await client.post(
        "/api/v1/sessions/",
        json={
            "student_id": student["id"],
            "session_date": "2024-01-15T00:00:00Z",
            "session_start_time": "2024-01-15T09:00:00Z",
            "session_end_time": "2024-01-15T10:00:00Z",
            "is_no_show": True,
        },
        headers=tutor_headers,
    )
    assert response.status_code == 201
    assert response.json()["is_no_show"] is True


async def test_no_show_nulls_content_fields(client, tutor_headers, student):
    response = await client.post(
        "/api/v1/sessions/",
        json={
            "student_id": student["id"],
            "session_date": "2024-01-15T00:00:00Z",
            "session_start_time": "2024-01-15T09:00:00Z",
            "session_end_time": "2024-01-15T10:00:00Z",
            "is_no_show": True,
            "work_covered": "Should be cleared",
            "student_actions": "Should also be cleared",
        },
        headers=tutor_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["is_no_show"] is True
    assert data["work_covered"] is None
    assert data["student_actions"] is None


async def test_get_sessions(client, tutor_headers, student):
    await _create_session(client, tutor_headers, student["id"])
    response = await client.get("/api/v1/sessions/", headers=tutor_headers)
    assert response.status_code == 200
    assert len(response.json()) == 1


async def test_get_empty_sessions(client, tutor_headers):
    response = await client.get("/api/v1/sessions/", headers=tutor_headers)
    assert response.status_code == 200
    assert response.json() == []


async def test_get_session_by_id(client, tutor_headers, student):
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


async def test_update_session(client, tutor_headers, student):
    session = await _create_session(client, tutor_headers, student["id"])
    response = await client.patch(
        f"/api/v1/sessions/{session['id']}",
        json={"work_covered": "Quadratic equations", "is_no_show": False},
        headers=tutor_headers,
    )
    assert response.status_code == 200
    assert response.json()["work_covered"] == "Quadratic equations"
    assert response.json()["is_no_show"] is False


async def test_delete_session(client, tutor_headers, student):
    session = await _create_session(client, tutor_headers, student["id"])
    response = await client.delete(f"/api/v1/sessions/{session['id']}", headers=tutor_headers)
    assert response.status_code == 204


async def test_get_sessions_requires_auth(client):
    response = await client.get("/api/v1/sessions/")
    assert response.status_code == 401


async def test_cannot_access_other_tutors_session(client, tutor_headers, second_tutor_headers, student):
    session = await _create_session(client, tutor_headers, student["id"])
    # tutor2 cannot see tutor1's session — gets 404
    response = await client.get(f"/api/v1/sessions/{session['id']}", headers=second_tutor_headers)
    assert response.status_code == 404


async def test_tutor_cannot_update_other_tutors_session(client, tutor_headers, second_tutor_headers, student):
    session = await _create_session(client, tutor_headers, student["id"])
    response = await client.patch(
        f"/api/v1/sessions/{session['id']}",
        json={"work_covered": "Unauthorised edit"},
        headers=second_tutor_headers,
    )
    assert response.status_code == 403


async def test_tutor_cannot_delete_other_tutors_session(client, tutor_headers, second_tutor_headers, student):
    session = await _create_session(client, tutor_headers, student["id"])
    response = await client.delete(f"/api/v1/sessions/{session['id']}", headers=second_tutor_headers)
    assert response.status_code == 403


async def test_tutor_sees_only_own_sessions(client, tutor_headers, second_tutor_headers, student):
    # tutor1 and tutor2 each log a session for the same student
    await _create_session(client, tutor_headers, student["id"])
    await _create_session(client, second_tutor_headers, student["id"])
    response = await client.get("/api/v1/sessions/", headers=tutor_headers)
    assert response.status_code == 200
    assert len(response.json()) == 1


async def test_admin_sees_all_sessions(client, admin_headers, tutor_headers, second_tutor_headers, student):
    await _create_session(client, tutor_headers, student["id"])
    await _create_session(client, second_tutor_headers, student["id"])
    response = await client.get("/api/v1/sessions/", headers=admin_headers)
    assert response.status_code == 200
    assert len(response.json()) == 2


async def test_admin_can_access_any_session(client, admin_headers, tutor_headers, student):
    session = await _create_session(client, tutor_headers, student["id"])
    response = await client.get(f"/api/v1/sessions/{session['id']}", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["id"] == session["id"]


async def test_update_nonexistent_session(client, tutor_headers):
    response = await client.patch(
        "/api/v1/sessions/00000000-0000-0000-0000-000000000000",
        json={"work_covered": "Quadratic equations"},
        headers=tutor_headers,
    )
    assert response.status_code == 404


async def test_delete_nonexistent_session(client, tutor_headers):
    response = await client.delete(
        "/api/v1/sessions/00000000-0000-0000-0000-000000000000",
        headers=tutor_headers,
    )
    assert response.status_code == 404
