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


async def test_create_student(client, admin_headers):
    response = await client.post(
        "/api/v1/students/",
        json={"first_name": "John", "last_name": "Doe", "level": "GCSE", "hourly_rate": 50.0},
        headers=admin_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["first_name"] == "John"
    assert data["last_name"] == "Doe"
    assert data["level"] == "GCSE"
    assert data["hourly_rate"] == 50.0
    assert data["is_active"] is True


async def test_create_student_assigned_to_tutor(client, admin_headers, tutor_user):
    response = await client.post(
        "/api/v1/students/",
        json={"first_name": "Alice", "last_name": "Jones", "level": "A-Level", "hourly_rate": 60.0, "tutor_id": tutor_user["id"]},
        headers=admin_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["user_id"] == tutor_user["id"]


async def test_get_students(client, admin_headers):
    await _create_student(client, admin_headers)
    response = await client.get("/api/v1/students/", headers=admin_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) == 1


async def test_get_empty_students(client, admin_headers):
    response = await client.get("/api/v1/students/", headers=admin_headers)
    assert response.status_code == 200
    assert response.json() == []


async def test_get_student_by_id(client, admin_headers):
    student = await _create_student(client, admin_headers)
    response = await client.get(f"/api/v1/students/{student['id']}", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["id"] == student["id"]


async def test_get_nonexistent_student(client, tutor_headers):
    response = await client.get(
        "/api/v1/students/00000000-0000-0000-0000-000000000000",
        headers=tutor_headers,
    )
    assert response.status_code == 404


async def test_update_student(client, admin_headers):
    student = await _create_student(client, admin_headers)
    response = await client.patch(
        f"/api/v1/students/{student['id']}",
        json={"level": "A-Level", "hourly_rate": 60.0},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["level"] == "A-Level"
    assert response.json()["hourly_rate"] == 60.0


async def test_delete_student(client, admin_headers):
    student = await _create_student(client, admin_headers)
    response = await client.delete(f"/api/v1/students/{student['id']}", headers=admin_headers)
    assert response.status_code == 204


async def test_get_students_requires_auth(client):
    response = await client.get("/api/v1/students/")
    assert response.status_code == 401


async def test_cannot_access_other_tutors_student(client, admin_headers, tutor_user, second_tutor_headers):
    # admin creates a student assigned to tutor1
    resp = await client.post(
        "/api/v1/students/",
        json={"first_name": "Private", "last_name": "Student", "level": "GCSE", "hourly_rate": 50.0, "tutor_id": tutor_user["id"]},
        headers=admin_headers,
    )
    student = resp.json()
    # tutor2 cannot see tutor1's student — gets 404 (not 403, to not leak existence)
    response = await client.get(f"/api/v1/students/{student['id']}", headers=second_tutor_headers)
    assert response.status_code == 404


async def test_tutor_cannot_create_student(client, tutor_headers):
    response = await client.post(
        "/api/v1/students/",
        json={"first_name": "Bob", "last_name": "Jones", "level": "GCSE", "hourly_rate": 50.0},
        headers=tutor_headers,
    )
    assert response.status_code == 403


async def test_tutor_cannot_update_student(client, tutor_headers, student):
    response = await client.patch(
        f"/api/v1/students/{student['id']}",
        json={"level": "A-Level"},
        headers=tutor_headers,
    )
    assert response.status_code == 403


async def test_tutor_cannot_delete_student(client, tutor_headers, student):
    response = await client.delete(
        f"/api/v1/students/{student['id']}",
        headers=tutor_headers,
    )
    assert response.status_code == 403


async def test_tutor_cannot_toggle_active_student(client, tutor_headers, student):
    response = await client.post(
        f"/api/v1/students/{student['id']}/toggle-active",
        headers=tutor_headers,
    )
    assert response.status_code == 403


async def test_tutor_sees_only_own_students(client, admin_headers, tutor_user, tutor_headers):
    # student assigned to tutor
    await client.post(
        "/api/v1/students/",
        json={"first_name": "Mine", "last_name": "Student", "level": "GCSE", "hourly_rate": 50.0, "tutor_id": tutor_user["id"]},
        headers=admin_headers,
    )
    # student assigned to admin (no tutor_id)
    await client.post(
        "/api/v1/students/",
        json={"first_name": "Admin", "last_name": "Student", "level": "GCSE", "hourly_rate": 50.0},
        headers=admin_headers,
    )
    response = await client.get("/api/v1/students/", headers=tutor_headers)
    assert response.status_code == 200
    students = response.json()
    assert len(students) == 1
    assert students[0]["first_name"] == "Mine"


async def test_admin_sees_all_students(client, admin_headers, tutor_user):
    await client.post(
        "/api/v1/students/",
        json={"first_name": "First", "last_name": "Student", "level": "GCSE", "hourly_rate": 50.0, "tutor_id": tutor_user["id"]},
        headers=admin_headers,
    )
    await client.post(
        "/api/v1/students/",
        json={"first_name": "Second", "last_name": "Student", "level": "GCSE", "hourly_rate": 50.0},
        headers=admin_headers,
    )
    response = await client.get("/api/v1/students/", headers=admin_headers)
    assert response.status_code == 200
    assert len(response.json()) == 2


async def test_search_students(client, admin_headers, tutor_user):
    await client.post(
        "/api/v1/students/",
        json={"first_name": "Alice", "last_name": "Smith", "level": "GCSE", "hourly_rate": 50.0, "tutor_id": tutor_user["id"]},
        headers=admin_headers,
    )
    await client.post(
        "/api/v1/students/",
        json={"first_name": "Bob", "last_name": "Jones", "level": "GCSE", "hourly_rate": 50.0},
        headers=admin_headers,
    )
    response = await client.get("/api/v1/students/?q=alice", headers=admin_headers)
    assert response.status_code == 200
    students = response.json()
    assert len(students) == 1
    assert students[0]["first_name"] == "Alice"


async def test_tutor_can_access_own_student(client, tutor_headers, student):
    response = await client.get(f"/api/v1/students/{student['id']}", headers=tutor_headers)
    assert response.status_code == 200
    assert response.json()["id"] == student["id"]


async def test_update_nonexistent_student(client, admin_headers):
    response = await client.patch(
        "/api/v1/students/00000000-0000-0000-0000-000000000000",
        json={"level": "A-Level"},
        headers=admin_headers,
    )
    assert response.status_code == 404


async def test_delete_nonexistent_student(client, admin_headers):
    response = await client.delete(
        "/api/v1/students/00000000-0000-0000-0000-000000000000",
        headers=admin_headers,
    )
    assert response.status_code == 404


async def test_toggle_active(client, admin_headers):
    student = await _create_student(client, admin_headers)
    assert student["is_active"] is True
    response = await client.post(
        f"/api/v1/students/{student['id']}/toggle-active",
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False
