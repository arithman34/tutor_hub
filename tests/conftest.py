import asyncio
import os
import uuid

from dotenv import load_dotenv

load_dotenv(".env.test")

import asyncpg
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from sqlalchemy import text

from app.auth import create_access_token, hash_password
from app.core.database import Base, get_db
from app.main import app
from app.models.student import Student
from app.models.user import User, UserRole

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL is None:
    raise ValueError("DATABASE_URL environment variable is not set")

POSTGRES_USER = os.getenv("POSTGRES_USER")

if POSTGRES_USER is None:
    raise ValueError("POSTGRES_USER environment variable is not set")

POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")

if POSTGRES_PASSWORD is None:
    raise ValueError("POSTGRES_PASSWORD environment variable is not set")

engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
TestingAsyncSessionLocal = async_sessionmaker(engine, autocommit=False, autoflush=False, expire_on_commit=False)


@pytest.fixture(scope="session", autouse=True)
def create_test_database():
    async def _create():
        conn = await asyncpg.connect(
            host="localhost",
            port=5432,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            database="postgres",
        )
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname='tutor_hub_test'")
        if not exists:
            await conn.execute("CREATE DATABASE tutor_hub_test")
        await conn.close()

    asyncio.run(_create())


@pytest.fixture(scope="session", autouse=True)
def create_tables(create_test_database):
    async def _create():
        async with engine.begin() as conn:
            await conn.execute(text("DROP SCHEMA public CASCADE"))
            await conn.execute(text("CREATE SCHEMA public"))
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_create())


@pytest_asyncio.fixture(autouse=True)
async def clean_tables():
    yield
    async with engine.begin() as conn:
        table_names = ", ".join(t.name for t in Base.metadata.sorted_tables)
        await conn.execute(text(f"TRUNCATE {table_names} RESTART IDENTITY CASCADE"))


@pytest_asyncio.fixture()
async def db():
    async with TestingAsyncSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture()
async def client(db):
    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture()
async def admin_user(db):
    user = User(
        email="admin@example.com",
        hashed_password=hash_password("adminpassword"),
        first_name="Admin",
        last_name="User",
        role=UserRole.admin,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture()
async def admin_headers(admin_user):
    token = create_access_token({"sub": admin_user.email})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture()
async def tutor_user(db):
    user = User(
        email="tutor@example.com",
        hashed_password=hash_password("tutorpassword"),
        first_name="John",
        last_name="Doe",
        role=UserRole.tutor,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return {"id": str(user.id), "email": user.email, "first_name": user.first_name,
            "last_name": user.last_name, "role": user.role.value, "is_active": user.is_active}


@pytest_asyncio.fixture()
async def tutor_user_obj(db):
    """Returns the ORM User object (for fixtures that need .id attribute)."""
    user = User(
        email="tutor@example.com",
        hashed_password=hash_password("tutorpassword"),
        first_name="John",
        last_name="Doe",
        role=UserRole.tutor,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture()
async def tutor_headers(tutor_user):
    token = create_access_token({"sub": tutor_user["email"]})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture()
async def second_tutor_user(db):
    user = User(
        email="tutor2@example.com",
        hashed_password=hash_password("tutor2password"),
        first_name="Jane",
        last_name="Smith",
        role=UserRole.tutor,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return {"id": str(user.id), "email": user.email, "first_name": user.first_name,
            "last_name": user.last_name, "role": user.role.value, "is_active": user.is_active}


@pytest_asyncio.fixture()
async def second_tutor_headers(second_tutor_user):
    token = create_access_token({"sub": second_tutor_user["email"]})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture()
async def student(db, tutor_user):
    s = Student(
        user_id=uuid.UUID(tutor_user["id"]),
        first_name="Jane",
        last_name="Smith",
        level="GCSE",
        hourly_rate=50.0,
    )
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return {"id": str(s.id), "first_name": s.first_name, "last_name": s.last_name,
            "level": s.level, "hourly_rate": s.hourly_rate, "user_id": str(s.user_id),
            "is_active": s.is_active}
