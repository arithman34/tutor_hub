import asyncio
import json
import logging
from datetime import datetime, timezone

import boto3
import resend
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.models.user import User, UserRole
from app.services import admin as admin_service
from app.worker import celery_app

logger = logging.getLogger(__name__)

_TABLES = ("users", "payees", "students", "sessions", "payments")


async def _fetch_export() -> tuple[str | None, dict]:
    engine = create_async_engine(settings.database_url)
    try:
        async with AsyncSession(engine) as db:
            admin = (
                await db.execute(
                    select(User).where(User.role.in_([UserRole.admin, UserRole.admin_tutor])).limit(1)
                )
            ).scalar_one_or_none()
            if not admin:
                return None, {}
            return admin.email, await admin_service.export_data(db)
    finally:
        await engine.dispose()


def _notify(to: str, subject: str, body: str) -> None:
    resend.api_key = settings.resend_api_key
    resend.Emails.send({
        "from": settings.from_email,
        "to": [to],
        "subject": subject,
        "text": body,
    })


@celery_app.task(name="app.tasks.exports.send_weekly_export")
def send_weekly_export() -> None:
    if not settings.backup_bucket:
        logger.warning("BACKUP_BUCKET is not configured; skipping weekly export")
        return

    admin_email, data = asyncio.run(_fetch_export())
    if not admin_email:
        return

    now = datetime.now(timezone.utc)
    payload = json.dumps(data, indent=2).encode()
    key = f"exports/{now:%Y/%m/%d}/tutorhub_export_{now:%Y%m%dT%H%M%SZ}.json"

    try:
        boto3.client("s3", region_name=settings.aws_region).put_object(
            Bucket=settings.backup_bucket,
            Key=key,
            Body=payload,
            ContentType="application/json",
            ServerSideEncryption="AES256",
        )
    except Exception as exc:
        # A backup that quietly stops working is worse than no backup, so the
        # admin hears about the failure rather than just CloudWatch.
        logger.exception("Weekly export upload failed")
        _notify(
            admin_email,
            "TutorHub: weekly backup FAILED",
            f"This week's data export could not be uploaded to S3.\n\nError: {exc}\n\n"
            "Please download a manual export from the Data page in TutorHub.\n",
        )
        return

    counts = ", ".join(f"{len(data.get(t, []))} {t}" for t in _TABLES)
    _notify(
        admin_email,
        f"TutorHub: weekly backup complete ({now:%d %b %Y})",
        "This week's data export has been backed up.\n\n"
        f"Bucket: {settings.backup_bucket}\n"
        f"Key: {key}\n"
        f"Size: {len(payload) / 1024:.1f} KB\n"
        f"Contents: {counts}.\n",
    )
