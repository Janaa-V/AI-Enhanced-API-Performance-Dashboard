# Frontend

A React dashboard that presents the backend's API performance data and AI-assisted observations.

> **Status: not started.** This document describes the planned design. It starts once the backend's `/metrics` response schemas are defined.

## What it will show

- **KPI cards:** total requests, average latency, error rate and requests per minute.
- **Latency chart:** per-endpoint trend over the selected window.
- **Status-code chart:** distribution of HTTP responses.
- **Recent requests:** a sortable table.
- **AI insights panel:** on-demand analysis with loading, success, empty and error states, labelled as AI-assisted.
- **Controls:** time-window selector and automatic refresh.

Every view handles loading, empty and error states, and the layout adapts from desktop to phone width.

## Stack

| Concern | Choice |
| --- | --- |
| Framework | React function components and hooks, Vite, TypeScript |
| Data fetching | TanStack Query (caching, loading and error states, refetch interval) with Axios |
| Charts | Recharts |
| Styling | CSS Modules or another lightweight approach |

## Data flow

1. `GET /metrics` is fetched by a `useMetrics` hook; TanStack Query manages caching and polling, and pauses when the tab is hidden.
2. Response types are generated from the backend's OpenAPI schema, so a contract change becomes a compile error instead of a runtime bug.
3. The insights panel calls `POST /analyze` only when the user asks, then shows the result or an actionable error.

## Planned structure

```text
src/
├── api/          Typed HTTP layer (metrics, analysis)
├── components/   DashboardOverview, LatencyChart, RequestsTable, InsightsPanel
├── hooks/        useMetrics
├── models/       Generated and derived types
├── App.tsx
└── main.tsx
```

## Configuration

`VITE_API_URL` sets the backend base URL, so local and deployed environments differ only by configuration. It is public: never place secrets in `VITE_*` variables. AI keys live only in the backend.

A router is deliberately left out of the first version; it can be added if the dashboard grows beyond one view.
