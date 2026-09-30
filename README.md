# AI-Enhanced API Performance Dashboard

A full-stack observability project: simulated API traffic is recorded in PostgreSQL and aggregated into latency, throughput and error metrics. A React dashboard is next; plain-English summaries from an LLM are planned.

> **Status: backend complete, frontend in progress.** The backend records every demo request, serves aggregated metrics at `GET /metrics` and includes a traffic generator (release `v0.2.0-backend`). The React dashboard is scaffolded with its tooling, theme and CI; its panels are next. AI insights are planned. See [Status](#status).

## Built so far

- **Backend engineering:** async FastAPI, SQLAlchemy 2 with Psycopg 3, Pydantic-validated configuration, Alembic migrations.
- **Request-level instrumentation:** simulated `/demo/*` endpoints with configurable latency and failure rates, and middleware that records endpoint, method, status code and latency for every call.
- **Metrics API:** `GET /metrics` returns summary, per-endpoint and status-code aggregates with p95 latency, latency trends in UTC-aligned buckets and recent requests, all read from one consistent snapshot and tested against a real PostgreSQL database. Measured at 17 ms for a one-hour window over 100,000 rows.
- **Traffic generator:** one command sends realistic, bounded live traffic (including deliberate client errors); a separate backfill mode writes clearly labelled synthetic history.
- **Engineering hygiene:** locked dependencies, static typing, linting, dependency audit, secret scanning, and CI that runs all of these plus unit and integration tests.

## Planned

- **React dashboard:** typed React with TanStack Query and Recharts, including loading, empty and error states.
- **AI insights:** an LLM that only ever sees server-computed aggregates, sits behind a swappable interface, and stays optional.

## How it works

The diagram shows the full design; [Status](#status) lists which parts are built.

```mermaid
flowchart LR
    T["Traffic generator"] --> D["/demo/* endpoints"]
    subgraph API ["FastAPI backend"]
        D --> M["Request-logging middleware"]
        M --> DB[("PostgreSQL")]
        Q["GET /metrics"] --> DB
        A["POST /analyze"] --> Q
        A --> P["AI provider interface"]
    end
    P --> L["Gemini or Groq"]
    UI["React dashboard"] --> Q
    UI --> A
```

1. Five mock endpoints (users, orders, products, search, reports) respond with configurable delays and failure rates.
2. Middleware records endpoint, method, status code, latency and timestamp for every call.
3. `/metrics` aggregates a time window into KPIs, per-endpoint stats, status codes, latency trends and recent requests.
4. *(Planned)* `/analyze` will send that aggregate summary to an LLM and return concise observations and next steps to investigate.

## Design decisions

| Decision | Reason |
| --- | --- |
| Only `/demo/*` traffic is measured | Dashboard polling, health checks and AI calls must not inflate the workload being observed |
| Aggregation happens in SQL, with one fixed window end per response | Correct, consistent snapshots; no averaging of averages |
| UTC timestamps, latency from a monotonic clock | Results do not depend on time zones or clock adjustments |
| AI receives aggregates only; clients cannot send prompts | Bounds cost and abuse, and keeps raw data private |
| AI sits behind a provider interface | Gemini and Groq are interchangeable without touching the rest of the backend |
| Metrics work without AI configured | AI is an enhancement, never a dependency |
| Alembic migrations, no schema changes at startup | Reproducible, reviewable database changes |

## AI-assisted insights (planned)

Not built yet; this is the design. No model will be trained or hosted. The backend will send a structured summary of recent metrics to a free-tier LLM API and ask practical questions: which endpoints are slower than expected, whether errors are concentrated in one service, what a bottleneck might look like, and what small step to try first. The prompt will separate observations from hypotheses and will not claim a root cause from latency alone. The dashboard will label the output as AI-assisted analysis, not autonomous monitoring.

## Status

| Area | State |
| --- | --- |
| Service foundation: config, async database connection, `/health`, tooling, CI | Done |
| Request model and migration | Done |
| Simulation engine (latency and failure profiles) | Done |
| Demo routes (`GET /demo/*`) | Done |
| `POST /demo/orders` (validated create) | Done |
| Request logging middleware, wired into the app | Done |
| `/metrics` response schemas and SQL queries (summary, per endpoint, status codes, latency trends, recent requests) | Done |
| `/metrics` endpoint (bounded parameters, read-only snapshot, performance-checked) | Done |
| Traffic generator for demos (live and synthetic backfill) | Done |
| React dashboard foundation: Vite and TypeScript scaffold, lint, format and test tooling, Holi theme tokens, CI | Done |
| React dashboard panels (KPIs, charts, tables, controls) | Next |
| AI insights (`/analyze`) | Planned |
| Deployment on free-tier services | Planned |

Not in scope for the first release: authentication, alerting, monitoring real production APIs, model training, WebSockets and distributed storage.

## Tech stack

| Layer | Technology |
| --- | --- |
| Backend | Python 3.12–3.14, FastAPI, SQLAlchemy (async), Psycopg 3, Pydantic |
| Database | PostgreSQL 18, Alembic migrations |
| Frontend | React 19, Vite, TypeScript, CSS Modules; TanStack Query, Axios and Recharts for the panels in progress |
| AI (planned) | Google Gemini or Groq, called from the backend only |
| Tooling | uv, Ruff, Pyright, pytest, pip-audit, ESLint, Stylelint, Prettier, Vitest, npm audit, pre-commit, gitleaks, GitHub Actions |

## Repository layout

```text
backend/     FastAPI service, tests and tooling      -> backend/README.md
frontend/    React dashboard (in progress)           -> frontend/README.md
```

## Quick start

Requires [uv](https://docs.astral.sh/uv/) and Docker. Full instructions, including the PostgreSQL container, are in the [backend guide](./backend/README.md#quick-start).

```bash
cd backend
make setup      # install dependencies, create .env (then set DB_PASSWORD)
make migrate    # create the database tables
make run        # http://127.0.0.1:8000/docs
make traffic    # in a second terminal: 60 s of demo traffic
make check      # lint, format, types, tests
```

Then open `http://127.0.0.1:8000/metrics?window_minutes=5&bucket_minutes=1`.

## Documentation

- [Backend](./backend/README.md): setup, configuration, data model, API contracts, testing, milestones
- [Frontend](./frontend/README.md): planned architecture, folder structure, modules and build order
- [Continuous integration](./backend/CI.md): checks, local verification, branch protection

## License

[MIT](./LICENSE)
