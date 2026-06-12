async def test_create_subject_as_admin(client, admin_headers):
    response = await client.post(
        "/api/v1/subjects/",
        json={"name": "Mathematics"},
        headers=admin_headers,
    )
    assert response.status_code == 201
    assert response.json()["name"] == "Mathematics"


async def test_create_subject_as_tutor_forbidden(client, tutor_headers):
    response = await client.post(
        "/api/v1/subjects/",
        json={"name": "Mathematics"},
        headers=tutor_headers,
    )
    assert response.status_code == 403


async def test_get_subjects(client, tutor_headers, admin_headers):
    await client.post("/api/v1/subjects/", json={"name": "Mathematics"}, headers=admin_headers)
    await client.post("/api/v1/subjects/", json={"name": "English"}, headers=admin_headers)
    response = await client.get("/api/v1/subjects/", headers=tutor_headers)
    assert response.status_code == 200
    assert len(response.json()) == 2


async def test_get_empty_subjects(client, tutor_headers):
    response = await client.get("/api/v1/subjects/", headers=tutor_headers)
    assert response.status_code == 200
    assert response.json() == []


async def test_delete_subject_as_admin(client, admin_headers):
    create_resp = await client.post(
        "/api/v1/subjects/", json={"name": "Mathematics"}, headers=admin_headers
    )
    subject_id = create_resp.json()["id"]
    response = await client.delete(f"/api/v1/subjects/{subject_id}", headers=admin_headers)
    assert response.status_code == 204


async def test_delete_subject_as_tutor_forbidden(client, admin_headers, tutor_headers):
    create_resp = await client.post(
        "/api/v1/subjects/", json={"name": "Mathematics"}, headers=admin_headers
    )
    subject_id = create_resp.json()["id"]
    response = await client.delete(f"/api/v1/subjects/{subject_id}", headers=tutor_headers)
    assert response.status_code == 403


async def test_delete_nonexistent_subject(client, admin_headers):
    response = await client.delete(
        "/api/v1/subjects/00000000-0000-0000-0000-000000000000",
        headers=admin_headers,
    )
    assert response.status_code == 404


async def test_get_subjects_requires_auth(client):
    response = await client.get("/api/v1/subjects/")
    assert response.status_code == 401
