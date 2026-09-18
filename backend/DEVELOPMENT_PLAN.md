# Backend development plan

## Requirements and current state

The backend uses Python, FastAPI, and PostgreSQL. The initial scaffold includes uv configuration, validated settings, an asynchronous SQLAlchemy/Psycopg connection, health checks, and connection lifecycle tests. Request storage and dashboard features remain to be implemented.

Local PostgreSQL runs through `~/Documents/os-services/compose.yaml` at `127.0.0.1:5432`, with database `performance_dashboard`, role `dashboard`, and a persistent Docker named volume. The backend uses `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, and `DB_PASSWORD`; see [environment configuration](./ENVIRONMENT.md) for secret handling.

The application must simulate API requests, persist request-level performance data, expose dashboard metrics, and generate AI-assisted observations from those metrics. Frontend development follows once the backend contracts are usable.

## Proposed implementation decisions

These decisions fill gaps in the existing requirements and can be adjusted during implementation:

- Use asynchronous FastAPI route handlers and `asyncio.sleep` for simulated delays, so simulation does not block other requests.
- Use SQLAlchemy with its asynchronous PostgreSQL driver (`psycopg`). Manage application resources through FastAPI lifespan and use separate sessions for writes and metrics queries.
- Validate configuration and API contracts with Pydantic. Load local environment settings without committing secrets.
- Store timestamps in UTC and measure elapsed request time using a monotonic clock. Express latency in milliseconds and error rates as percentages from 0 to 100.
- Monitor only requests under `/demo/`. Dashboard polling, health checks, and AI requests must not inflate the measured workload.
- Treat HTTP statuses of 400 or higher as errors. Count a completed request after its response is produced; simulated failures must be recorded too.
- Default to a 60-minute reporting window with a supported range of 1–1440 minutes. Use one fixed window end per metrics response and include its boundaries in the response.
- Keep simulation controllable through configuration, with automatic traffic generation disabled by default. Provide a local traffic script for reproducible demonstrations.
- Put AI calls behind a provider interface. Select and implement one of the documented providers, Gemini or Groq, in the AI milestone after checking its current API documentation.

## Data model

Start with one `request_logs` table:

| Field | Purpose |
| --- | --- |
| `id` | PostgreSQL bigint identity primary key |
| `endpoint` | Normalized route path, such as `/demo/users` |
| `method` | HTTP method |
| `status_code` | Response status |
| `latency_ms` | Double-precision elapsed duration with a nonnegative constraint |
| `timestamp` | Timezone-aware PostgreSQL timestamp (`TIMESTAMPTZ`), supplied in UTC |

Index timestamps and endpoint/timestamp lookups. Store route paths without query strings, bodies, or credentials. Use Alembic migrations when request models are introduced; avoid implicit schema changes at startup.

Use short PostgreSQL transactions and a connection pool to support reads while traffic is being recorded. Logging failures should be reported through application logs without replacing the original endpoint response.

## API contracts

### `GET /health`

Return service readiness, including a lightweight database check. Return a service-unavailable response if persistence is unavailable. Exclude this route from request metrics.

### Demo routes

Expose `GET /demo/users`, `/demo/orders`, `/demo/products`, `/demo/search`, and `/demo/reports`. Each route returns a small synthetic payload and has its own configured latency range and failure probability. Reports should typically take longer than simple reads. Failures return a consistent JSON error body and an HTTP error status.

Use deterministic overrides in tests to verify successes, delays, and failures without depending on random outcomes.

### `GET /metrics`

Query parameters:

- `window_minutes`: default 60, minimum 1, maximum 1440.
- `bucket_minutes`: default 5, minimum 1, maximum 60.
- `recent_limit`: default 20, minimum 1, maximum 100.

Return:

- `window`: UTC `start`, `end`, and bucket size.
- `summary`: total requests, error count, error rate, average latency, and requests per minute over the selected window.
- `endpoints`: the same aggregates grouped by endpoint and method.
- `status_codes`: counts grouped by HTTP status code.
- `latency_trend`: UTC time buckets with overall and per-endpoint average latency, request counts, and error counts.
- `recent_requests`: newest request records first, with ID as a tie breaker.

Use a half-open interval `[start, end)` for filtering and clip edge buckets to the selected window. Empty datasets return zero counts and rates, empty endpoint/status/recent arrays, and trend buckets with zero counts and null latency averages. Overall average latency is null when there are no requests. Calculate overall averages from request totals rather than averaging endpoint averages.

### `POST /analyze`

Accept an optional JSON body containing `window_minutes`, with the same default and bounds as `/metrics`. Obtain the metrics on the server; do not accept arbitrary prompts or client-supplied measurements.

Return the reporting window, provider, generation timestamp, and analysis text. Send only aggregate metrics to the provider. Instruct it to distinguish observations from hypotheses and avoid claiming a root cause from latency alone.

For an empty window, return an explicit `no_data` result without a provider call. For missing AI configuration, provider timeouts, rate limits, and invalid responses, return documented, actionable errors without exposing credentials or upstream internals. Configure a timeout and bound provider input/output size. Add a short cache and a single in-flight request per reporting window to reduce repeated calls.

## Development sequence

| Milestone | Work | Completion criteria |
| --- | --- | --- |
| 1. Service foundation | Dependency configuration, application package, settings, lifespan, CORS, database schema, `/health`, `.env.example`, local setup instructions | Service starts locally, connects to PostgreSQL, and reports readiness; invalid settings fail clearly |
| 2. Simulation and recording | Five demo routes, asynchronous delays, configurable failures, request logging middleware | Successful and failed demo requests create accurate records; dashboard routes create none |
| 3. Dashboard metrics | Typed response schemas, aggregate queries, time buckets, recent requests, validated query parameters | Known records produce correct aggregates; empty windows and UTC boundaries behave consistently |
| 4. Demonstration workflow | Local traffic script with bounded duration/concurrency and varied endpoint selection | A documented command produces enough data for summary cards, charts, and a request table |
| 5. AI insights | Provider interface, one provider adapter, structured summary/prompt, timeout/error handling, caching | Mocked provider tests pass; configured credentials enable a manual live check; metrics work without credentials |
| 6. Frontend handoff | Document response examples, error contracts, startup and demo commands, deployment settings | Frontend can consume stable metrics and analysis contracts without inferring field meanings |

Milestones 1–4 form the first usable backend. Implement them before adding live AI calls.

## Planned structure

```text
backend/
  pyproject.toml
  uv.lock
  Makefile
  .env.example
  README.md
  alembic.ini                 # Planned with request models
  migrations/                # Planned Alembic revisions
  app/
    main.py
    config.py
    database.py
    models.py
    schemas.py
    middleware/request_logging.py
    api/routers/health.py
    api/routers/demo.py
    api/routers/metrics.py
    api/routers/analysis.py
    services/metrics_service.py
    services/ai_analysis.py
    services/ai_providers.py
  scripts/generate_traffic.py
  tests/
