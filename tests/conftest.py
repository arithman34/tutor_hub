import asyncio
import os

from dotenv import load_dotenv

load_dotenv(".env.test")

import asyncpg
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.auth import hash_password
from app.core.database import Base, get_db
from app.main import app
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
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_create())


@pytest_asyncio.fixture(autouse=True)
async def clean_tables():
    yield
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())


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
async def admin_headers(client, admin_user):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "adminpassword"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture()
async def tutor_user(client, admin_headers):
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
    return response.json()


@pytest_asyncio.fixture()
async def tutor_headers(client, tutor_user):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "tutor@example.com", "password": "tutorpassword"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
