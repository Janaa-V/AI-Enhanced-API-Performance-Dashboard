# Frontend

A React dashboard that presents the backend's API performance data and AI-assisted observations.

> **Status: planned, not scaffolded.** The backend's `/metrics` contract is final (`backend/app/schemas/metrics.py`), so the folder structure, modules and build order below are settled. `POST /analyze` does not exist yet, so everything for AI insights is marked *(later)*.

## What it will show

- **KPI cards:** total requests, average and p95 latency, error rate and requests per minute.
- **Latency chart:** overall and per-endpoint p95 and average latency over the selected window.
- **Status-code chart:** distribution of HTTP responses, grouped by class (2xx, 4xx, 5xx).
- **Endpoint table:** the same statistics for each method and route.
- **Recent requests:** a sortable table.
- **AI insights panel** *(later)*: on-demand analysis with loading, success, empty and error states, labelled as AI-assisted.
- **Controls:** time-window selector, automatic refresh toggle, manual refresh and "updated N seconds ago".

Every view handles loading, empty and error states, and the layout adapts from desktop to phone width.

## Stack

| Concern | Choice |
| --- | --- |
| Framework | React function components and hooks, Vite, TypeScript (strict) |
| Data fetching | TanStack Query (caching, loading and error states, refetch interval) with Axios |
| API types | `openapi-typescript`, generated from the backend's OpenAPI schema |
| Charts | Recharts |
| Styling | CSS Modules and CSS custom properties for theme tokens; no UI framework |
| Testing | Vitest, React Testing Library, Mock Service Worker (MSW) |
| Tooling | ESLint, Prettier, `tsc --noEmit`, `npm audit`, GitHub Actions |

## Data flow

```mermaid
flowchart LR
    B["Backend OpenAPI schema"] -->|make openapi| J["frontend/openapi.json"]
    J -->|npm run generate:api| G["src/api/schema.gen.ts"]
    G --> M["src/models"]
    C["useDashboardControls<br/>(window, auto-refresh)"] --> H["useMetrics"]
    H --> A["api/metrics.ts<br/>fetchMetrics"] --> X["Axios client"] --> S["GET /metrics"]
    H -->|one MetricsResponse| App["App"]
    App --> K["KPI cards"] & L["Latency chart"] & SC["Status-code chart"] & T["Tables"]
```

1. `useMetrics` fetches `GET /metrics` once per refresh. **Every panel renders from that single response**, so the KPIs, charts and tables always describe the same snapshot, just as the backend computes them in one transaction. No component fetches on its own.
2. Types are generated from the backend's OpenAPI schema, so a contract change becomes a compile error instead of a runtime bug.
3. Raw values are formatted only at the edge (`lib/format.ts`): the API sends unrounded milliseconds, fractional rates, UTC timestamps and `null` for "nothing to measure", and the UI keeps them that way until display.
4. *(Later)* The insights panel calls `POST /analyze` only when the user asks, then shows the result or an actionable error.

## Folder structure