```

## Verification

Use pytest with an HTTP test client and isolated PostgreSQL test databases for query integration and mocks for connection lifecycle checks. Focus tests on behavior:

- Request logging includes successes and failures, has nonnegative latency, and excludes monitoring routes.
- Metrics match a known dataset across endpoints, statuses, empty windows, ordering, and time boundaries.
- Query and request validation rejects unsupported values.
- Provider integration is tested with mocked responses, including timeouts, rate limits, malformed output, and missing configuration.
- A local smoke check starts the service, generates traffic, and reads metrics.

Unit tests must not require a running database, AI credentials, or external provider calls. Query integration tests will use a dedicated PostgreSQL test database, separate from development data. Apply migrations to that database and isolate fixtures between tests. Record the executed checks in the implementation handoff.

## Initial scope and deployment assumptions

Start with one backend instance and a local PostgreSQL 18 Compose service in `~/Documents/os-services`, with a persistent named volume. Configure allowed frontend origins explicitly. Ignore local environment files, databases, virtual environments, and generated caches in Git.

Keep authentication, alerts, real production API monitoring, model training, WebSockets, and distributed storage outside the first release. Do not expose unrestricted AI calls publicly; before public deployment, add access controls or server-enforced quotas. Choose a managed PostgreSQL service or a database host with persistent storage for deployment. Decide retention and cleanup policy before running traffic continuously.
