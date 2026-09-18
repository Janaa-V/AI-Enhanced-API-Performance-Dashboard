# Backend

## Purpose

The backend is a Python and FastAPI service using PostgreSQL for persistence. It will provide the dashboard's data, simulated API traffic, metrics aggregation, and AI-assisted analysis.

## Development Plan

See [the backend development plan](./DEVELOPMENT_PLAN.md) for proposed API contracts, data storage, implementation milestones, and verification criteria. The first usable milestone group covers service setup, simulated traffic, request recording, and dashboard metrics; AI integration follows.

## Responsibilities

- Expose mock endpoints that simulate common backend services with varied latency and occasional errors.
- Capture request metadata, including endpoint, HTTP method, status code, latency, and timestamp.
- Persist request logs in PostgreSQL.
- Aggregate request data into endpoint-level metrics, status-code breakdowns, latency trends, and recent-request records.
- Expose metrics and analysis endpoints for the React frontend.
- Call an external AI provider from an isolated service module and return concise performance observations.
- Provide configuration for PostgreSQL connection settings, AI credentials, CORS, and analysis time windows.

## Planned API

- `GET /metrics` returns aggregated performance data for the selected time window.
- `POST /analyze` accepts an optional time window and returns an AI-generated summary of recent metrics.
- Mock endpoints are grouped under a dedicated demo route prefix so monitoring traffic remains separate from dashboard API routes.

## Core Modules

The following list includes planned modules; models, schemas, request logging, and feature services are not implemented yet.

- `app/main.py` initializes the FastAPI application, database, middleware, and routers.
- `app/database.py` manages the PostgreSQL connection pool and request sessions.
- `app/models.py` defines database models.
- `app/schemas.py` defines request and response contracts.
- `app/middleware/request_logging.py` records request performance data.
- `app/services/metrics_service.py` calculates aggregates and trends.
- `app/services/ai_analysis.py` builds prompts, calls the selected AI provider, and validates responses.
- `app/api/routers/` contains endpoint handlers for mock traffic, metrics, and insights.

## Local Configuration

Settings are defined in `app/config.py`. See [environment and secret management](./ENVIRONMENT.md) for defaults, override rules, and deployment guidance.

## Initial Scaffold

The scaffold includes application configuration, CORS, an asynchronous SQLAlchemy/Psycopg PostgreSQL connection, and `GET /health` for database readiness. Startup verifies the connection and shutdown disposes the connection pool. Request tables, migrations, logging, demo routes, metrics, and AI integration follow the development plan.

## Local PostgreSQL

Local services can be managed separately in `~/Documents/os-services/compose.yaml`; that folder is outside this repository. To reproduce the setup, create that directory and save the following as `compose.yaml`:

```yaml
name: os-services
services:
  postgres:
    image: postgres:18
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-performance_dashboard}
      POSTGRES_USER: ${POSTGRES_USER:-dashboard}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD in .env}
    ports:
      - "127.0.0.1:5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U \"$$POSTGRES_USER\" -d \"$$POSTGRES_DB\""]
      interval: 5s
      timeout: 5s
      retries: 10
      start_period: 10s
volumes:
  postgres_data:
```

Create a private `.env` alongside it with `POSTGRES_PASSWORD` set to a strong development password. Keep that file untracked. Start the service before the backend:

```bash
cd ~/Documents/os-services
docker compose up -d --wait
docker compose ps
```

Connect at **127.0.0.1:5432**, with database `performance_dashboard` and user `dashboard`. Match `DB_PASSWORD` in `backend/.env` to `POSTGRES_PASSWORD` in `os-services/.env`; neither file should be committed. The database persists in a Docker named volume. `docker compose down` retains that volume; `down -v` deletes its data. Initialization credentials apply only to an empty volume. The local bootstrap role is a superuser; use a restricted application role in production.

The connection uses separate `DB_*` fields so passwords with special characters do not require manual URL encoding. `app/database.py` provides `get_session` for future routes; writes must explicitly commit. No application tables are created yet.

Packages contain `__init__.py` files; empty directories use `.gitkeep` placeholders. PostgreSQL stores its data in the external Docker volume; `backend/data/` is not database storage.

## Setup with the uv CLI

From `backend/`, `make setup` installs dependencies and creates `.env` only if it is missing. Start development with `make run`. Use `make help` to see all commands, including `make check`, `make format`, `make clean-logs`, and `make clean`. `make sync` requires an existing lockfile and installs with `--locked`.

Install the standalone uv tool using the [official installation instructions](https://docs.astral.sh/uv/getting-started/installation/), then restart your terminal and verify:

```bash
uv --version
```

From `backend/`, initialize the project environment:

```bash
uv sync --locked
make env
# Set DB_PASSWORD in .env to match os-services/.env before starting.
uv run uvicorn app.main:app --reload
```

`uv sync` creates `.venv` and generates `uv.lock` on first setup. Use `uv sync` without `--locked` if the lockfile has not been generated yet. Commit the lockfile for reproducible installs. The selected local Python version is 3.14; project metadata supports Python 3.12–3.14.

The standalone tool does not require pip. `uv run` uses the project virtual environment automatically, so shell activation is optional.

Add dependencies with `uv add PACKAGE` or `uv add --dev PACKAGE`.

Visit `http://127.0.0.1:8000/docs` for the API documentation. Run code checks from `backend/`:

```bash
uv run ruff check .
uv run ruff format --check .
```

Run database lifecycle and health tests with `make test` or `uv run pytest`. These tests use mocks and do not require a running PostgreSQL container.
