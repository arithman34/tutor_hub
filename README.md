# TutorHub

[![Deploy](https://github.com/arithman34/tutor_hub/actions/workflows/deploy.yml/badge.svg)](https://github.com/arithman34/tutor_hub/actions/workflows/deploy.yml)
[![coverage](https://raw.githubusercontent.com/arithman34/tutor_hub/gh-pages/badges/coverage.svg)](https://github.com/arithman34/tutor_hub/actions/workflows/deploy.yml)

A full-stack tutoring management platform. The backend is a Django REST Framework API on PostgreSQL, and the frontend is a React + TypeScript single-page app that Django serves. It integrates with Google Calendar, uses OpenAI to parse Zoom session summaries into structured notes, and includes TutorHub AI, a chat assistant that answers questions about the tutor's own students, sessions and payments by calling read-only tools.

**Live:** [tutorhub.arithman.dev](https://tutorhub.arithman.dev)

> The app started as a FastAPI project (still in [`app/`](app/) for reference, with its own tests and docs below) and was rewritten on Django + DRF, which is what's actually running in production now — see [`django_app/`](django_app) and its [README](django_app/README.md) for the current implementation. `app/`'s CI job was retired since nothing deploys it anymore; the code stays for reference.

## Screenshots

| Analytics | Session notes from a Zoom summary |
|---|---|
| ![Weekly sessions, no-shows and hours taught](docs/screenshots/admin-analytics-sessions.png) | ![Session detail with AI-generated notes](docs/screenshots/session-detail.png) |
| **Admin overview** | |
| ![Admin financial and operations overview](docs/screenshots/admin-dashboard.png) | |

<details>
<summary><strong>Admin pages</strong></summary>

| Sessions | Tutor accounts |
|---|---|
| ![All tutors' sessions](docs/screenshots/admin-sessions.png) | ![Tutor account management](docs/screenshots/admin-users.png) |
| **Payees and balances** | **Payments** |
| ![Payees with outstanding balances](docs/screenshots/admin-payees.png) | ![Payments received](docs/screenshots/admin-payments.png) |
| **Student trends** | **Payment trends** |
| ![Weekly new, active and lapsed students](docs/screenshots/admin-analytics-students.png) | ![Weekly payments received](docs/screenshots/admin-analytics-payments.png) |

</details>

## Features

- One account per tutor: every student, session, payee and payment belongs to the account that created it, and no account can see another's data
- "My data" JSON export and import of your own records
- Student profiles with Zoom, Google Docs, and OneDrive links
- Session logging with AI-powered Zoom summary parsing via OpenAI
- TutorHub AI: ask questions in plain English such as "does any payee owe me money?" or "summarise last week's classes for Lok", answered from your own data (see [TutorHub AI](#tutorhub-ai))
- Payment and payee management
- Google Calendar integration (OAuth 2.0) for session scheduling
- Dashboard with analytics and KPIs
- Automated overdue payment alerts via email (Celery + Redis + Resend)
- Dark mode
- Alembic database migrations

## TutorHub AI

TutorHub AI is a chat page (`/assistant`) where a tutor asks questions about their own records: "how many sessions has Lok had this term?", "does any payee owe me money?", "summarise last week's classes". It replaced an earlier Document Q&A feature (RAG over uploaded PDFs), which answered questions about teaching material rather than the business itself.

**How it works** ([`django_app/assistant/`](django_app/assistant))

1. The model gets the question, the last 10 turns of the conversation, and a system prompt with today's date in UK time. The prompt tells it to answer only from tool results and to ask when a name matches more than one student.
2. It can call five read-only tools ([`tools.py`](django_app/assistant/tools.py)): `find_students`, `count_sessions`, `get_sessions`, `list_payee_balances` and `get_payments`. Each runs a normal Django query scoped to the signed-in user, so another account's ids are reported as not found. Payee balances reuse the same calculation as the Payees page.
3. The agent loop ([`agent.py`](django_app/assistant/agent.py)) runs the requested tools and feeds the results back, for up to 5 rounds within a 45-second budget. Bad arguments come back to the model as errors it can correct, never as exceptions.
4. Only [`llm.py`](django_app/assistant/llm.py) knows the provider is OpenAI. Everything else uses provider-neutral message and tool-call types, so switching provider touches one file.

Tool output is kept to what answers need. Payee contact details, bank and payment references, raw Zoom transcripts and calendar ids never reach the model. Each account has a daily question allowance (default 1, or unlimited), editable in the Django admin. A question is reserved before the model is called and refunded if the provider fails.

**Tests** cover each tool's results and account scoping, date boundaries in UK time, the agent loop against a scripted fake model, the quota, and the chat page, including CSRF-enforcing tests.

## Technical decisions

**FastAPI → Django + DRF.** The project originally chose FastAPI over Django for the reason below, and that tradeoff was real. In practice, running this as the actual day-to-day tool for a real tutoring business for a while made Django's built-in admin, ORM/migrations, and batteries-included auth worth more than the async win, especially since this app's load is one tutor's worth of traffic, not a request volume where tying up a worker per request matters. The FastAPI app (`app/`) was fully ported feature-for-feature to Django + DRF (`django_app/`) and cut over to production; `app/` is kept in the repo for reference but nothing builds, tests or deploys it anymore.

> Original rationale, kept for context: *"Most requests spend their time waiting on Postgres, OpenAI or Google. FastAPI with async SQLAlchemy and asyncpg handles that without tying up a worker per request. Pydantic schemas validate the REST API and generate the OpenAPI docs at `/docs`. The JSON API and the Jinja2 pages both call the same service layer. Django's main draws are its ORM and its built-in admin, and this project uses neither. The admin area is custom, and SQLAlchemy with Alembic gives direct control over schema changes such as the pgvector columns."*

**Single container, no Celery.** The FastAPI app ran separate worker/beat/Redis processes for background email alerts and the weekly export. The Django app is a synchronous `gunicorn` process with no background task queue — simpler to run and reason about at this scale, at the cost of giving up true async background jobs (the weekly export now runs as its own scheduled ECS task; see `terraform/environments/cost-optimized`).

**Terraform, split into layers.** All AWS infrastructure is defined in Terraform as three root modules. `foundation` holds the parts that are costly or impossible to recreate: the VPC, RDS, ECR, IAM, and SSM secrets. `cost-optimized` is the compute layer that actually runs live — a single Fargate Spot task running the Django app plus a Cloudflare Tunnel sidecar, so the task has no inbound ports open. [`production`](terraform/environments/production) is an earlier, load-balanced + Celery/Redis design for the old FastAPI app; its state is empty (nothing is deployed from it) and it's kept only as a reference for that alternative shape. GitHub Actions authenticates to AWS through OIDC, so no long-lived access keys are stored.

**Tool calling, not RAG, for TutorHub AI.** The questions a tutor actually asks about their business are counts, balances and date-range filters over structured rows. Retrieving similar-looking text and letting the model add it up would miscount. Instead the model chooses from a few read-only tools, and the database does the counting. The model never writes SQL and can't change anything. This replaced the earlier Document Q&A feature, a pgvector RAG pipeline over uploaded PDFs, which answered a different question (what's in my teaching material) and saw little use.

## Project Structure

```
tutor_hub/
├── django_app/             # Current production backend (Django + DRF)
│   ├── accounts/           # Custom User model, JWT auth
│   ├── students/           # Student model/viewset
│   ├── tutoring_sessions/  # Session model/viewset
│   ├── billing/            # Payee/Payment models/viewsets
│   ├── assistant/          # TutorHub AI: read-only tools, agent loop, LLM client, daily quota
│   ├── calendar_integration/ # Google Calendar OAuth + events
│   ├── analytics/          # Dashboard trend data
│   ├── spa/                # The frontend: React + TypeScript app, served at /app/
│   ├── web/                # Public homepage and privacy page, redirects from old page URLs
│   ├── templates/          # Jinja2 templates for those public pages
│   ├── config/             # Settings, urls, wsgi
│   ├── Dockerfile
│   └── entrypoint.sh
├── app/                    # Retired FastAPI app — kept for reference only, not built/tested/deployed
│   ├── api/v1/routers/
│   ├── web/routers/
│   ├── models/             # SQLAlchemy ORM models
│   ├── schemas/             # Pydantic request/response schemas
│   ├── services/
│   ├── tasks/              # Celery background tasks
│   ├── core/
│   ├── auth.py
│   ├── worker.py
│   └── main.py
├── alembic/                # FastAPI app's database migrations
├── templates/              # FastAPI app's Jinja2 templates
├── static/                 # CSS and JS assets
├── tests/                  # FastAPI app's tests
├── terraform/              # AWS infrastructure (foundation, cost-optimized [live], production [legacy/unused])
├── docker/
├── docker-compose.yml
├── docker-compose.dev.yml
├── docker-compose.prod.yml
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
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

The app will be available at `http://localhost:8000`.

To stop:

```bash
docker compose down
```

## Deployment

The app runs on AWS and is provisioned with Terraform. See [terraform/environments/README.md](terraform/environments/README.md) for the architecture and setup. The live setup is a single ECS Fargate Spot task running the Django app (`gunicorn`) alongside a Cloudflare Tunnel sidecar — no Celery/Redis, since the Django app has no background task queue. The database is RDS PostgreSQL. Traffic reaches the app through the tunnel, so the task has no inbound ports open.

Every push to `main` runs the test suite, then the [deploy workflow](.github/workflows/deploy.yml):

1. Builds the image and pushes it to ECR, tagged with the commit SHA.
2. Registers a new task definition revision that points at that SHA tag.
3. Updates the ECS service and waits for the rollout to finish.

If the new task fails to start or fails its health check, the ECS deployment circuit breaker rolls the service back to the previous task definition revision, and the workflow fails. Each revision is pinned to a commit-specific image tag, so the rollback restores the previous image. A redeploy of `:latest` would just pull the broken image again.

To roll back by hand, point the service at an earlier revision:

```bash
aws ecs update-service --cluster tutorhub-lean --service app --task-definition tutorhub-lean-app:<revision>
```

## Running Tests

```bash
cd django_app && python manage.py test
```

The retired FastAPI app's tests (`pytest`, at the repo root) still run locally if needed, but aren't part of CI anymore. Coverage reports for it are written to `htmlcov/`.

## Environment Variables

| Variable | Description |
|---|---|
| `POSTGRES_HOST` / `POSTGRES_PORT` | Database host/port |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` | Database credentials |
| `POSTGRES_DB` | Database name |
| `DJANGO_SECRET_KEY` | Django's `SECRET_KEY` |
| `DJANGO_DEBUG` | `true`/`false` |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated allowed hosts (must include `localhost` in production — the container's own health check hits it) |
| `CSRF_TRUSTED_ORIGINS` | Comma-separated trusted origins behind the Cloudflare Tunnel |
| `OPENAI_API_KEY` | API key from platform.openai.com |
| `ASSISTANT_MODEL` | Chat model for TutorHub AI (optional, default `gpt-4o-mini`) |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Google OAuth client credentials |
| `GOOGLE_REDIRECT_URI` | OAuth redirect URI |
| `RESEND_API_KEY` | API key from resend.com for outbound email |
| `FROM_EMAIL` | Sender address for alert emails |

## API Endpoints

All REST endpoints are under the `/api/v1` prefix, served by Django REST Framework. Every endpoint except auth requires a logged-in user and only ever reads or writes that user's own rows: another account's ids return 404, and related ids in a payload (a session's `student`, a payment's `payee`, a student's `payee_id`) must belong to the same account or the request is rejected with 400. The platform operator sees across accounts only through Django's admin at `/django-admin/` (superuser only).

### Auth

| Method | Endpoint | Description | Auth required |
|---|---|---|---|
| POST | `/auth/login` | Log in, get an access + refresh token pair | No |
| POST | `/auth/refresh` | Exchange a refresh token for a new access token | No |
| POST | `/auth/logout` | Blacklist a refresh token | No |

### Students

| Method | Endpoint | Description | Auth required |
|---|---|---|---|
| GET | `/students/` | List students (supports `?q=` search) | Yes |
| POST | `/students/` | Create a student | Yes |
| GET | `/students/{student_id}` | Get student details | Yes |
| PATCH | `/students/{student_id}` | Update a student | Yes |
| POST | `/students/{student_id}/toggle-active` | Toggle active status | Yes |
| DELETE | `/students/{student_id}` | Delete a student | Yes |

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
| GET | `/payments/` | List payments | Yes |
| POST | `/payments/` | Create a payment | Yes |
| GET | `/payments/{payment_id}` | Get payment details | Yes |
| PATCH | `/payments/{payment_id}` | Update a payment | Yes |
| DELETE | `/payments/{payment_id}` | Delete a payment | Yes |

### Payees

| Method | Endpoint | Description | Auth required |
|---|---|---|---|
| GET | `/payees/` | List payees (supports `?q=` search) | Yes |
| POST | `/payees/` | Create a payee | Yes |
| GET | `/payees/{payee_id}` | Get payee details | Yes |
| GET | `/payees/{payee_id}/balance` | Get payee balance | Yes |
| PATCH | `/payees/{payee_id}` | Update a payee | Yes |
| DELETE | `/payees/{payee_id}` | Delete a payee | Yes |

## Tech Stack

| Layer | Technology |
|---|---|
| API | Django, Django REST Framework, Gunicorn |
| Database | PostgreSQL, Django ORM, migrations |
| Auth | JWT (`djangorestframework-simplejwt`), bcrypt (for legacy password hashes) |
| AI | OpenAI API (TutorHub AI tool calling, Zoom summary parsing) |
| Calendar | Google OAuth 2.0, Google Calendar API |
| Email | Resend |
| Frontend | React, TypeScript, Vite, React Router, TanStack Query, React Hook Form + Zod, Tailwind CSS, Chart.js |
| API types | OpenAPI schema (drf-spectacular), generated TypeScript types (openapi-typescript) |
| Static files | WhiteNoise |
| Testing | Django's test runner (`manage.py test`); Vitest, Testing Library and MSW for the frontend |
| Containerisation | Docker, Docker Compose |
| CI/CD | GitHub Actions |
| Hosting | AWS (ECS Fargate, RDS), Cloudflare Tunnel, Terraform |

*(The retired FastAPI app in `app/` used FastAPI/Uvicorn, async SQLAlchemy + Alembic, python-jose JWTs, and Celery + Redis for background tasks — see [`app/`](app) and [`tests/`](tests) if you want to see that version.)*
