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

All six planned apps are scaffolded, plus a frontend has started:

- `web` — server-rendered pages, reusing the FastAPI app's Jinja2 templates
  almost unchanged (Django's `django.template.backends.jinja2.Jinja2` backend
  — see `config/jinja2_env.py` and the second entry in `TEMPLATES`), rather
  than rewriting them in Django's own template language. Auth is
  cookie-based but reuses the *same* SimpleJWT tokens the API issues
  (`access_token`/`refresh_token` httponly cookies instead of an
  Authorization header) — see `web/auth.py`. Pages: `/login`, `/logout`,
  `/dashboard` (admin vs. tutor stats, `web/services.py`), and every other
  page the FastAPI web app had — all ported and now the only one actually
  serving traffic; `app/web` is retired.
- `students` (web) — `/students` (list/search), `/students/new` + `POST
  /students` (admin-only create), `/students/<uuid>` detail with inline
  update/toggle-active/delete forms. Same permission rules as the DRF
  `StudentViewSet`.
- `sessions` (web) — `/sessions/new` + `POST /sessions` (manual entry or
  "paste Zoom AI summary" → `POST /sessions/zoom-parse`, OpenAI call in
  `web/ai.py`), `/sessions/<uuid>` detail with separate "Details"
  (date/time/no-show) and "Notes" forms, delete. `/sessions` itself now
  matches the original FastAPI app: admins get the simple logged-sessions
  list filtered to `calendar_event_id__isnull=False` (sessions that came
  from a calendar event), while tutors get the live Calendar-merged view
  (`sessions/google.html`) — their upcoming/past Google Calendar
  ("Tutoring" calendar) events merged with which ones are already logged,
  with search, status/period filters (persisted in `sessions_status`/
  `sessions_period` cookies), and pagination. Redirects to
  `/connections?error=not_connected` if the tutor has no
  `GoogleCalendarToken` row at all; a stale/expired token instead renders
  the page with an error banner and a "Reconnect" link, since Google
  errors (expired refresh token, deleted calendar) are expected steady-state,
  not exceptional.

  **Fixed a real bug while porting**: the original's session-update route
  binds all form fields (including the notes fields) with FastAPI
  `Form(default="")` regardless of which of the two `<form>`s on the detail
  page submitted — so editing just the date/time via the "Details" form
  (which has no notes inputs) silently blanked `work_covered` and the other
  notes fields to `None`. The Django port only touches a field when it's
  actually present in the POST body, so fixing a session's time no longer
  wipes its notes. Covered by
  `web/test_sessions.py:test_update_details_does_not_wipe_notes` and
  verified by hand in the browser.
- `payees` (web) — `/payees` (admin-only list/search, with balance shown
  per payee), `/payees/new` + `POST /payees` (create), `/payees/<uuid>`
  detail (balance banner, linked students, payment history) with an inline
  update form. Balance reuses `billing.views.payee_balance` (payments
  received minus billable session cost) rather than duplicating that
  calculation. Jinja2 doesn't auto-call zero-arg methods the way Django's
  own template language does, so templates iterating a related manager
  need an explicit `.all()`/`.count()` (e.g. `payee.students.all()`,
  `payee.students.count()`) rather than bare attribute access.
- `payments` (web) — `/payments` (admin-only list/search by payee name),
  `/payments/new` + `POST /payments` (create, with an optional
  `?payee_id=` prefill used by the "Add Payment" link on a payee's detail
  page). No update/delete UI, matching the original FastAPI app — only the
  DRF `PaymentViewSet` supports those.
- `assistant` (web) — `/assistant` (TutorHub AI chat), `POST
  /assistant/ask` (checks the daily allowance, then calls
  `assistant.agent.answer`) and `POST /assistant/reset` ("New chat").
  History lives in the Django session under a per-user key, so a shared
  browser never shows one account's chat to another.
- `connections` (web) — `/connections` shows Google Calendar connect/
  disconnect status (connected = the stored `GoogleCalendarToken` has a
  `refresh_token`; disconnect clears credentials but keeps the row, since
  `tutoring_calendar_id` is the only record of which calendar is ours), with
  flash/error messages for the OAuth outcomes.
- `calendar` (web) — `/calendar/create` (GET form / `POST` to create a
  one-off or weekly-recurring Google Calendar event for a student, title
  built as `"<First name> - Tuition"`), `/calendar/connect` (redirects to
  Google, sets a short-lived `gcal_state` cookie), `/calendar/callback`
  (verifies the cookie against Google's `state` param, then
  `calendar_integration.services.exchange_code`), `/calendar/disconnect`.
  Unlike the DRF API's OAuth endpoints (JWT-only, so they sign the `state`
  payload with `django.core.signing` instead), the web flow has real cookies
  available, so it mirrors the original FastAPI app's plain cookie-based
  state check rather than reusing the signed-state approach.
