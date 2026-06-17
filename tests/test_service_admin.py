from app.auth import hash_password
from app.models.user import User, UserRole
from app.services import admin as admin_service


async def test_export_data_has_correct_structure(db):
    data = await admin_service.export_data(db)
    assert "exported_at" in data
    assert data["version"] == "1"
    for key in ("users", "subjects", "payees", "students", "enrollments", "sessions", "payments"):
        assert key in data
        assert isinstance(data[key], list)


async def test_export_serialises_uuid_as_string_and_enum_as_value(db):
    user = User(
        email="tutor@test.com",
        hashed_password=hash_password("password"),
        first_name="Test",
        last_name="Tutor",
        role=UserRole.tutor,
        is_active=True,
    )
    db.add(user)
    await db.commit()

    data = await admin_service.export_data(db)
    row = data["users"][0]
    assert isinstance(row["id"], str)
    assert row["role"] == "tutor"
    assert row["email"] == "tutor@test.com"


async def test_import_data_round_trip(db):
    user = User(
        email="tutor@test.com",
        hashed_password=hash_password("password"),
        first_name="Test",
        last_name="Tutor",
        role=UserRole.tutor,
        is_active=True,
    )
    db.add(user)
    await db.commit()

    data = await admin_service.export_data(db)
    await admin_service.import_data(db, data)

    data2 = await admin_service.export_data(db)
    assert len(data2["users"]) == 1
    assert data2["users"][0]["email"] == "tutor@test.com"
    assert data2["users"][0]["id"] == data["users"][0]["id"]


async def test_import_empty_payload_clears_all_tables(db):
    user = User(
        email="tutor@test.com",
        hashed_password=hash_password("password"),
        first_name="Test",
        last_name="Tutor",
        role=UserRole.tutor,
        is_active=True,
    )
    db.add(user)
    await db.commit()

    await admin_service.import_data(db, {})

    data = await admin_service.export_data(db)
    assert data["users"] == []
