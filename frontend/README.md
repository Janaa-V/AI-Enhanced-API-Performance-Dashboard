# Frontend

## Purpose

The frontend is a React application built with Vite and TypeScript. It presents API performance data in a clear, interactive dashboard and connects users with AI-assisted observations.

## Technology

- React function components and hooks for component composition and local state.
- TanStack Query for metrics fetching, loading and error states, caching, and automatic refetching.
- Axios for typed HTTP requests to the FastAPI backend.
- Recharts for latency and status-code visualizations.
- CSS Modules or another lightweight CSS approach for component styling and responsive layouts.

## Minimal Learning Path

Before starting the dashboard phase, focus on the following topics in order:

1. JSX and components, including props and function components.
2. `useState` for local component state.
3. `useEffect` for mount-time and dependency-driven side effects, including data fetching.
4. Conditional rendering and list rendering with `{... ? ... : ...}` and `.map()` with stable keys.
5. Custom hooks for keeping repeated fetch and state logic out of individual components.
6. TanStack Query basics, including `useQuery`, `data`, `isLoading`, `isError`, and refetch intervals.

The first five topics are enough to begin. TanStack Query is optional at first but is recommended because it reduces manual fetching boilerplate and supports the live-dashboard behavior.

## Responsibilities

- Display key performance indicators for latency, request volume, and error rate.
- Render latency trends and status-code distribution using responsive Recharts components.
- Show recent requests in a sortable table.
- Display AI-generated insights with loading, success, empty, and error states.
- Retrieve metrics and analysis results from the FastAPI backend through a typed API layer and a metrics hook.
- Provide a clean layout that adapts to desktop and smaller screens.
- Keep components, models, API functions, hooks, and styling organized for future features.

## Planned Structure

```text
src/
├── api/
│   └── metrics.ts
├── components/
│   ├── DashboardOverview.tsx
│   ├── LatencyChart.tsx
│   ├── RequestsTable.tsx
│   └── InsightsPanel.tsx
├── hooks/
│   └── useMetrics.ts
├── models/
│   └── metrics.ts
├── App.tsx
└── main.tsx
```

`DashboardOverview.tsx` displays the main performance summary cards. `LatencyChart.tsx` uses a Recharts line chart for endpoint latency trends. `RequestsTable.tsx` displays recent request records with sortable columns. `InsightsPanel.tsx` presents AI-generated analysis and refresh controls.

## Data Flow

The application loads metrics from `GET /metrics`, maps the response into frontend models, and updates the dashboard components. TanStack Query manages loading, error, caching, and refetch behavior. When analysis is requested, the insights panel calls `POST /analyze`, displays a loading state while the backend processes the request, and renders the returned text or an actionable error message.

## Configuration

Use a `.env` file with `VITE_API_URL` pointing to the FastAPI backend. Axios should use that value as its base URL so local development and deployed environments can use different API addresses.

React Router can remain out of the initial single-page implementation and can be added later if the dashboard expands into multiple views.
