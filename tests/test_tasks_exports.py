import asyncio
import json
import re

import pytest

from app.tasks import exports as exports_task

BUCKET = "tutorhub-backups-test"


class _FakeS3:
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.puts: list[dict] = []

    def put_object(self, **kwargs):
        if self.error:
            raise self.error
        self.puts.append(kwargs)
        return {}


@pytest.fixture()
def s3(monkeypatch):
    client = _FakeS3()
    monkeypatch.setattr(exports_task.settings, "backup_bucket", BUCKET)
    monkeypatch.setattr(exports_task.boto3, "client", lambda *a, **kw: client)
    return client


@pytest.fixture()
def sent(monkeypatch):
    captured: list[dict] = []
    monkeypatch.setattr(exports_task.resend.Emails, "send", lambda params: captured.append(params))
    return captured


async def _run_task() -> None:
    """The task calls asyncio.run(), so it needs a thread without a running loop."""
    await asyncio.to_thread(exports_task.send_weekly_export)


async def test_fetch_export_returns_none_when_no_admin(db):
    email, data = await exports_task._fetch_export()
    assert email is None
    assert data == {}


async def test_fetch_export_returns_admin_email_and_data(db, admin_user):
    email, data = await exports_task._fetch_export()
    assert email == "admin@example.com"
    assert data["version"] == "1"
    assert [u["email"] for u in data["users"]] == ["admin@example.com"]


async def test_skips_entirely_when_bucket_not_configured(db, admin_user, sent, monkeypatch):
    monkeypatch.setattr(exports_task.settings, "backup_bucket", "")
    called = []
    monkeypatch.setattr(exports_task.boto3, "client", lambda *a, **kw: called.append(1))

    await _run_task()

    assert called == []
    assert sent == []


async def test_does_nothing_without_admin(db, s3, sent):
    await _run_task()
    assert s3.puts == []
    assert sent == []


async def test_uploads_export_to_s3(db, admin_user, s3, sent):
    await _run_task()

    assert len(s3.puts) == 1
    put = s3.puts[0]
    assert put["Bucket"] == BUCKET
    assert put["ContentType"] == "application/json"
    assert put["ServerSideEncryption"] == "AES256"
    assert re.fullmatch(
        r"exports/\d{4}/\d{2}/\d{2}/tutorhub_export_\d{8}T\d{6}Z\.json", put["Key"]
    )

    payload = json.loads(put["Body"])
    assert payload["version"] == "1"
    for table in ("users", "payees", "students", "sessions", "payments"):
        assert table in payload
    assert [u["email"] for u in payload["users"]] == ["admin@example.com"]


async def test_success_email_reports_location_and_counts(db, admin_user, s3, sent):
    await _run_task()

    assert len(sent) == 1
    assert sent[0]["to"] == ["admin@example.com"]
    assert "backup complete" in sent[0]["subject"]
    body = sent[0]["text"]
    assert BUCKET in body
    assert s3.puts[0]["Key"] in body
    assert "1 users" in body
    assert "0 payments" in body


async def test_no_attachment_is_ever_sent(db, admin_user, s3, sent):
    await _run_task()
    assert "attachments" not in sent[0]


async def test_alerts_admin_when_upload_fails(db, admin_user, sent, monkeypatch):
    monkeypatch.setattr(exports_task.settings, "backup_bucket", BUCKET)
    monkeypatch.setattr(
        exports_task.boto3, "client", lambda *a, **kw: _FakeS3(error=RuntimeError("access denied"))
    )

    await _run_task()

    assert len(sent) == 1
    assert "FAILED" in sent[0]["subject"]
    assert "access denied" in sent[0]["text"]
    assert "attachments" not in sent[0]