```text
frontend/
├── index.html
├── package.json, package-lock.json   Dependencies (locked; npm ci in CI)
├── vite.config.ts                    Dev server on port 5173 (matches the backend's default CORS origin), Vitest config
├── tsconfig.json                     strict, noUncheckedIndexedAccess
├── eslint.config.js, .prettierrc
├── .env.example                      VITE_API_URL=http://127.0.0.1:8000
├── openapi.json                      Backend contract snapshot (generated, committed)
└── src/
    ├── main.tsx                      React root, QueryClientProvider, global styles
    ├── App.tsx                       Page layout; calls useMetrics once and passes slices down
    ├── config.ts                     Reads and validates VITE_API_URL once, at startup
    │
    ├── api/                          HTTP only: no React, no formatting
    │   ├── schema.gen.ts             Generated from openapi.json; never edited by hand
    │   ├── client.ts                 Axios instance: base URL, timeout, error normalisation
    │   ├── errors.ts                 ApiError and toApiError()
    │   ├── metrics.ts                fetchMetrics(params, signal)
    │   └── analysis.ts               (later) requestAnalysis(params)
    │
    ├── models/                       Types and constants, no runtime dependencies
    │   ├── metrics.ts                Named aliases of generated types (MetricsResponse, Summary, TrendBucket, ...)
    │   └── windows.ts                Time-window presets and their bucket sizes
    │
    ├── hooks/                        The only layer that talks to TanStack Query
    │   ├── queryClient.ts            Shared QueryClient and retry policy
    │   ├── useMetrics.ts             useQuery wrapper: key, polling, previous data while switching windows
    │   ├── useDashboardControls.ts   Selected window and auto-refresh, mirrored in the URL query string
    │   ├── useNow.ts                 Ticking clock for "updated N seconds ago"
    │   └── useAnalysis.ts            (later) useMutation wrapper for POST /analyze
    │
    ├── lib/                          Pure functions, unit-tested, no React
    │   ├── format.ts                 Latency, percentages, counts, local times; null -> "—"
    │   ├── endpoints.ts              endpointKey() and endpointLabel(): "GET /demo/orders"
    │   ├── chartData.ts              Trend buckets -> Recharts rows; status codes -> classes
    │   └── sort.ts                   Stable, null-last comparators for the tables
    │
    ├── components/                   One folder per dashboard section; component, CSS Module and test side by side
    │   ├── layout/                   DashboardLayout, Header
    │   ├── controls/                 WindowSelector, RefreshControl
    │   ├── feedback/                 Panel, LoadingState, EmptyState, ErrorState, StaleDataBanner
    │   ├── kpis/                     KpiGrid, KpiCard
    │   ├── charts/                   LatencyChart, StatusCodeChart, ChartTooltip
    │   ├── tables/                   EndpointTable, RecentRequestsTable, SortableHeader
    │   └── insights/                 (later) InsightsPanel
    │
    ├── styles/
    │   ├── tokens.css                Colours, spacing and type as CSS variables; light and dark themes
    │   └── global.css                Reset and base element styles
    │
    └── test/
        ├── setup.ts                  Testing Library matchers, MSW server lifecycle
        ├── server.ts                 MSW handlers for /metrics (success, empty, 422, 503, network error)
        └── fixtures/metrics.ts       Typed MetricsResponse fixtures: busy, empty, one endpoint failing
```

## Module responsibilities

### Dependency rules

Imports flow in one direction, so each layer can be tested without the ones above it:

```text
components  ->  hooks  ->  api  ->  models
     \              \-> lib -/
      \-> lib, models
```

- `components/` never import from `api/` or TanStack Query; they receive data and callbacks as props. Only `App.tsx` and `InsightsPanel` call hooks that fetch.
- `api/` has no React imports and returns typed data or throws `ApiError`.
- `lib/` and `models/` are pure: no React, no Axios, no side effects.
- Only `api/schema.gen.ts` knows generated type names; the rest of the app imports from `models/`, so regeneration never ripples through components.

### `api/`

| Module | Responsibility |
| --- | --- |
| `client.ts` | One Axios instance with `baseURL` from `config.ts` and a 10-second timeout. A response interceptor turns every failure into an `ApiError`. |
| `errors.ts` | `ApiError` with a `kind` the UI can branch on: `network` (backend unreachable), `timeout`, `validation` (FastAPI `422`, keeps the first `msg`, such as the "too many buckets" hint), `server` (the shared `{ error: { code, message } }` body, such as `service_unavailable`) and `unknown`. Messages are safe to show; raw responses are never rendered. |
| `metrics.ts` | `fetchMetrics({ windowMinutes, bucketMinutes, recentLimit }, signal)` maps camelCase parameters to the query string and returns `MetricsResponse`. The `signal` lets TanStack Query cancel a request when the window changes. |
| `analysis.ts` | *(later)* `requestAnalysis({ windowMinutes })`. Sends no prompt or measurements; the server computes them. |

### `models/`

`metrics.ts` re-exports readable names (`MetricsResponse`, `Summary`, `EndpointMetrics`, `StatusCodeCount`, `TrendBucket`, `EndpointTrend`, `RecentRequest`, `ErrorResponse`) from the generated schema. Nullable fields stay `number | null`.

