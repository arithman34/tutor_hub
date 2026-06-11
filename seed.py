import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth import hash_password
from app.core.config import settings
from app.models import User

ADMIN_EMAIL = "admin@tutorhub.com"
ADMIN_PASSWORD = "admin"
ADMIN_FIRST_NAME = "admin"
ADMIN_LAST_NAME = "admin"


async def seed():
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        result = await db.execute(select(User).where(User.email == ADMIN_EMAIL))
        existing = result.scalar_one_or_none()

        if existing:
            print(f"Admin already exists: {ADMIN_EMAIL}")
            return

        admin = User(
            email=ADMIN_EMAIL,
            hashed_password=hash_password(ADMIN_PASSWORD),
            first_name=ADMIN_FIRST_NAME,
            last_name=ADMIN_LAST_NAME,
            role="admin",
            is_active=True,
        )
        db.add(admin)
        await db.commit()

        print("Admin created successfully.")
        print(f"  Email:    {ADMIN_EMAIL}")
        print(f"  Password: {ADMIN_PASSWORD}")
        print("  ** Change this password immediately after first login **")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
