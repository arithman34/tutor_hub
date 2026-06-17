async def _create_subject(client, headers):
    resp = await client.post(
        "/api/v1/subjects/",
        json={"name": "Mathematics"},
        headers=headers,
    )
    return resp.json()


async def test_enroll_student(client, tutor_headers, admin_headers, student):
    subject = await _create_subject(client, admin_headers)
    response = await client.post(
        "/api/v1/enrollments/",
        json={"student_id": student["id"], "subject_id": subject["id"]},
        headers=tutor_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["student_id"] == student["id"]
    assert data["subject_id"] == subject["id"]


async def test_get_student_enrollments(client, tutor_headers, admin_headers, student):
    subject = await _create_subject(client, admin_headers)
    await client.post(
        "/api/v1/enrollments/",
        json={"student_id": student["id"], "subject_id": subject["id"]},
        headers=tutor_headers,
    )
    response = await client.get(
        f"/api/v1/enrollments/students/{student['id']}",
        headers=tutor_headers,
    )
    assert response.status_code == 200
    assert len(response.json()) == 1


async def test_remove_enrollment(client, tutor_headers, admin_headers, student):
    subject = await _create_subject(client, admin_headers)
    await client.post(
        "/api/v1/enrollments/",
        json={"student_id": student["id"], "subject_id": subject["id"]},
        headers=tutor_headers,
    )
    response = await client.delete(
        f"/api/v1/enrollments/students/{student['id']}/subjects/{subject['id']}",
        headers=tutor_headers,
    )
    assert response.status_code == 204


async def test_enroll_student_not_found(client, tutor_headers, admin_headers):
    subject = await _create_subject(client, admin_headers)
    response = await client.post(
        "/api/v1/enrollments/",
        json={
            "student_id": "00000000-0000-0000-0000-000000000000",
            "subject_id": subject["id"],
        },
        headers=tutor_headers,
    )
    assert response.status_code == 404


async def test_remove_nonexistent_enrollment(client, tutor_headers, admin_headers, student):
    subject = await _create_subject(client, admin_headers)
    response = await client.delete(
        f"/api/v1/enrollments/students/{student['id']}/subjects/{subject['id']}",
        headers=tutor_headers,
    )
    assert response.status_code == 404


async def test_enrollments_requires_auth(client):
    response = await client.get("/api/v1/enrollments/students/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 401


async def test_get_enrollments_unowned_student(client, second_tutor_headers, student):
    # student belongs to tutor1; tutor2 cannot list their enrollments
    response = await client.get(
        f"/api/v1/enrollments/students/{student['id']}",
        headers=second_tutor_headers,
    )
    assert response.status_code == 404


async def test_remove_enrollment_unowned_student(client, admin_headers, tutor_headers, second_tutor_headers, student):
    subject = await _create_subject(client, admin_headers)
    await client.post(
        "/api/v1/enrollments/",
        json={"student_id": student["id"], "subject_id": subject["id"]},
        headers=tutor_headers,
    )
    # tutor2 cannot remove an enrollment for tutor1's student
    response = await client.delete(
        f"/api/v1/enrollments/students/{student['id']}/subjects/{subject['id']}",
        headers=second_tutor_headers,
    )
    assert response.status_code == 404


async def test_admin_can_enroll_any_student(client, admin_headers, student):
    subject = await _create_subject(client, admin_headers)
    response = await client.post(
        "/api/v1/enrollments/",
        json={"student_id": student["id"], "subject_id": subject["id"]},
        headers=admin_headers,
    )
    assert response.status_code == 201


async def test_admin_can_list_enrollments_for_any_student(client, admin_headers, student):
    subject = await _create_subject(client, admin_headers)
    await client.post(
        "/api/v1/enrollments/",
        json={"student_id": student["id"], "subject_id": subject["id"]},
        headers=admin_headers,
    )
    response = await client.get(
        f"/api/v1/enrollments/students/{student['id']}",
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert len(response.json()) == 1
