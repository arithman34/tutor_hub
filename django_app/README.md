# TutorHub — Django backend (production)

This is the Django + DRF rewrite of the FastAPI app that used to live at
`app/` at the repo root. It's now the live production backend — cut over
from FastAPI, including a full data migration of the real business's
database. `app/` is kept in the repo for reference only; nothing builds,
tests, or deploys it anymore.

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
- `assistant` — TutorHub AI. `tools.py` holds five read-only, user-scoped
  query tools plus their JSON-schema specs; `agent.py` runs the tool-calling
  loop (5 rounds, 45s budget, last 10 turns of history); `llm.py` is the only
  module that knows the provider (OpenAI); `quota.py` enforces each
  account's daily question allowance (`User.assistant_daily_limit`, blank =
  unlimited) with the `AssistantUsage` model. Tested with a fake model client.
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

The frontend is the React app in `spa/` (see "React app" below), served at
`/app/`. Django is the DRF API behind it, plus a small `web` app:

- `/` and `/privacy`: the public homepage and privacy policy, which Google's
  OAuth consent screen links to, so they work without signing in. They're
  Jinja2 templates (`templates/`, carried over from the FastAPI app). A
  signed-in visitor to `/` goes straight to `/app/`.
- `/calendar/callback`: the OAuth redirect URI registered with Google. It's
  `calendar_integration`'s callback (also at `/api/v1/calendar/callback`)
  and sends the browser on to `/app/connections`.
- Redirects from the old server-rendered pages' URLs (`/dashboard`,
  `/students/<id>`, `/calendar/create`, ...) to the same page under `/app/`,
  so bookmarks keep working.
- Management commands: `export_to_s3` and `import_legacy_export`.

Each app ships its tests alongside it (`tests.py`) rather than as a
follow-up. Run them as you go, not just before a PR.

## Local setup

```bash
cd django_app
pip install -r requirements.txt
npm install
npm run build
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### Public pages' CSS

The homepage and privacy policy are styled with Tailwind CSS v4, compiled
ahead of time by the Tailwind CLI (no CDN). `frontend/tailwind.css` is the
input; Tailwind scans `templates/` and emits only the classes they use, into
`static/css/app.css` (gitignored). The Docker image builds it in a Node
stage, and `collectstatic` gives it a content-hashed name that WhiteNoise
serves with a long cache lifetime.

While editing those templates, run `npm run dev` alongside `runserver` to
rebuild the CSS on every change.

### React app (`spa/`)

Vite + React + TypeScript, with React Router, TanStack Query and Tailwind v4.
Django serves it at `/app/`: `config/spa.py` returns the built `index.html`
for every `/app/*` URL, and the bundles are static files under
`/static/spa/` (cached forever, since Vite hashes their names).

```bash
cd spa
npm install
npm run dev        # http://localhost:5173/app/ with hot reload; runserver must be running
```

The dev server proxies everything except the app itself to Django
(`DJANGO_ORIGIN`, default `http://localhost:8000`), so the API, the public
pages and the login cookies all behave as in production.

- `npm test` / `npm run test:watch`: Vitest + Testing Library, with the API
  faked by MSW (`src/test/server.ts`).
- `npm run lint`, `npm run typecheck`.
- `npm run build`: production build into `static/spa/` (gitignored). The
  Docker image does this in its Node stage. Login and the dashboard are in
  the main bundle; every other page is its own chunk, loaded on first visit
  (`src/App.tsx`).

**API types.** `src/api/schema.d.ts` is generated from Django's OpenAPI
schema, so every `api.GET/POST(...)` call is type-checked against the real
endpoints. After changing an API endpoint, regenerate and commit both files:

```bash
python manage.py spectacular --file spa/openapi.yaml   # from django_app/
npm run gen:api                                        # from spa/
```

CI fails if either is out of date.

**Auth.** The app logs in with `POST /api/v1/auth/cookie/login`, which sets
httponly JWT cookies (`access_token`/`refresh_token`), so JavaScript never
sees a token. `src/api/client.ts` adds the CSRF header to unsafe requests
and quietly refreshes an expired access token once before giving up.

Reads config from a `.env` file in this directory (same variables as the
root FastAPI app's `POSTGRES_*` settings, plus `DJANGO_SECRET_KEY`,
`DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`).

No standalone Postgres handy? `docker run -d -e POSTGRES_USER=postgres -e
POSTGRES_PASSWORD=postgres -e POSTGRES_DB=tutorhub_dev -p 127.0.0.1:5432:5432
postgres:17` gives you one; point `.env`'s `POSTGRES_*` vars at it.

The `/setup` first-run page (create the first admin when the `users` table
is empty) is ported too — visit it once, or use
`python manage.py createsuperuser` / the Django admin instead.

## Auth endpoints

Full, interactive API docs are at `/api/v1/docs` (sign in first).

For API clients (tokens in the response body, sent back as `Authorization: Bearer`):

- `POST /api/v1/auth/login` — `{"email": ..., "password": ...}` → access +
  refresh token pair.
- `POST /api/v1/auth/refresh` — `{"refresh": ...}` → new access token
  (rotates/blacklists the old refresh token).
- `POST /api/v1/auth/logout` — `{"refresh": ...}` → blacklists the token.

For the browser app (tokens in httponly cookies; unsafe requests need the
`X-CSRFToken` header):

- `GET /api/v1/auth/csrf` → sets and returns the CSRF token.
- `POST /api/v1/auth/cookie/login`, `/cookie/refresh`, `/cookie/logout`.
- `GET`/`PATCH /api/v1/auth/me`, `POST /api/v1/auth/password`.

## Running tests

```bash
python manage.py test
```

Test runs automatically use an in-memory SQLite database (see
`RUNNING_TESTS` in `config/settings.py`), so no local Postgres is needed.
