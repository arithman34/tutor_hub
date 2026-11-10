# TutorHub — Django rewrite (in progress)

This is the Django + DRF rewrite of the FastAPI app living in `app/` at the
repo root. It's being built incrementally, app by app; see the root
`CLAUDE.md`/conversation history for the full migration plan.

## Apps

- `accounts` — custom email-based `User` model, JWT auth (login/refresh/logout
  via `djangorestframework-simplejwt`), Django admin registration. Tested.
- `students` — `Student` model/viewset, admin-only create/update/delete/
  toggle-active, tutors scoped to their own students. Tested.
- `tutoring_sessions` — `Session` model/viewset (served at `/api/v1/sessions/`;
  app is named `tutoring_sessions` to avoid clashing with
  `django.contrib.sessions`), owner-or-admin access. Tested.
- `billing` — `Payee`/`Payment` models/viewsets (admin-only), `/payees/{id}/balance`
  endpoint (payments received minus billable session cost). `students.payee`
  is now a real `ForeignKey` into this app. Tested.
- `rag` — `Document`/`Chunk` models (`Chunk.embedding` via `pgvector.django.VectorField`),
  PDF ingestion (`pdfplumber` + OpenAI embeddings), and a `/query` endpoint
  doing cosine-distance retrieval + chat completion. Tutor-only. Tested —
  note the cosine-distance query tests require a real Postgres + pgvector
  backend and are skipped under the SQLite test database (see "Running
  tests" below).
- `calendar_integration` — `GoogleCalendarToken` model, OAuth connect/callback/
  disconnect, upcoming/one-off/recurring event endpoints against the
  "Tutoring" calendar. The connect/callback handshake is JWT-only (no Django
  session): `state` is a signed, short-lived token embedding the user id
  (`django.core.signing`), since the browser's redirect to Google and back
  can't carry an Authorization header. Tested (httpx calls mocked).
- `analytics` — admin dashboard trend data (`/trends`, `/filters`): new/taught/
  churned/roster student series, session counts/hours/no-shows, payment
  totals, bucketed by day/week/month with prior-period % change. Admin-only.
  Deliberately aggregates in Python rather than via Postgres `date_trunc`
  (the FastAPI version's approach) — see the module docstring in
  `analytics/services.py` for why. Tested.

All six planned apps are now scaffolded. What's left: delete `app/web` once
this API has frontend parity, and decide on a frontend (SPA, or keep a
server-rendered admin via Django templates for the dashboard).

Each app ships its tests alongside it (`tests.py`) rather than as a
follow-up — run them as you go, not just before a PR.

## Local setup

```bash
cd django_app
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Reads config from a `.env` file in this directory (same variables as the
root FastAPI app's `POSTGRES_*` settings, plus `DJANGO_SECRET_KEY`,
`DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`).

## Auth endpoints

- `POST /api/v1/auth/login` — `{"email": ..., "password": ...}` → access +
  refresh token pair.
- `POST /api/v1/auth/refresh` — `{"refresh": ...}` → new access token
  (rotates/blacklists the old refresh token).
- `POST /api/v1/auth/logout` — `{"refresh": ...}` → blacklists the token.

## Running tests

```bash
python manage.py test
```

Test runs automatically use an in-memory SQLite database (see
`RUNNING_TESTS` in `config/settings.py`), so no local Postgres is needed —
except for the two `rag` tests that exercise real cosine-distance
retrieval, which are skipped unless `connection.vendor == "postgresql"`
(they can't run against sqlite). To cover those too, temporarily remove
the `RUNNING_TESTS` branch in `config/settings.py` so tests run against a
real Postgres database with the `vector` extension available, then run
`python manage.py test rag`.
