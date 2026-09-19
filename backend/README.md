# Backend

Python 3.12–3.14 service built with FastAPI, async SQLAlchemy and PostgreSQL. It simulates API traffic, records every request, aggregates the data into dashboard metrics and produces AI-assisted observations.

## Status

| Milestone | Scope | State |
| --- | --- | --- |
| 1. Service foundation | Settings, lifespan-managed async database engine, CORS, `/health`, tooling, CI | Done |
| 2. Simulation and recording | Request model and migration (done); five `/demo/*` routes and logging middleware (planned) | In progress |
| 3. Dashboard metrics | Typed schemas, aggregate queries, time buckets, `GET /metrics` | Planned |
| 4. Demonstration workflow | Bounded traffic-generator script | Planned |
| 5. AI insights | Provider interface, one adapter, `POST /analyze` | Planned |
| 6. Frontend handoff | Response examples, error contracts, deployment settings | Planned |

Milestones 1–4 form the first usable backend and come before any live AI call. The API and data sections below describe the **target design**; only `/health` exists today.

## Quick start

Prerequisites: [uv](https://docs.astral.sh/uv/getting-started/installation/) and Docker.

```bash
# 1. Start PostgreSQL (see "Local PostgreSQL" below)
# 2. From backend/:
make setup            # install dependencies, create .env if missing
# 3. Set DB_PASSWORD in .env to match the PostgreSQL container
make migrate         # create the database tables
make run              # API on http://127.0.0.1:8000, docs at /docs
```

| Command | Purpose |
| --- | --- |
| `make check` | Lint, format check, type check and tests |
| `make test` | Unit tests; they mock the database and need no PostgreSQL |
| `make test-integration` | Tests against a real PostgreSQL test database |
| `make migrate` | Apply database migrations |
| `make migration MSG="..."` | Generate a migration from model changes; always review it |
| `make format` | Format with Ruff |
| `make audit` | Scan dependencies for known vulnerabilities |
| `make pre-commit-install` | Install Git hooks (Ruff, gitleaks, key detection) |
| `make clean` | Remove logs and caches; keeps `.env`, `.venv` and `uv.lock` |

Run `make help` for the full list. Automated checks are described in [CI](./CI.md).

## Local PostgreSQL

The database runs in Docker, outside this repository (`~/Documents/os-services/compose.yaml`), so its data survives project changes. To reproduce it, save the following as `compose.yaml` in that folder:

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

Create an untracked `.env` next to it with a strong `POSTGRES_PASSWORD`, then run `docker compose up -d --wait`. Set the same value as `DB_PASSWORD` in `backend/.env`.

- The port is bound to `127.0.0.1` only. `docker compose down` keeps the data volume; `down -v` deletes it.
- The password applies when the volume is first created; editing the files later does not change an existing role's password.
- The bootstrap role is a superuser, which is acceptable locally. Use a restricted role in production.

## Configuration

Settings are validated at startup by `app/config.py` (Pydantic). Values come from the process environment, which overrides `backend/.env`. Restart after changing them. Copy `.env.example` to `.env` (`make env` does this without overwriting).

| Variable | Default | Purpose |
| --- | --- | --- |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER` | `127.0.0.1`, `5432`, `performance_dashboard`, `dashboard` | PostgreSQL connection |
| `TEST_DB_NAME` | `performance_dashboard_test` | Database used by integration tests; emptied on every run, so it must end in `_test` |
| `DB_PASSWORD` | none, required | Database password; kept separate from the URL so special characters need no escaping |
| `CORS_ORIGINS` | `["http://localhost:5173"]` | Allowed browser origins, as a JSON array |
| `METRICS_WINDOW_MINUTES` | `60` | Default reporting window, 1–1440 |
| `AI_PROVIDER` | `disabled` | `disabled`, `gemini` or `groq` |
| `AI_API_KEY`, `AI_MODEL` | empty | Provider credentials and model, backend-only |
| `AI_TIMEOUT_SECONDS` | `30` | Provider timeout, above 0 and at most 120 |
| `ENVIRONMENT`, `APP_NAME` | `development`, `API Performance Dashboard` | Runtime label and API title |

**Secrets:** `.env` is git-ignored and only `.env.example` is tracked. AI keys stay in the backend; frontend `VITE_*` variables are public. Secrets are `SecretStr` values and must never be logged. In CI and deployment, inject secrets through the platform's secret store. If a key leaks, revoke it: deleting it from Git does not invalidate it.

## Data model

One table, `request_logs`, defined in `app/models.py` and created by an Alembic migration (never implicitly at startup). Every column is `NOT NULL`.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | bigint identity | Primary key |
| `endpoint` | text | Route template such as `/demo/users`; never the query string, body or credentials |
| `method` | text | HTTP method, validated by the application |
| `status_code` | smallint | Check: between 100 and 599 |
| `latency_ms` | double precision | Measured with a monotonic clock; check: at least 0 |
| `started_at` | `TIMESTAMPTZ` | Request start, stored in UTC |

Design choices:

- **Start plus duration, no end column.** The end time is `started_at + latency_ms`. Storing it too would duplicate one fact, and a wall-clock end time could disagree with the monotonic-clock latency. If a feature needs it, compute it in a query.
- **Constraints in the database.** Invalid values are rejected by PostgreSQL itself, whatever code writes them.
- **One index, on `started_at`.** Every metrics query filters by time window. An `(endpoint, started_at)` index is deliberately left out until a query plan shows it is needed, because each index slows every insert.
- **Named constraints.** A naming convention gives constraints and indexes predictable names, which keeps migrations reviewable.
- **Out of scope for now:** partitioning, rollup tables and extra columns such as an error flag or request ID; each can be added later with a migration.

## API design

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Readiness with a database check; `503` if the database is unavailable. Not measured. Implemented. |
| `GET /demo/users`, `/orders`, `/products`, `/search`, `/reports` | Synthetic services, each with its own latency range and failure rate; reports are slowest. Failures return a consistent JSON error body. |
| `GET /metrics` | Aggregated metrics for a time window |
| `POST /analyze` | AI observations for a time window |

### `GET /metrics`

Query parameters: `window_minutes` (default 60, 1–1440), `bucket_minutes` (default 5, 1–60), `recent_limit` (default 20, 1–100).

Response: `window` (UTC start, end, bucket size), `summary` (total requests, errors, error rate, average latency, requests per minute), `endpoints` (the same per endpoint and method), `status_codes`, `latency_trend` (time buckets, overall and per endpoint) and `recent_requests` (newest first, ID as tie-breaker).

Rules: rows are placed in windows and buckets by `started_at`. Filtering uses the half-open interval `[start, end)` with edge buckets clipped. Empty windows return zero counts, empty arrays, and null averages. Overall averages come from totals, not from averaging endpoint averages. Errors are HTTP status 400 and above.

### `POST /analyze`

Accepts an optional `window_minutes`. The server computes the metrics itself; clients cannot supply prompts or measurements. Returns the window, provider, generation time and analysis text. An empty window returns `no_data` without calling the provider. Missing configuration, timeouts, rate limits and malformed provider output return documented errors that expose no credentials or upstream details. Calls have a timeout, bounded input and output, a short cache and one in-flight request per window.

## Simulation and recording

- Only `/demo/*` requests are recorded; `/health`, `/metrics`, `/analyze` and docs are excluded.
- Delays use `asyncio.sleep`, so simulation never blocks other requests. Latency is measured with a monotonic clock, in milliseconds.
- Failed responses, including simulated failures, are recorded. A logging failure is reported in application logs and never changes the endpoint's response.
- Latency ranges and failure rates are configurable, and randomness is injectable so tests are deterministic.
- Automatic traffic generation is off by default. A local script generates bounded, varied traffic for demos.

## Testing

| Layer | Approach |
| --- | --- |
| Connection lifecycle, `/health` | Unit tests with a mocked database; no PostgreSQL, credentials or network needed. These run in CI. |
| Schema, migrations, request logging, metrics queries | Integration tests (`make test-integration`) against a separate PostgreSQL test database |
| AI provider | Mocked responses covering timeouts, rate limits, malformed output and missing configuration *(planned)* |

Queries need a real PostgreSQL because time binning, `TIMESTAMPTZ` and boundary behaviour are database behaviour that a mock cannot verify.

How the integration tests work:

- **Separate database.** They use the database named by `TEST_DB_NAME` (default `performance_dashboard_test`, changeable in `.env` or the environment, and required to end in `_test`), created automatically on first run. Development data is never touched.
- **Migrated once, emptied per test.** The migrations run once per test session; each test starts by truncating the tables. Truncating, rather than rolling back a transaction, lets the tests exercise code that commits its own transactions, such as the request-logging middleware.
- **Opt-in.** Plain `pytest` skips them, so `make test` works without a database. They fail with a clear message if PostgreSQL is unreachable.
- **What they check now:** the database rejects invalid rows, `TIMESTAMPTZ` preserves the instant, migrations can be reversed and reapplied, and the models still match the migrated schema, so a model change without a migration fails the build.

## Structure

```text
backend/
├── app/
│   ├── main.py                    App factory, lifespan, CORS, routers
│   ├── config.py                  Validated settings
│   ├── database.py                Async engine and per-request sessions
│   ├── models.py                  SQLAlchemy models (request_logs)
│   └── api/routers/health.py
├── migrations/                    Alembic revisions (schema history)
├── tests/
├── pyproject.toml, uv.lock        Dependencies (locked)
├── Makefile                       Developer commands
└── CI.md                          Automated checks
```

Planned additions: `schemas.py`, `middleware/request_logging.py`, `api/routers/{demo,metrics,analysis}.py`, `services/{metrics_service,ai_analysis,ai_providers}.py`, `scripts/generate_traffic.py`.

## Deployment assumptions

One backend instance, a managed PostgreSQL with persistent storage, and explicit CORS origins. Before public deployment: add access controls or server-enforced quotas to `/analyze`, use a restricted database role, and decide a retention and cleanup policy for `request_logs`.
