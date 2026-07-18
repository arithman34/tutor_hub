# TutorHub

A full-stack tutoring management platform. The backend is a FastAPI REST API with a PostgreSQL database. The frontend is a server-rendered web UI built with Jinja2 templates. Integrates with Google Calendar and uses OpenAI to parse Zoom session summaries into structured notes.

**Live:** [tutorhub.arithman.dev/login](https://tutorhub.arithman.dev/login) | **API Docs:** [tutorhub.arithman.dev/docs](https://tutorhub.arithman.dev/docs)

## Features

- Role-based access control (admin, tutor, admin\_tutor)
- Student profiles with Zoom, Google Docs, and OneDrive links
- Session logging with AI-powered Zoom summary parsing via OpenAI
- Payment and payee management
- Google Calendar integration (OAuth 2.0) for session scheduling
- Dashboard with analytics and KPIs
- Automated overdue payment alerts via email (Celery + Redis + Resend)
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
│   ├── tasks/              # Celery background tasks
│   ├── core/               # Config and database setup
│   ├── auth.py
│   ├── worker.py           # Celery app and beat schedule
│   └── main.py
├── alembic/                # Database migrations
├── templates/              # Jinja2 HTML templates
├── static/                 # CSS and JS assets
├── tests/
├── docker/
├── docker-compose.yml
├── docker-compose.dev.yml
├── docker-compose.prod.yml
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
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

The app will be available at `http://localhost:8000`.

Interactive API docs: `http://localhost:8000/docs`

To stop:

```bash
docker compose down
```

## Deployment

The app runs on AWS (ECS Fargate, RDS PostgreSQL with pgvector, ElastiCache), provisioned with Terraform — see [terraform/README.md](terraform/README.md) for the architecture and setup. A GitHub Actions pipeline runs tests on every push to `main`, then builds the image, pushes it to ECR, and redeploys the ECS services.

To deploy manually:

```bash
aws ecr get-login-password --region eu-west-2 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.eu-west-2.amazonaws.com
docker build -t <ecr_repository_url>:latest .
docker push <ecr_repository_url>:latest
for service in api worker beat; do
  aws ecs update-service --cluster tutorhub --service "$service" --force-new-deployment
done
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
| `GOOGLE_REDIRECT_URI` | OAuth redirect URI |
| `REDIS_URL` | Redis connection URL (default: `redis://redis:6379/0`) |
| `RESEND_API_KEY` | API key from resend.com for outbound email |
| `FROM_EMAIL` | Sender address for alert emails |

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

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI, Uvicorn |
| Database | PostgreSQL, SQLAlchemy (async), Alembic |
| Auth | JWT (python-jose), bcrypt (passlib) |
| AI | OpenAI API (Zoom summary parsing) |
| Calendar | Google OAuth 2.0, Google Calendar API |
| Background tasks | Celery, Redis |
| Email | Resend |
| Templating | Jinja2, Bootstrap |
| Testing | pytest, pytest-asyncio, httpx, pytest-cov |
| Containerisation | Docker, Docker Compose |
| CI/CD | GitHub Actions |
| Hosting | AWS (ECS Fargate, RDS, ElastiCache), Terraform |