- `profile` (web) — `/profile` (own account details + account status),
  `POST /profile/update` (name/email/address, and — only for an admin or
  admin_tutor — their own `role`, matching the original FastAPI app's
  "role is managed by an administrator" UI for plain tutors),
  `POST /profile/password` (requires the current password via
  `user.check_password`).
- `setup` (web) — `/setup`, the first-run page: GET shows a plain
  "create your admin account" form (no sidebar, extends `base.html`
  directly like `login.html`), POST creates it. Both redirect to `/login`
  once the `users` table is non-empty, so the page is a no-op after the
  very first run and needs no auth of its own.
- `admin` (web) — `/admin/users` (admin-only list/create of tutors, toggle
  active, edit payout config via a modal, delete — only when the tutor has
  no linked students/sessions/payments/payees), `/admin/data` (full JSON
  export of every table via `/admin/data/export`, and a destructive
  wipe-and-replace `POST /admin/data/import`). Creating a tutor emails them
  a generated temporary password via Resend (`RESEND_API_KEY`/`FROM_EMAIL`
  settings) — a send failure is logged and swallowed, matching the
  original FastAPI app, since the account is still usable without the
  email. **Django's own admin site was moved from `/admin/` to
  `/django-admin/`** (see `config/urls.py`) — the FastAPI app's `/admin/*`
  web pages collide with it otherwise: `django.contrib.admin`'s URLconf
  claims the whole `/admin/` prefix and its catch-all view intercepts
  unmatched sub-paths with a login redirect before `web.urls` ever sees
  the request, so `/admin/users` 302'd to the Django admin login instead
  of reaching our view.
- `analytics` (web) — `/analytics` (admin-only dashboard shell: filter bar
  + empty chart containers) and `/analytics/data` (JSON endpoint the
  page's own Chart.js fetches on load/filter-change). Both reuse
  `analytics.services` directly — the same trend-bucketing, range
  resolution and filter-options logic the DRF `TrendsView`/
  `FilterOptionsView` already use — so there's no second implementation of
  that logic for the web layer.

Every POST form needs a `{{ csrf_token }}` hidden input — Django's test
`Client` doesn't enforce CSRF by default, so a template missing it can pass
every test while still 403ing for a real browser. Each page group's tests
include a `Client(enforce_csrf_checks=True)` regression test for this
(see `web/test_students.py:StudentFormsCsrfTests` for the pattern) — this
bit me once already (caught by the manual browser check, not the test
suite) and is worth repeating for every new page.

Each app ships its tests alongside it (`tests.py`) rather than as a
follow-up — run them as you go, not just before a PR.

The frontend is moving, page by page, to a React app in `spa/` served at
`/app/` (see "React app" below). Until a page is rebuilt there, the app's
sidebar links to its classic version here. Once every page has moved, Django
is a pure DRF API plus the public pages, and `web`/its templates are retired.

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

### Frontend assets

Pages are styled with Tailwind CSS v4, compiled ahead of time by the
Tailwind CLI (no CDN). `frontend/tailwind.css` is the input: it holds the
dark-mode variant, the shared `th-*` component classes and a few v3
compatibility defaults. Tailwind scans `templates/` and emits only the
classes they use, into `static/css/app.css`.

`npm run build` also copies Flowbite and Chart.js (pinned in
`package.json`) into `static/vendor/`, so all browser JS is self-hosted.
Both outputs are gitignored. The Docker image builds them in a Node stage,
and `collectstatic` gives them content-hashed names that WhiteNoise serves
with long cache lifetimes.

While editing templates, run `npm run dev` alongside `runserver` to rebuild
the CSS on every change. A class added to a template has no styles until
Tailwind rebuilds.

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
(`DJANGO_ORIGIN`, default `http://localhost:8000`), so the API, the classic
pages and the login cookies all behave as in production.

- `npm test` / `npm run test:watch`: Vitest + Testing Library, with the API
  faked by MSW (`src/test/server.ts`).
- `npm run lint`, `npm run typecheck`.
- `npm run build`: production build into `static/spa/` (gitignored). The
  Docker image does this in its Node stage.

**API types.** `src/api/schema.d.ts` is generated from Django's OpenAPI
schema, so every `api.GET/POST(...)` call is type-checked against the real
endpoints. After changing an API endpoint, regenerate and commit both files:

```bash
python manage.py spectacular --file spa/openapi.yaml   # from django_app/
npm run gen:api                                        # from spa/
```

CI fails if either is out of date.

**Auth.** The app logs in with `POST /api/v1/auth/cookie/login`, which sets
the same httponly JWT cookies as the classic login page, so one sign-in
covers both. `src/api/client.ts` adds the CSRF header to unsafe requests
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
