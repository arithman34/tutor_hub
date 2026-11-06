# TutorHub — Django rewrite (in progress)

This is the Django + DRF rewrite of the FastAPI app living in `app/` at the
repo root. It's being built incrementally, app by app; see the root
`CLAUDE.md`/conversation history for the full migration plan.

## Apps

- `accounts` — custom email-based `User` model, JWT auth (login/refresh/logout
  via `djangorestframework-simplejwt`), Django admin registration. Scaffolded.
- `students`, `sessions`, `billing`, `calendar_integration`, `rag`,
  `analytics` — not started yet.

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
