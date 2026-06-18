# TutorHub

A full-stack tutoring management platform. The backend is a FastAPI REST API with a PostgreSQL database. The frontend is a server-rendered web UI built with Jinja2 templates. Integrates with Google Calendar and uses OpenAI to parse Zoom session summaries into structured notes.

## Features

- Role-based access control (admin, tutor, admin\_tutor)
- Student profiles with Zoom, Google Docs, and OneDrive links
- Session logging with AI-powered Zoom summary parsing via OpenAI
- Payment and payee management
- Subject enrollment system
- Google Calendar integration (OAuth 2.0) for session scheduling
- Dashboard with analytics and KPIs
- Dark mode
- Alembic database migrations

## Project Structure

```
tutor_hub/
├── app/
│   ├── api/v1/routers/     # REST API endpoints
│   ├── web/routers/        # Server-rendered web UI routes
│   ├── models/             # SQLAlchemy ORM models
│   ├── schemas/            # Pydantic request/response schemas
│   ├── services/           # Business logic layer
│   ├── core/               # Config and database setup
│   ├── auth.py
│   └── main.py
├── alembic/                # Database migrations
├── templates/              # Jinja2 HTML templates
├── static/                 # CSS and JS assets
├── tests/
├── docker/
├── docker-compose.yml
├── Dockerfile
└── .env.example
```

## Setup

### Prerequisites

Docker Desktop installed and running.

### Steps

Create a `.env` file from the example and fill in your values:

```bash
cp .env.example .env
```

The variables you must set are listed in the [Environment Variables](#environment-variables) section.

Build and start all services:

```bash
docker compose up --build
```

Run migrations (first time only):

```bash
docker compose exec api alembic upgrade head
```

The app will be available at `http://localhost:8000`.

Interactive API docs: `http://localhost:8000/docs`

To stop:

```bash
docker compose down
```

## Running Tests

```bash
pytest
```

Coverage reports are written to `htmlcov/`. Open `htmlcov/index.html` in a browser to view line-by-line coverage.

## Environment Variables

| Variable | Description |
|---|---|
| `POSTGRES_USER` | PostgreSQL superuser name |
| `POSTGRES_PASSWORD` | PostgreSQL superuser password |
| `APP_DB_USER` | Application database user |
| `APP_DB_PASSWORD` | Application database password |
| `APP_DB_NAME` | Application database name |
| `SECRET_KEY` | Secret used to sign JWTs |
| `OPENAI_API_KEY` | API key from platform.openai.com |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret |
| `GOOGLE_REDIRECT_URI` | OAuth redirect URI (default: `http://localhost:8000/calendar/callback`) |

## API Endpoints

All REST endpoints are under the `/api/v1` prefix.

### Auth

| Method | Endpoint | Description | Auth required |
|---|---|---|---|
| POST | `/auth/login` | Log in and receive a JWT token | No |

### Users

| Method | Endpoint | Description | Auth required |
|---|---|---|---|
| GET | `/users/` | List all users | Admin |
| POST | `/users/` | Create a user | Admin |
| GET | `/users/{user_id}` | Get user details | Yes |
| PATCH | `/users/{user_id}/activate` | Activate a user | Admin |
| PATCH | `/users/{user_id}/deactivate` | Deactivate a user | Admin |
| GET | `/me/` | Get current user profile | Yes |
| PATCH | `/me/` | Update own profile | Yes |

### Students

| Method | Endpoint | Description | Auth required |
|---|---|---|---|
| GET | `/students/` | List students (supports `?q=` search) | Yes |
| POST | `/students/` | Create a student | Yes |
| GET | `/students/{student_id}` | Get student details | Yes |
| PATCH | `/students/{student_id}` | Update a student | Yes |
| POST | `/students/{student_id}/toggle-active` | Toggle active status | Yes |
| DELETE | `/students/{student_id}` | Delete a student | Admin |

### Sessions

| Method | Endpoint | Description | Auth required |
|---|---|---|---|
| GET | `/sessions/` | List sessions (supports `?q=` search) | Yes |
| POST | `/sessions/` | Log a session | Yes |
| GET | `/sessions/{session_id}` | Get session details | Yes |
| PATCH | `/sessions/{session_id}` | Update a session | Yes |
| DELETE | `/sessions/{session_id}` | Delete a session | Yes |

### Payments

| Method | Endpoint | Description | Auth required |
|---|---|---|---|
| GET | `/payments/` | List all payments | Admin |
| POST | `/payments/` | Create a payment | Admin |
| GET | `/payments/{payment_id}` | Get payment details | Admin |
| PATCH | `/payments/{payment_id}` | Update a payment | Admin |
| DELETE | `/payments/{payment_id}` | Delete a payment | Admin |

### Payees

| Method | Endpoint | Description | Auth required |
|---|---|---|---|
| GET | `/payees/` | List payees (supports `?q=` search) | Admin |
| POST | `/payees/` | Create a payee | Admin |
| GET | `/payees/{payee_id}` | Get payee details | Admin |
| GET | `/payees/{payee_id}/balance` | Get payee balance | Admin |
| PATCH | `/payees/{payee_id}` | Update a payee | Admin |
| DELETE | `/payees/{payee_id}` | Delete a payee | Admin |

### Subjects

| Method | Endpoint | Description | Auth required |
|---|---|---|---|
| GET | `/subjects/` | List all subjects | Yes |
| POST | `/subjects/` | Create a subject | Admin |
| DELETE | `/subjects/{subject_id}` | Delete a subject | Admin |

### Enrollments

| Method | Endpoint | Description | Auth required |
|---|---|---|---|
| POST | `/enrollments/` | Enroll a student in a subject | Yes |
| GET | `/enrollments/students/{student_id}` | Get a student's enrollments | Yes |
| DELETE | `/enrollments/students/{student_id}/subjects/{subject_id}` | Remove an enrollment | Yes |

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI, Uvicorn |
| Database | PostgreSQL, SQLAlchemy (async), Alembic |
| Auth | JWT (python-jose), bcrypt (passlib) |
| AI | OpenAI API (Zoom summary parsing) |
| Calendar | Google OAuth 2.0, Google Calendar API |
| Templating | Jinja2, Bootstrap |
| Testing | pytest, pytest-asyncio, httpx, pytest-cov |
| Containerisation | Docker, Docker Compose |
