# TutorHub

[![Deploy](https://github.com/arithman34/tutor_hub/actions/workflows/deploy.yml/badge.svg)](https://github.com/arithman34/tutor_hub/actions/workflows/deploy.yml)
[![coverage](https://raw.githubusercontent.com/arithman34/tutor_hub/gh-pages/badges/coverage.svg)](https://github.com/arithman34/tutor_hub/actions/workflows/deploy.yml)

A full-stack tutoring management platform. The backend is Django + Django REST Framework with a PostgreSQL database. The frontend is a server-rendered web UI built with Jinja2 templates. It integrates with Google Calendar, uses OpenAI to parse Zoom session summaries into structured notes, and answers questions over uploaded teaching documents using retrieval-augmented generation (RAG) on pgvector.

**Live:** [tutorhub.arithman.dev/login](https://tutorhub.arithman.dev/login)

> The app started as a FastAPI project (still in [`app/`](app/) for reference, with its own tests and docs below) and was rewritten on Django + DRF, which is what's actually running in production now — see [`django_app/`](django_app) and its [README](django_app/README.md) for the current implementation. `app/`'s CI job was retired since nothing deploys it anymore; the code stays for reference.

## Screenshots

| Analytics | Document Q&A |
|---|---|
| ![Weekly sessions, no-shows and hours taught](docs/screenshots/admin-analytics-sessions.png) | ![Document Q&A answer with source pages](docs/screenshots/documents-query.png) |
| **Session notes from a Zoom summary** | **Admin overview** |
| ![Session detail with AI-generated notes](docs/screenshots/session-detail.png) | ![Admin financial and operations overview](docs/screenshots/admin-dashboard.png) |

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

- Role-based access control (admin, tutor, admin\_tutor)
- Student profiles with Zoom, Google Docs, and OneDrive links
- Session logging with AI-powered Zoom summary parsing via OpenAI
- Document library: upload PDFs (past papers, textbooks, notes) and ask questions across them, filtered by subject, level, document type and exam board, with answers citing source pages (see [Document Q&A](#document-qa-rag))
- Payment and payee management
- Google Calendar integration (OAuth 2.0) for session scheduling
- Dashboard with analytics and KPIs
- Automated overdue payment alerts via email (Celery + Redis + Resend)
- Dark mode
- Alembic database migrations

## Document Q&A (RAG)

Tutors upload PDFs from the **Documents** page and ask questions across them. Retrieval runs inside the main app, against the same PostgreSQL database, using pgvector. (Described below as originally built in FastAPI; the live Django port works the same way — see [`django_app/rag/services.py`](django_app/rag/services.py).)

**Ingestion** ([`app/services/ingestion.py`](app/services/ingestion.py))

1. pdfplumber extracts the text page by page. Blank pages are skipped. A PDF with no extractable text, such as a scan without an OCR layer, is rejected.
2. Each page is split into 800-character chunks that overlap by 100 characters, so text cut at a boundary still appears in context in the next chunk. Chunks never span two pages, so each one keeps an exact page number.
3. All of a document's chunks are embedded in one batched call to OpenAI `text-embedding-3-small`, which returns 1536-dimensional vectors.
4. The document row (title, type, subject, level, optional exam board) and its chunks are written in a single transaction. Each chunk's embedding goes in a `vector(1536)` column.

**Querying** ([`app/services/query.py`](app/services/query.py))

1. The question is embedded with the same model.
2. One SQL query ranks chunks by cosine distance (pgvector's `<=>` operator) and returns the top 5. Any filters on document type, subject, level or exam board are `WHERE` clauses in that same query. The top 5 therefore always come from the filtered set; results are never trimmed after ranking.
3. The retrieved chunks go to `gpt-4o-mini`, each labelled with its document title and page number. The system prompt tells the model to answer only from that context and to say so when the answer isn't there.
4. The response lists the source document and page for every retrieved chunk, with duplicate pages removed. The UI renders LaTeX in answers with MathJax, so equations display properly.

Search is exact, with no approximate-nearest-neighbour index. For a single tutoring business's library, a sequential scan is fast and returns exact results. If the library grows, an HNSW index is the next step. Models, chunk size, overlap and `top_k` are set in [`app/core/config.py`](app/core/config.py) and can be overridden with environment variables (`EMBEDDING_MODEL`, `CHAT_MODEL`, `CHUNK_SIZE`, `CHUNK_OVERLAP`, `TOP_K`).

**Tests**

- [`tests/test_service_ingestion.py`](tests/test_service_ingestion.py) covers chunk boundaries and the 100-character overlap, rejection of PDFs with no text, and saving documents with and without the optional metadata.
- [`tests/test_service_query.py`](tests/test_service_query.py) covers the fallback when nothing matches, answers with sources, merging of sources that share a page, and metadata filters that exclude non-matching documents.

The OpenAI calls are mocked. The similarity queries run against a real pgvector database (the `pgvector/pgvector:pg17` service in CI), so the retrieval SQL is tested exactly as it runs in production.

## Technical decisions

**FastAPI → Django + DRF.** The project originally chose FastAPI over Django for the reason below, and that tradeoff was real. In practice, running this as the actual day-to-day tool for a real tutoring business for a while made Django's built-in admin, ORM/migrations, and batteries-included auth worth more than the async win, especially since this app's load is one tutor's worth of traffic, not a request volume where tying up a worker per request matters. The FastAPI app (`app/`) was fully ported feature-for-feature to Django + DRF (`django_app/`) and cut over to production; `app/` is kept in the repo for reference but nothing builds, tests or deploys it anymore.

> Original rationale, kept for context: *"Most requests spend their time waiting on Postgres, OpenAI or Google. FastAPI with async SQLAlchemy and asyncpg handles that without tying up a worker per request. Pydantic schemas validate the REST API and generate the OpenAPI docs at `/docs`. The JSON API and the Jinja2 pages both call the same service layer. Django's main draws are its ORM and its built-in admin, and this project uses neither. The admin area is custom, and SQLAlchemy with Alembic gives direct control over schema changes such as the pgvector columns."*

**Single container, no Celery.** The FastAPI app ran separate worker/beat/Redis processes for background email alerts and the weekly export. The Django app is a synchronous `gunicorn` process with no background task queue — simpler to run and reason about at this scale, at the cost of giving up true async background jobs (the weekly export now runs as its own scheduled ECS task; see `terraform/environments/cost-optimized`).

**Terraform, split into layers.** All AWS infrastructure is defined in Terraform as three root modules. `foundation` holds the parts that are costly or impossible to recreate: the VPC, RDS with pgvector, ECR, IAM, and SSM secrets. `cost-optimized` is the compute layer that actually runs live — a single Fargate Spot task running the Django app plus a Cloudflare Tunnel sidecar, so the task has no inbound ports open. [`production`](terraform/environments/production) is an earlier, load-balanced + Celery/Redis design for the old FastAPI app; its state is empty (nothing is deployed from it) and it's kept only as a reference for that alternative shape. GitHub Actions authenticates to AWS through OIDC, so no long-lived access keys are stored.

**RAG inside the app.** Document Q&A started as a separate service and was moved into the main app on pgvector. Chunks live in the same Postgres database as students and sessions. That leaves one database to back up and no second service to host or secure. Metadata filters are ordinary SQL against the same data. A document and its chunks commit in one transaction, so a failed upload never leaves a half-indexed document behind. The trade-off is that vector search shares the database with the transactional workload. That is fine at this scale, and because retrieval sits behind its own service module, it could be split out again later.

## Project Structure

```
tutor_hub/
├── django_app/             # Current production backend (Django + DRF)
│   ├── accounts/           # Custom User model, JWT auth
│   ├── students/           # Student model/viewset
│   ├── tutoring_sessions/  # Session model/viewset
│   ├── billing/            # Payee/Payment models/viewsets
│   ├── rag/                # Document Q&A: models, ingestion, query
│   ├── calendar_integration/ # Google Calendar OAuth + events
│   ├── analytics/          # Dashboard trend data
│   ├── web/                # Server-rendered pages (reuses the Jinja2 templates below)
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
├── templates/              # Jinja2 HTML templates (shared by both backends)
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

The app runs on AWS and is provisioned with Terraform. See [terraform/environments/README.md](terraform/environments/README.md) for the architecture and setup. The live setup is a single ECS Fargate Spot task running the Django app (`gunicorn`) alongside a Cloudflare Tunnel sidecar — no Celery/Redis, since the Django app has no background task queue. The database is RDS PostgreSQL with pgvector. Traffic reaches the app through the tunnel, so the task has no inbound ports open.

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
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Google OAuth client credentials |
| `GOOGLE_REDIRECT_URI` | OAuth redirect URI |
| `RESEND_API_KEY` | API key from resend.com for outbound email |
| `FROM_EMAIL` | Sender address for alert emails |

## API Endpoints

All REST endpoints are under the `/api/v1` prefix, served by Django REST Framework. User/tutor account management (create, activate/deactivate, role) moved to the admin-only web pages (`/admin/users`) rather than the API.

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

## Tech Stack

| Layer | Technology |
|---|---|
| API | Django, Django REST Framework, Gunicorn |
| Database | PostgreSQL, pgvector, Django ORM, migrations |
| Auth | JWT (`djangorestframework-simplejwt`), bcrypt (for legacy password hashes) |
| AI | OpenAI API (Zoom summary parsing, embeddings, document Q&A) |
| PDF parsing | pdfplumber |
| Calendar | Google OAuth 2.0, Google Calendar API |
| Email | Resend |
| Templating | Jinja2 (via Django's Jinja2 template backend), Tailwind CSS |
| Static files | WhiteNoise |
| Testing | Django's test runner (`manage.py test`) |
| Containerisation | Docker, Docker Compose |
| CI/CD | GitHub Actions |
| Hosting | AWS (ECS Fargate, RDS), Cloudflare Tunnel, Terraform |

*(The retired FastAPI app in `app/` used FastAPI/Uvicorn, async SQLAlchemy + Alembic, python-jose JWTs, and Celery + Redis for background tasks — see [`app/`](app) and [`tests/`](tests) if you want to see that version.)*
