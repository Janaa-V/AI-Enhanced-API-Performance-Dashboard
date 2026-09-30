# Backend

Python 3.12–3.14 service built with FastAPI, async SQLAlchemy and PostgreSQL. It simulates API traffic, records every request, aggregates the data into dashboard metrics and produces AI-assisted observations.

## Status

| Milestone | Scope | State |
| --- | --- | --- |
| 1. Service foundation | Settings, lifespan-managed async database engine, CORS, `/health`, tooling, CI | Done |
| 2. Simulation and recording | Request model, migration, simulation engine, five `GET /demo/*` routes, `POST /demo/orders`, the recording service, the logging middleware, and wiring them into the app | Done |
| 3. Dashboard metrics | Typed schemas, aggregate queries, time buckets, `GET /metrics` | Done |
| 4. Demonstration workflow | Bounded traffic generator (live and synthetic backfill), `make traffic` | Done |
| 5. AI insights | Provider interface, one adapter, `POST /analyze` | Planned |
| 6. Frontend handoff | Response examples, error contracts, deployment settings | Planned |

Milestones 1–4 form the first usable backend and come before any live AI call. The API and data sections below describe the **target design**; `/health`, the demo routes and `/metrics` exist today.

## Quick start

Prerequisites: [uv](https://docs.astral.sh/uv/getting-started/installation/) and Docker.

```bash
# 1. Start PostgreSQL (see "Local PostgreSQL" below)
# 2. From backend/:
make setup            # install dependencies, create .env if missing
# 3. Set DB_PASSWORD in .env to match the PostgreSQL container
make migrate         # create the database tables
make run              # API on http://127.0.0.1:8000, docs at /docs
# 4. In a second terminal, give the dashboard data:
make traffic          # 60 s of live requests, then a summary
curl 'http://127.0.0.1:8000/metrics?window_minutes=5&bucket_minutes=1'
```

| Command | Purpose |
| --- | --- |
| `make check` | Lint, format check, type check and tests |
| `make test` | Unit tests; they mock the database and need no PostgreSQL |
| `make test-integration` | Tests against a real PostgreSQL test database |
| `make migrate` | Apply database migrations |
| `make migration MSG="..."` | Generate a migration from model changes; always review it |
| `make traffic` | Send live demo traffic to the running backend (`ARGS="--duration 300 --concurrency 10"`) |
| `make backfill HOURS=24` | Write synthetic past rows so charts have history (invented, not measured) |
| `make openapi` | Write the API schema to `frontend/openapi.json`, which the frontend's types are generated from; `make openapi-check` fails if it is out of date |
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
| `SIMULATION_LATENCY_SCALE` | `1` | Multiplier for simulated delays; `0` removes them |
| `SIMULATION_FAILURE_SCALE` | `1` | Multiplier for simulated failure rates; `0` turns failures off |
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
| `GET /demo/users`, `/orders`, `/products`, `/search`, `/reports` | Synthetic services, each with its own latency range and failure rate; reports are slowest. Failures return a consistent JSON error body. Implemented. |
| `POST /demo/orders` | Creates a priced order from a validated JSON body and returns `201`; nothing is stored. Implemented. |
| `GET /metrics` | Aggregated metrics for a time window; `503` if the database is unavailable. Not measured. Implemented. |
| `POST /analyze` | AI observations for a time window |

### Demo routes and the error format

Each route returns small fixed data and never touches the database, so the measured time is exactly the simulated time. `GET /demo/search?q=lap` filters the products by name, ignoring case, and accepts a query of at most 100 characters.

`POST /demo/orders` accepts `{"user_id": 2, "items": [{"product_id": 2, "quantity": 2}]}` and returns `201` with a random UUID `id`, `status: "created"`, and a `total` computed from the fixed product prices (rounded to cents). It is strict: `user_id` and `product_id` must be at least 1, there must be 1–20 items with a `quantity` of 1–99, and unknown fields are rejected so a typo such as `qty` is caught. An unknown `product_id` returns a `422` whose `loc` points at the exact field, for example `["body", "items", 1, "product_id"]`. Creating orders uses its own, slower and less reliable profile than listing them, so reads and writes look different on the dashboard.

A simulated failure returns one JSON shape for every route and status:

```json
{"error": {"code": "gateway_timeout", "message": "An upstream service took too long to respond."}}
```

| Status | `code` |
| --- | --- |
| 500 | `internal_error` |
| 503 | `service_unavailable` |
| 504 | `gateway_timeout` |

Invalid requests (for example a `q` longer than 100 characters, or an order body that breaks the rules above) get a standard FastAPI `422` immediately: handlers call the simulator only after FastAPI has validated the request, so bad input is never delayed or disguised as a simulated server failure. The interactive docs at `/docs` list, for each route, exactly the failure statuses its profile allows.

### `GET /metrics`

Query parameters: `window_minutes` (default `METRICS_WINDOW_MINUTES`, 60; 1–1440), `bucket_minutes` (default 5, 1–60), `recent_limit` (default 20, 1–100). A window may hold at most 288 buckets (a day in 5-minute buckets); above that the response is a `422` on `bucket_minutes` that names the smallest bucket size allowed. A database failure or a query over the 5-second limit returns the shared `503` body, with details only in the server log.

Response (models in `app/schemas/metrics.py`): `window` (UTC start, end, window and bucket size), `summary` (total requests, server errors, client errors, error rate, average and p95 latency, requests per minute), `endpoints` (the same statistics per method and route template), `status_codes` (ascending, only statuses that occurred), `latency_trend` (time buckets with the same statistics, overall and per endpoint) and `recent_requests` (newest first, ID as tie-breaker).

Rules:

- **Windows and buckets.** Rows are placed by `started_at`. Filtering uses the half-open interval `[start, end)`. Buckets are aligned to round UTC times (10:00, 10:05), not to the window start, so their boundaries stay put between refreshes; the first and last buckets are clipped to the window and can be shorter. Every bucket is listed, empty ones included, for the overall trend and for each endpoint that has requests in the window.
- **Errors are 5xx.** `error_rate` is server errors divided by total requests. Client errors (4xx, such as a `422` for an invalid order) are counted separately, because a bad request is not the service failing.
- **Latency.** Milliseconds as unrounded numbers; the client rounds for display. p95 is interpolated (`percentile_cont`); p99 is left out because small windows make it noisy. Overall figures come from the rows, never from averaging per-endpoint figures.
- **Empty data.** Counts are `0` and lists are empty; `error_rate`, average and p95 are `null`, never `0`, since there is nothing to measure. These fields are always present, so generated client types read `number | null`.
- **Formats.** Timestamps are ISO 8601 UTC with a `Z` suffix; rates are fractions from 0 to 1; lists are arrays of objects rather than objects keyed by name.
- **One snapshot.** The window end is fixed once per request and all queries run in one `REPEATABLE READ, READ ONLY` transaction with a 5-second statement timeout, so a row saved mid-request cannot make the per-endpoint totals disagree with the summary, and a slow query cannot hold a connection.

The queries live in `app/services/metrics.py`. Each takes the caller's session and a `TimeWindow` (timezone-aware bounds, computed in Python so tests can fix the clock), and the statistics columns are defined once and reused by every query. `collect_metrics` starts the snapshot and runs them in turn; the router (`app/api/routers/metrics.py`) only validates parameters, reads the clock (a dependency, so tests fix it) and maps database failures to `503`.

The trend groups rows with PostgreSQL's `date_bin`, which returns only buckets that have rows; a pure Python function lists every bucket in the window and fills the empty ones. Both use the same origin constant, and a database bucket that the Python list lacks raises an error instead of being dropped. The overall trend is a separate query from the per-endpoint one, because percentiles cannot be combined: the overall p95 is not derivable from per-endpoint p95s. Recent requests are read newest first through the `started_at` index and converted to UTC, whatever the database session's time zone.

**Performance, measured on 27 Sep 2026** (100,000 rows over 24 hours, local PostgreSQL 18): the full response takes a median of 17 ms for a 60-minute window and 260 ms for a 1440-minute window. Recent requests take under 0.1 ms through a backward scan of the `started_at` index. For a whole-day window every row is read, so a sequential scan is the right plan and no extra index would help; the per-endpoint trend is the slowest query (about 120 ms), mostly sorting for grouping and `percentile_cont`. Raising `work_mem` to 16 MB removed the disk sorts but did not change the end-to-end time, so it was not adopted. No index was added. If the table grows far beyond this, the next steps are `GROUPING SETS` to share one scan between the two trend queries, then rollup tables.

### `POST /analyze`

Accepts an optional `window_minutes`. The server computes the metrics itself; clients cannot supply prompts or measurements. Returns the window, provider, generation time and analysis text. An empty window returns `no_data` without calling the provider. Missing configuration, timeouts, rate limits and malformed provider output return documented errors that expose no credentials or upstream details. Calls have a timeout, bounded input and output, a short cache and one in-flight request per window.

## Simulation and recording

- Only `/demo/*` requests are recorded; `/health`, `/metrics`, `/analyze` and docs are excluded.
- Delays use `asyncio.sleep`, so simulation never blocks other requests. Latency is measured with a monotonic clock, in milliseconds.
- Failed responses, including simulated failures, are recorded. A logging failure is reported in application logs and never changes the endpoint's response.
- `RequestRecorder` (`services/request_recorder.py`) saves one row per request in a short transaction with a 2-second limit. Recording is best effort: a failed or slow save is logged as a single line (the full traceback only at debug level) and dropped, while cancellation during shutdown is deliberately not swallowed. It takes a plain `RequestRecord` (method, route template, status, latency, UTC start time), so callers never touch the database model.
- `RequestLoggingMiddleware` (`middleware/request_logging.py`) is a pure ASGI middleware, not `BaseHTTPMiddleware`, which has known problems with exceptions and streaming. It records only HTTP requests under `/demo/`, so `/health`, `/docs`, `/metrics` and browser preflights are never recorded, and it sits innermost, inside the CORS layer.
  - The endpoint is the matched **route template** (`/demo/items/{item_id}`), never the raw path or query string. Requests that matched no route (404s) are skipped, so random paths cannot fill the table.
  - Latency uses a monotonic clock and ends when the final response chunk is sent, so the database write never counts. The row is saved after the response has been sent.
  - An unhandled crash is recorded as a `500` and re-raised unchanged. That save runs as a background task, because waiting would delay the `500` the outer layer is about to send. A client disconnect or a cancelled request is not recorded.
  - The recorder, the clock and the wall-clock time are injected, so tests need no database and no real waiting. A failing recorder can never break a request or hide the original error.
  - Wiring (`app/main.py`): the recorder is created at startup from the database's sessions and cleared at shutdown, and the middleware finds it on the app state. Before startup or after shutdown nothing is recorded and nothing breaks.
- Each endpoint has a profile in `app/services/simulation/profiles.py`: a latency range, a failure probability and the server-error codes a failure chooses from. Latency is uniform within the range; a failing request still waits its full time first, like a real timeout.
- `Simulator` (`simulator.py`) separates the decision from the side effects: `plan(profile)` is a pure function that returns the delay and outcome, and `simulate(profile)` waits and raises. It takes any profile, and receives its random generator and sleep function as parameters, so tests force any outcome and never wait in real time.
- Two settings scale every profile (`SIMULATION_LATENCY_SCALE`, `SIMULATION_FAILURE_SCALE`), for example failures off for a quiet demo.
- A traffic generator (`scripts/generate_traffic.py`) gives the dashboard data; see below.

| Endpoint | Latency | Failure rate | Failure statuses |
| --- | --- | --- | --- |
| `users` | 20–80 ms | 2% | 500, 503 |
| `products` | 30–120 ms | 1% | 500 |
| `orders` | 60–250 ms | 5% | 500, 503 |
| `search` | 80–400 ms | 3% | 503, 504 |
| `reports` | 400–1500 ms | 8% | 504, 500 |
| `orders_create` (`POST /demo/orders`) | 100–400 ms | 6% | 500, 503 |

### What a recorded request looks like

Checked on the real server with `curl`: one row per demo call; `/health`, `/docs` and unknown paths add none; the query string is never stored.

| id | method | endpoint | status_code | latency_ms | started_at (UTC) |
| --- | --- | --- | --- | --- | --- |
| 1 | GET | `/demo/users` | 200 | 58.6 | 21:01:32.395 |
| 5 | GET | `/demo/reports` | 200 | 1340.3 | 21:01:32.704 |
| 6 | POST | `/demo/orders` | 201 | 288.1 | 21:01:34.074 |
| 7 | POST | `/demo/orders` | 422 | 1.0 | 21:01:34.372 |

### Demo traffic

`scripts/generate_traffic.py` has two modes.

**Live (default): `make traffic`.** Workers send real HTTP requests to a running server until the time is up, pausing 50–300 ms between requests like users would. Every row is measured by the real middleware. The mix is weighted like a small shop: users 30%, products 25%, order list 20%, search 12% (random terms), orders created 8% and reports 5%. One order in ten has a deliberately invalid body (unknown product, zero quantity or a misspelt field), so client errors (`422`) show on the dashboard. At the end it prints requests by status and a client-side p95 per endpoint, interpolated like `percentile_cont`, so it can be compared with `/metrics`; the client figure is a few milliseconds higher because it includes HTTP overhead. Bounds: `--duration` 1–3600 s (default 60), `--concurrency` 1–50 (default 5). It checks `/health` first, and it refuses any host other than localhost unless `--allow-remote` is passed.

**Backfill: `make backfill HOURS=24`.** Writes past rows straight to the configured database so charts have history at once, at `--per-minute` rows per minute (default 20, so 28,800 rows for a day). The rows use the same mix and the same simulation profiles as live traffic, and invalid orders take 1–5 ms because the real app rejects them before simulating anything. **These rows are invented, not measured**, and skip the recording pipeline. It refuses to run when `ENVIRONMENT=production`, and refuses if the range already holds rows, so running it twice cannot double the data. At most 24 hours, the longest `/metrics` window.

Both modes accept `--seed` for repeatable runs.

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
│   ├── schemas/                   Pydantic response models (demo, errors, metrics)
│   ├── services/demo_data.py      Fixed fake data for the demo routes
│   ├── services/metrics.py        /metrics queries, buckets and the snapshot
│   ├── services/request_recorder.py  Saves request_logs rows, best effort
│   ├── middleware/request_logging.py  Times /demo requests and hands them to the recorder
│   ├── services/simulation/       Simulated latency and failures
│   │   ├── profiles.py            Per-endpoint behaviour (data)
│   │   └── simulator.py           Decision (plan) and side effects (simulate)
│   └── api/
│       ├── dependencies.py        Shared dependencies (simulator, clock, session, settings)
│       ├── errors.py              One JSON error format and its handler
│       └── routers/               health.py, demo.py, metrics.py
├── migrations/                    Alembic revisions (schema history)
├── scripts/generate_traffic.py    Live demo traffic and synthetic backfill
├── tests/
├── pyproject.toml, uv.lock        Dependencies (locked)
├── Makefile                       Developer commands
└── CI.md                          Automated checks
```

Planned additions: `api/routers/analysis.py`, `services/{ai_analysis,ai_providers}.py`.

## Deployment assumptions

One backend instance, a managed PostgreSQL with persistent storage, and explicit CORS origins. Before public deployment: add access controls or server-enforced quotas to `/analyze`, use a restricted database role, and decide a retention and cleanup policy for `request_logs`.
