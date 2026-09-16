# Backend

## Purpose

The backend is a Python and FastAPI service that provides the dashboard's data, simulated API traffic, persistence, metrics aggregation, and AI-assisted analysis.

## Responsibilities

- Expose mock endpoints that simulate common backend services with varied latency and occasional errors.
- Capture request metadata, including endpoint, HTTP method, status code, latency, and timestamp.
- Persist request logs in SQLite.
- Aggregate request data into endpoint-level metrics, status-code breakdowns, latency trends, and recent-request records.
- Expose metrics and analysis endpoints for the React frontend.
- Call an external AI provider from an isolated service module and return concise performance observations.
- Provide configuration for database location, AI credentials, CORS, and analysis time windows.

## Planned API

- `GET /metrics` returns aggregated performance data for the selected time window.
- `POST /analyze` accepts an optional time window and returns an AI-generated summary of recent metrics.
- Mock endpoints are grouped under a dedicated demo route prefix so monitoring traffic remains separate from dashboard API routes.

## Core Modules

- `app/main.py` initializes the FastAPI application, database, middleware, and routers.
- `app/database.py` manages the SQLite connection and schema.
- `app/models.py` defines database models.
- `app/schemas.py` defines request and response contracts.
- `app/middleware/request_logging.py` records request performance data.
- `app/services/metrics_service.py` calculates aggregates and trends.
- `app/services/ai_analysis.py` builds prompts, calls the selected AI provider, and validates responses.
- `app/api/routers/` contains endpoint handlers for mock traffic, metrics, and insights.

## Local Configuration

The backend will use environment-based configuration for the SQLite path and AI provider credentials. A `.env.example` file will document required variables without storing secrets.
