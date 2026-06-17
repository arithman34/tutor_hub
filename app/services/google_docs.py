import html as _html
import json

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.google_calendar_token import GoogleCalendarToken
from app.services.google_calendar import _get_valid_access_token

_DRIVE_UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"


async def _get_token(user_id, db: AsyncSession) -> str:
    result = await db.execute(select(GoogleCalendarToken).where(GoogleCalendarToken.user_id == user_id))
    token = result.scalar_one_or_none()
    if not token:
        raise ValueError("Google not connected — cannot update ILP.")
    return await _get_valid_access_token(token, db)


def _e(text) -> str:
    """HTML-escape a value; return empty string for None."""
    if text is None:
        return ""
    return _html.escape(str(text))


def _table(rows: list[tuple[str, str]]) -> str:
    """Two-column table: bold left label, plain right value."""
    style = "border-collapse:collapse;width:100%"
    td_l = "border:1px solid #000;padding:8px;font-weight:bold;width:35%"
    td_r = "border:1px solid #000;padding:8px"
    cells = "".join(f"<tr><td style='{td_l}'>{_e(label)}</td><td style='{td_r}'>{_e(value)}</td></tr>" for label, value in rows)
    return f"<table style='{style}'>{cells}</table>"


def _student_table(student) -> str:
    name = f"{student.first_name} {student.last_name}".strip()
    rows: list[tuple[str, str]] = [("Student Name", name)]
    if student.level:
        rows.append(("Level", student.level))
    if student.onedrive_shared_link:
        rows.append(("Shared Link", student.onedrive_shared_link))
    return _table(rows)


def _payee_table(payee) -> str:
    return _table(
        [
            ("Payee Name", f"{payee.first_name} {payee.last_name}"),
            ("Email", payee.email or ""),
            ("Phone", payee.phone_number or ""),
        ]
    )


def _session_block(session, number: int) -> str:
    date_str = session.session_date.strftime("%d/%m/%Y")
    start = session.session_start_time.strftime("%H:%M")
    end = session.session_end_time.strftime("%H:%M")
    heading = f"SESSION {number} - {date_str} ({start} - {end})"

    if session.is_no_show:
        rows = [("Status", "No Show")]
    else:
        rows = [
            ("Work Covered", session.work_covered or ""),
            ("Student Actions", session.student_actions or ""),
            ("Tutor Actions", session.tutor_actions or ""),
            ("Next Lesson", session.next_lesson_focus or ""),
            ("Topic Tags", session.topic_tags or ""),
        ]
    return f"<br><h3>{_e(heading)}</h3>{_table(rows)}"


def _build_html(student, payee, sessions: list) -> str:
    parts = [
        "<!DOCTYPE html><html><body>",
        "<h1>INDIVIDUAL LEARNING PLAN (ILP)</h1>",
        "<br>",
        "<h2>Student Info</h2>",
        _student_table(student),
    ]
    if payee:
        parts += ["<br>", "<h2>Payee Info</h2>", _payee_table(payee)]

    # Page break — sessions start on a new page
    parts.append('<p style="page-break-after:always"></p>')

    sorted_sessions = sorted(sessions, key=lambda s: s.session_date)
    for i, s in enumerate(sorted_sessions, 1):
        parts.append(_session_block(s, i))

    parts.append("</body></html>")
    return "\n".join(parts)


async def _drive_upload(
    client: httpx.AsyncClient,
    access_token: str,
    title: str,
    html_content: str,
    doc_id: str | None = None,
) -> str:
    """Create or fully replace a Google Doc via Drive multipart upload.

    Passing doc_id replaces the existing file content (keeps the same URL).
    Omitting doc_id creates a new file. Returns the document ID.
    """
    boundary = "ilp_boundary_x7k2"
    metadata = json.dumps(
        {
            "name": title,
            "mimeType": "application/vnd.google-apps.document",
        }
    )
    body = (
        f"--{boundary}\r\n"
        "Content-Type: application/json; charset=UTF-8\r\n\r\n"
        f"{metadata}\r\n"
        f"--{boundary}\r\n"
        "Content-Type: text/html; charset=UTF-8\r\n\r\n"
        f"{html_content}\r\n"
        f"--{boundary}--"
    ).encode("utf-8")

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": f"multipart/related; boundary={boundary}",
    }

    if doc_id:
        resp = await client.patch(
            f"{_DRIVE_UPLOAD}/{doc_id}?uploadType=multipart",
            content=body,
            headers=headers,
        )
        if resp.status_code == 404:
            # Doc was deleted — create a fresh one instead
            resp = await client.post(
                f"{_DRIVE_UPLOAD}?uploadType=multipart",
                content=body,
                headers=headers,
            )
    else:
        resp = await client.post(
            f"{_DRIVE_UPLOAD}?uploadType=multipart",
            content=body,
            headers=headers,
        )

    resp.raise_for_status()
    return resp.json()["id"]


async def create_ilp_document(user_id, student, payee, db: AsyncSession) -> str:
    """Create a new ILP Google Doc. Returns the document ID."""
    access_token = await _get_token(user_id, db)
    title = f"{student.first_name} {student.last_name} - ILP"
    html = _build_html(student, payee, [])

    async with httpx.AsyncClient(timeout=30.0) as client:
        return await _drive_upload(client, access_token, title, html)


async def rebuild_ilp(user_id, student, payee, sessions: list, db: AsyncSession) -> str:
    """Create a fresh ILP Google Doc with all sessions. Returns the document ID."""
    access_token = await _get_token(user_id, db)
    title = f"{student.first_name} {student.last_name} - ILP"
    html = _build_html(student, payee, sessions)

    async with httpx.AsyncClient(timeout=60.0) as client:
        return await _drive_upload(client, access_token, title, html)


async def update_ilp_document(user_id, doc_id: str, student, payee, sessions: list, db: AsyncSession) -> str:
    """Replace the content of an existing ILP Google Doc in-place.

    Returns the doc ID — normally unchanged, but a new ID is returned if the
    original document was deleted and had to be recreated.
    """
    access_token = await _get_token(user_id, db)
    title = f"{student.first_name} {student.last_name} - ILP"
    html = _build_html(student, payee, sessions)

    async with httpx.AsyncClient(timeout=60.0) as client:
        return await _drive_upload(client, access_token, title, html, doc_id=doc_id)
