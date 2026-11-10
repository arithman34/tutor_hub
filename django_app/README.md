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

All six planned apps are scaffolded, plus a frontend has started:

- `web` — server-rendered pages, reusing the FastAPI app's Jinja2 templates
  almost unchanged (Django's `django.template.backends.jinja2.Jinja2` backend
  — see `config/jinja2_env.py` and the second entry in `TEMPLATES`), rather
  than rewriting them in Django's own template language. Auth is
  cookie-based but reuses the *same* SimpleJWT tokens the API issues
  (`access_token`/`refresh_token` httponly cookies instead of an
  Authorization header) — see `web/auth.py`. Pages so far: `/login`,
  `/logout`, `/dashboard` (admin vs. tutor stats, `web/services.py`).
  Remaining pages (`students`, `sessions`, `payees`, `payments`, `documents`,
  `calendar`, `connections`, `profile`, `admin`, `analytics`, `setup`) are
  not ported yet — `app/web` stays the live daily-use app until this one has
  parity.
- `students` (web) — `/students` (list/search), `/students/new` + `POST
  /students` (admin-only create), `/students/<uuid>` detail with inline
  update/toggle-active/delete forms. Same permission rules as the DRF
  `StudentViewSet`.

Every POST form needs a `{{ csrf_token }}` hidden input — Django's test
`Client` doesn't enforce CSRF by default, so a template missing it can pass
every test while still 403ing for a real browser. Each page group's tests
include a `Client(enforce_csrf_checks=True)` regression test for this
(see `web/test_students.py:StudentFormsCsrfTests` for the pattern) — this
bit me once already (caught by the manual browser check, not the test
suite) and is worth repeating for every new page.

Each app ships its tests alongside it (`tests.py`) rather than as a
follow-up — run them as you go, not just before a PR.

The plan is to eventually move the frontend to a separate React + Tailwind
app once this is stable; Django stays as a pure DRF API at that point and
`web`/its templates get retired.

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

No standalone Postgres handy? `docker run -d -e POSTGRES_USER=postgres -e
POSTGRES_PASSWORD=postgres -e POSTGRES_DB=tutorhub_dev -p 127.0.0.1:5432:5432
pgvector/pgvector:pg17` gives you one with the `vector` extension image
already baked in; point `.env`'s `POSTGRES_*` vars at it.

The FastAPI app's `/setup` first-run page (create the first admin when the
`users` table is empty) isn't ported yet — create your first user with
`python manage.py createsuperuser` or the Django admin instead.

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