`windows.ts` holds the presets the selector offers. Each respects the backend's limits (1–1440 minutes, at most 288 buckets) and targets 12–60 points per chart:

| Label | `window_minutes` | `bucket_minutes` | Buckets |
| --- | --- | --- | --- |
| 5 min | 5 | 1 | 5 |
| 15 min | 15 | 1 | 15 |
| 1 hour (default) | 60 | 5 | 12 |
| 6 hours | 360 | 15 | 24 |
| 24 hours | 1440 | 60 | 24 |

A unit test asserts every preset stays within those limits, so a new preset cannot trigger a `422`.

### `hooks/`

| Hook | Contract |
| --- | --- |
| `useMetrics(window, { autoRefresh })` | Query key `['metrics', windowMinutes, bucketMinutes, recentLimit]`. Polls every 15 seconds when auto-refresh is on; TanStack Query pauses polling while the tab is hidden and refetches on focus. Keeps the previous window's data on screen while a new window loads. Retries network errors and `5xx` twice; never retries `4xx`. |
| `useDashboardControls()` | Selected preset and auto-refresh flag, read from and written to the URL query string (`?window=60&refresh=on`), so a view can be bookmarked or shared without adding a router. Unknown values fall back to the defaults. |
| `useNow(intervalMs)` | Current time, ticking, for relative "updated" labels. Kept separate so only that label re-renders every second. |
| `useAnalysis()` | *(later)* `useMutation` around `requestAnalysis`; only runs when the user clicks. |

`queryClient.ts` centralises defaults (`staleTime` 10 seconds, the retry rule above) so tests build the same client with retries off.

### `lib/`

| Module | Responsibility |
| --- | --- |
| `format.ts` | `formatLatency` (`842 ms`, `1.24 s`), `formatPercent` (fraction to `3.2 %`), `formatCount`, `formatRate` (per minute), `formatTime` and `formatRelative` in the viewer's local time zone via `Intl`. Every function renders `null` as "—", never `0`. |
| `endpoints.ts` | `endpointKey(method, endpoint)` for React keys, series names and colours, since `GET` and `POST /demo/orders` are different series. |
| `chartData.ts` | `toLatencyRows(trend, metric)` pivots `overall` and `by_endpoint` buckets into one row per bucket start (epoch milliseconds), leaving `null` where a bucket was empty so Recharts draws a gap instead of a false zero. `toStatusClasses(codes)` groups codes by class for colouring. |
| `sort.ts` | Comparators for the tables; `null` sorts last in both directions. |

### `components/`

| Folder | Components | Notes |
| --- | --- | --- |
| `layout/` | `DashboardLayout`, `Header` | CSS grid: KPIs across the top, charts in two columns on desktop and one on phones, tables full width. |
| `controls/` | `WindowSelector`, `RefreshControl` | Native `<select>` and `<button>` for keyboard and screen-reader support. `RefreshControl` shows "updated N seconds ago", the auto-refresh toggle and "Refresh now". |
| `feedback/` | `Panel`, `LoadingState`, `EmptyState`, `ErrorState`, `StaleDataBanner` | `Panel` is the frame every section uses; it picks loading, empty, error or content, so each section handles all four states the same way. If a refresh fails after a success, the last data stays visible under `StaleDataBanner` instead of being replaced by an error. |
| `kpis/` | `KpiGrid`, `KpiCard` | Takes `Summary`. Error rate counts `5xx` only; the card shows `4xx` separately, matching the backend's definition. |
| `charts/` | `LatencyChart`, `StatusCodeChart`, `ChartTooltip` | `LatencyChart` has a p95/average toggle and one line per endpoint plus "All endpoints"; the X axis is time with the window's local-time bounds. `StatusCodeChart` is a bar chart coloured by class. Both have a text summary for screen readers. |
| `tables/` | `EndpointTable`, `RecentRequestsTable`, `SortableHeader` | Client-side sorting with `aria-sort`; tables scroll horizontally inside their panel on narrow screens, never the page. |
| `insights/` | *(later)* `InsightsPanel` | Labelled "AI-assisted analysis". Shows the provider and generation time, and a clear message when AI is not configured on the server. |

### Error and empty states

| Situation | What the user sees |
| --- | --- |
| First load | Skeletons in each panel, sized like the content, so the layout does not jump |
| Window has no requests | `EmptyState` with the command that generates traffic (`make traffic`); KPIs show "—" |
| Backend unreachable (`network`, `timeout`) | `ErrorState` naming the configured API URL, with "Try again" |
| `503 service_unavailable` | The server's message ("The service is temporarily unavailable.") with "Try again" |
| `422` | The first validation message; this means a preset is wrong, so it also logs to the console |
| Refresh fails after data was shown | Last data stays, with `StaleDataBanner` ("Showing data from 10:42; refresh failed") |

## Contract and type generation

The backend already builds its OpenAPI schema without a database, so the contract can be exported offline:

1. **Backend:** a `make openapi` target writes `app.openapi()` to `frontend/openapi.json`.
2. **Frontend:** `npm run generate:api` runs `openapi-typescript openapi.json -o src/api/schema.gen.ts`.
3. **CI:** regenerates both and fails if `git diff` is not empty, so a backend change that alters the contract cannot merge without the frontend seeing it.

Both generated files are committed, so the frontend builds without a running backend.

## Configuration

`VITE_API_URL` sets the backend base URL, so local and deployed environments differ only by configuration. `config.ts` validates it once at startup and fails with a clear message if it is missing or not a URL. It is public: never place secrets in `VITE_*` variables. AI keys live only in the backend.

The Vite dev server runs on port 5173, the backend's default `CORS_ORIGINS` entry, so local development needs no proxy. A router is deliberately left out; the URL query string holds the only state worth sharing, and a router can be added if the dashboard grows beyond one view.

## Testing

| Layer | How |
| --- | --- |
| `lib/`, `models/` | Plain Vitest unit tests: formatting edge cases (`null`, `0`, sub-millisecond, over one second), pivoting trends with empty buckets, preset limits |
| `api/` | MSW returns each backend response (success, empty, `422`, `503`, network failure); assert the typed result or the `ApiError` kind |
| `hooks/` | `renderHook` with a test `QueryClient`: query keys, polling on and off, no retry on `4xx`, previous data kept while switching windows |
| `components/` | Testing Library with the typed fixtures: each panel's four states, sorting, keyboard use of the controls |
| `App` | One integration test per fixture: busy, empty and failing backend render the right states end to end |

Fixtures are typed as `MetricsResponse`, so a contract change breaks them at compile time too.

## Build order

Each step is one reviewable pull request that leaves the app working.

| Step | Scope | Done when |
| --- | --- | --- |
| 1. Scaffold | Vite, TypeScript, ESLint, Prettier, Vitest, `config.ts`, `styles/`, a `frontend-ci.yml` workflow (install, lint, format, types, tests, build, audit) | CI is green on an empty page |
| 2. Contract | `make openapi`, `openapi.json`, `schema.gen.ts`, `models/`, `api/` with tests, the freshness check in CI | `fetchMetrics` is typed end to end and tested against MSW |
| 3. Pure logic | `lib/` and `models/windows.ts` with unit tests | Formatting and chart pivots are covered, including `null` and empty buckets |
| 4. Data and controls | `hooks/`, `controls/`, `feedback/`, `layout/`, `App.tsx` | Switching windows and auto-refresh work against the real backend; every state renders |
| 5. KPIs and charts | `kpis/`, `charts/` | Charts match `/metrics` output for a generated traffic run |
| 6. Tables | `tables/` | Sorting, `aria-sort` and narrow-screen scrolling work |
| 7. Polish | Dark theme, responsive checks at phone width, accessibility pass, README screenshots | Usable at 360 px wide and by keyboard only |
| 8. AI insights *(later)* | `api/analysis.ts`, `useAnalysis`, `insights/` | Starts once `POST /analyze` exists in the backend |
