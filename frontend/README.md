# Frontend

A React dashboard that presents the backend's API performance data and AI-assisted observations.

> **Status: dashboard complete.** Steps 1 to 7 of the [build order](#build-order) are done: the typed API contract, pure formatting and chart-data functions, data hooks and controls, KPI cards, latency and status-code charts, sortable tables, and a polish pass (both themes at 360, 768 and 1280 px with no sideways page scroll, no axe-core WCAG 2.1 AA violations, and every control reachable and visibly focused by keyboard). The backend's `/metrics` contract is final (`backend/app/schemas/metrics.py`). `POST /analyze` does not exist yet, so everything for AI insights is marked *(later)*.

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
| Tooling | ESLint, Stylelint, Prettier, `tsc --noEmit`, `npm audit`, GitHub Actions |

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
├── Makefile                          Every task as a make target, like backend/Makefile (make help)
├── index.html
├── package.json, package-lock.json   Dependencies (locked; npm ci in CI)
├── vite.config.ts                    Dev server on port 5173 (matches the backend's default CORS origin), Vitest config
├── tsconfig.json                     strict, noUncheckedIndexedAccess
├── eslint.config.js, stylelint.config.js, .prettierrc.json
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
    │   ├── useSortState.ts           A table's sorted column and direction
    │   ├── useTheme.ts               Dark by default, or light or system; sets data-theme on <html>
    │   ├── useChartColors.ts         Resolved token colours for Recharts, re-read on theme change
    │   ├── usePrefersReducedMotion.ts  Switches chart animations off for reduced motion
    │   └── useAnalysis.ts            (later) useMutation wrapper for POST /analyze
    │
    ├── lib/                          Pure functions, unit-tested, no React
    │   ├── format.ts                 Latency, percentages, counts, local times; null -> "—"
    │   ├── endpoints.ts              endpointKey(): "GET /demo/orders"
    │   ├── chartData.ts              Trend buckets -> Recharts rows; status codes -> classes
    │   ├── series.ts                 assignSeriesSlots(): each endpoint's fixed colour slot
    │   └── sort.ts                   Stable, null-last comparators for the tables
    │
    ├── components/                   One folder per dashboard section; component, CSS Module and test side by side
    │   ├── layout/                   DashboardLayout, Header, ThemeToggle
    │   ├── controls/                 WindowSelector, RefreshControl, SegmentedControl
    │   ├── feedback/                 Panel, LoadingState, EmptyState, ErrorState, StaleDataBanner
    │   ├── kpis/                     KpiGrid, KpiCard
    │   ├── charts/                   LatencyPanel, LatencyChart, StatusCodeChart, ChartTable
    │   ├── tables/                   EndpointTable, RecentRequestsTable, SortableHeader
    │   └── insights/                 (later) InsightsPanel
    │
    ├── styles/
    │   ├── tokens.css                Design tokens as CSS variables; light and dark themes; reduced motion
    │   ├── global.css                Small reset, base typography and focus outline
    │   ├── shared.module.css         Patterns reused with composes: (visuallyHidden, button, numeric)
    │   └── table.module.css          The data tables' shared look
    │
    └── test/
        ├── setup.ts                  Testing Library matchers, MSW server lifecycle, page-state reset
        ├── render.tsx                renderWithClient and renderHookWithClient: a fresh QueryClient, retries off
        ├── server.ts                 MSW handlers for /metrics (success, empty, 422, 503, network error)
        └── fixtures/metrics.ts       Typed MetricsResponse fixtures: busy and empty; more are added with the panels that need them
```

## Module responsibilities

### Dependency rules

Imports flow in one direction, so each layer can be tested without the ones above it:

```text
components  ->  hooks  ->  api  ->  models
     \              \-> lib -/
      \-> lib, models
```

- `components/` never import from `api/` or TanStack Query; they receive data and callbacks as props. `ErrorState` takes a plain `{ kind, message }`, which an `ApiError` satisfies, rather than importing the class. Only `App.tsx` and `InsightsPanel` call hooks that fetch.
- `api/` has no React imports and returns typed data or throws `ApiError`.
- `lib/` and `models/` are pure: no React, no Axios, no side effects.
- Only `api/schema.gen.ts` knows generated type names; the rest of the app imports from `models/`, so regeneration never ripples through components.

### `api/`

| Module | Responsibility |
| --- | --- |
| `client.ts` | One Axios instance with `baseURL` from `config.ts` and a 10-second timeout. A response interceptor turns every failure into an `ApiError`, except cancellation, which TanStack Query triggers on purpose and handles itself. |
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
| `useMetrics(preset, { autoRefresh })` | Query key `['metrics', windowMinutes, bucketMinutes]`; the recent-requests limit is left at the backend's default (20). Polls every 15 seconds when auto-refresh is on; TanStack Query pauses polling while the tab is hidden and refetches on focus. Keeps the previous window's data on screen while a new window loads. Retries network errors and `5xx` twice; never retries `4xx`. |
| `useDashboardControls()` | Selected preset and auto-refresh flag, read from and written to the URL query string (`?window=60&refresh=on`), so a view can be bookmarked or shared without adding a router. Unknown values fall back to the defaults. |
| `useNow(intervalMs)` | Current time, ticking, for relative "updated" labels. Kept separate so only that label re-renders every second. |
| `useAnalysis()` | *(later)* `useMutation` around `requestAnalysis`; only runs when the user clicks. |

`queryClient.ts` centralises defaults (`staleTime` 10 seconds, the retry rule above) so tests build the same client with retries off. It also registers `ApiError` as TanStack Query's error type, so `query.error` is typed without casts.

`useTheme` is backed by a small inline script in `index.html` that applies the saved theme, or dark when nothing valid is saved, before the first paint, so no viewer sees the wrong theme flash while the app loads. A test runs that script against every stored value, so it cannot drift from `useTheme`.

### `lib/`

| Module | Responsibility |
| --- | --- |
| `format.ts` | `formatLatency` (`4.2 ms`, `842 ms`, `1.24 s`), `formatPercent` (fraction to `3.2 %`), `formatCount` (`1,234`), `formatRate` (`8.0`, with the unit in the label beside it), `formatTime` (24-hour, `15:34:05`, in the viewer's time zone) and `formatRelative` (`12 s ago`). Numbers use one fixed locale (`en-US`) so they read the same everywhere. Every function renders `null` as "—", never `0`, and a tiny non-zero value as `< 0.1 ms` or `< 0.1 %`, never as zero. |
| `endpoints.ts` | `endpointKey({ method, endpoint })`, such as `GET /demo/orders`, for React keys, series names, colours and labels, since `GET` and `POST /demo/orders` are different series. |
| `chartData.ts` | `toLatencyRows(trend, metric)` pivots `overall` and `by_endpoint` buckets into one row per bucket start (epoch milliseconds), leaving `null` where a bucket was empty so Recharts draws a gap instead of a false zero. Returns the rows and the endpoint series keys; every row carries every key. `toStatusClasses(codes)` groups codes by class (2xx, 4xx, 5xx), with each class's total, its codes for the tooltip, and a tone (`success`, `warning`, `danger`) for colouring. |
| `sort.ts` | `sortBy(items, value, direction)` returns a sorted copy; `null` sorts last in both directions and ties keep their order. Timestamps are sorted as numbers, since ISO strings with and without fractional seconds do not sort correctly as text. |

### `components/`

| Folder | Components | Notes |
| --- | --- | --- |
| `layout/` | `DashboardLayout`, `Header` | CSS grid: KPIs across the top, charts in two columns on desktop and one on phones, tables full width. |
| `controls/` | `WindowSelector`, `RefreshControl`, `SegmentedControl` | Native `<select>`, `<button>` and radio buttons for keyboard and screen-reader support. `SegmentedControl` serves both the theme toggle and the p95/average switch. `RefreshControl` shows "updated N seconds ago", the auto-refresh toggle and "Refresh now". |
| `feedback/` | `Panel`, `LoadingState`, `EmptyState`, `ErrorState`, `StaleDataBanner` | `Panel` is the frame every section uses; it picks loading, empty, error or content, so each section handles all four states the same way. If a refresh fails after a success, the last data stays visible under `StaleDataBanner` instead of being replaced by an error. |
| `kpis/` | `KpiGrid`, `KpiCard` | Takes `Summary`: requests, requests per minute, error rate, average and p95 latency, as a `<dl>`. Error rate counts `5xx` only; the card shows `4xx` separately, matching the backend's definition. As many columns as the panel fits; values step down a size in a narrow panel (container query). |
| `charts/` | `LatencyPanel`, `LatencyChart`, `StatusCodeChart`, `ChartTable` | `LatencyPanel` holds the p95/average switch. `LatencyChart` draws one 2 px line per endpoint plus "All endpoints" in the text colour; empty buckets are gaps, and a bucket between two empty ones gets a dot. The X axis spans the window in local time; the tooltip lists every series at the hovered bucket, highest first. `StatusCodeChart` draws one thin bar per code, coloured by class and labelled with a symbol (✓ 2xx, ! 4xx, ✕ 5xx), with the class totals as text above. Legends are HTML beside the chart. Each chart has a screen-reader summary and a collapsed `ChartTable` with every value, which the lighter light-mode series need (see the palette validation). |
| `tables/` | `EndpointTable`, `RecentRequestsTable`, `SortableHeader` | Client-side sorting with `aria-sort` on each header; a second click flips the direction, and a new column starts in its natural direction (numbers largest first, text A to Z). `null` sorts last both ways. The endpoint table starts slowest first (p95) and shows each endpoint's latency-chart colour beside its name; recent requests start newest first, with times sorted as instants and error statuses marked ✕ 5xx or ! 4xx. Tables scroll horizontally inside their panel on narrow screens, never the page, and the scroll area is focusable for keyboard users. |
| `insights/` | *(later)* `InsightsPanel` | Labelled "AI-assisted analysis". Shows the provider and generation time, and a clear message when AI is not configured on the server. |

### Error and empty states

| Situation | What the user sees |
| --- | --- |
| First load | Skeletons in each panel, sized like the content, so the layout does not jump |
| First load fails | One `ErrorState` for the page instead of one per panel, since every panel reads the same response |
| Window has no requests | `EmptyState` with the command that generates traffic (`make traffic`); KPIs show "—" |
| Backend unreachable (`network`, `timeout`) | `ErrorState` naming the configured API URL, with "Try again" |
| `503 service_unavailable` | The server's message ("The service is temporarily unavailable.") with "Try again" |
| `422` | The first validation message; this means a preset is wrong, so it also logs to the console |
| Refresh fails after data was shown | Last data stays, with `StaleDataBanner` ("Showing data from 10:42; refresh failed") |

## Styling

CSS Modules for each component and one shared set of design tokens as CSS custom properties. Vite supports both without extra dependencies, class names are scoped to their component, styles sit next to the component they belong to, and nothing runs at runtime.

| Option | Why not |
| --- | --- |
| Tailwind | Another tool and long class lists in markup; charts still need colours in JavaScript |
| CSS-in-JS (styled-components, Emotion) | Runtime cost, and the ecosystem is moving away from it |
| Component library (MUI, Chakra) | Heavy, generic look, and fights custom chart styling |

### Files

| File | Contents |
| --- | --- |
| `styles/tokens.css` | Every colour, space, size, radius, shadow and duration, for both themes. Under `prefers-reduced-motion` it sets `--duration-fast` to `0ms`, and every transition uses that token, so no `!important` override is needed |
| `styles/global.css` | Small reset, base typography, `:focus-visible` outline; the only place global selectors are allowed |
| `components/**/X.module.css` | One module per component, imported as `styles` and used as `styles.cardValue` |

### Design tokens

Tokens are named by purpose, not by value (`--color-text-muted`, never `--gray-500`), so a theme only redefines variables and components never change.

| Group | Tokens |
| --- | --- |
| Colour | `--color-bg`, `--color-surface`, `--color-surface-raised`, `--color-border`, `--color-text`, `--color-text-muted`, `--color-axis`, `--color-grid`, `--color-accent`, `--color-accent-text`, `--color-on-accent` |
| Status | `--color-success`, `--color-warning`, `--color-danger`, each with a `-text` variant for words and a `-subtle` background variant |
| Chart series | `--color-series-1` … `--color-series-8`, distinguishable in both themes and for common colour-vision deficiencies |
| Space | `--space-1` … `--space-8` on a 4 px base, in `rem` |
| Type | Five sizes (`--text-xs` … `--text-xl`), system font stack, no web font |
| Other | `--radius-sm`, `--radius-md`, `--shadow-panel`, `--duration-fast` |

Numbers in tables, tooltips and the refresh label use `font-variant-numeric: tabular-nums`, so digits line up and do not shift on refresh. The large KPI values keep proportional figures, which read better at that size.

### Palette: Holi

The theme is named after the festival of colours: eight saturated hues on a warm cream day theme and a near-black night theme. Every value below is final and goes into `tokens.css` as written.

**Neutrals and accent**

| Token | Light | Dark |
| --- | --- | --- |
| `--color-bg` (page) | `#fbf0e4` | `#0b0b0c` |
| `--color-surface` (panels, cards) | `#fffaf3` | `#141416` |
| `--color-surface-raised` (tooltips, menus) | `#ffffff` | `#1c1c1f` |
| `--color-border` | `#e7dccd` | `#2a2a2e` |
| `--color-text` | `#1f1633` | `#f5f5f4` |
| `--color-text-muted` | `#62577a` | `#b4b2ad` |
| `--color-axis` (ticks, axis labels) | `#8a7f9e` | `#85837e` |
| `--color-grid` (chart gridlines) | `#efe4d6` | `#1f1f22` |
| `--color-accent` (buttons, focus ring) | `#c8007f` | `#ff5cc0` |
| `--color-accent-text` (links, selected text) | `#b3006f` | `#ff7ccd` |
| `--color-on-accent` (text on accent) | `#ffffff` | `#141416` |

A thin decorative strip across the top of the header runs through series 1, 8, 4, 2 and 7 (fuchsia, tangerine, marigold, lime, turquoise). It carries no meaning, so it is exempt from contrast rules.

**Chart series**, assigned in this fixed order:

| Slot | Colour | Light | Dark | Used for |
| --- | --- | --- | --- | --- |
| 1 | Fuchsia | `#e10095` | `#eb009b` | `GET /demo/users` |
| 2 | Lime | `#84c900` | `#6da600` | `GET /demo/orders` |
| 3 | Azure | `#007dd6` | `#008ff4` | `POST /demo/orders` |
| 4 | Marigold | `#efa200` | `#c78600` | `GET /demo/products` |
| 5 | Pink | `#ff5799` | `#ff288c` | `GET /demo/search` |
| 6 | Violet | `#8700ec` | `#9c44ff` | `GET /demo/reports` |
| 7 | Turquoise | `#00beaf` | `#00a99b` | Spare |
| 8 | Tangerine | `#f56600` | `#e25e00` | Spare |

The "All endpoints" line uses `--color-text`, so it reads as the reference and never competes with a series.

**Status**, fixed and never reused for series:

| Token | Light fill | Light text | Dark (fill and text) |
| --- | --- | --- | --- |
| `--color-success` | `#00ae64` | `#007742` | `#00d27a` |
| `--color-warning` | `#fcab00` | `#8d5e00` | `#ffbe3d` |
| `--color-danger` | `#ef0028` | `#bc001d` | `#ff5352` |

`-subtle` backgrounds are the fill at 14 % opacity (`color-mix(in srgb, var(--color-success) 14%, transparent)`). The status-code chart colours 2xx, 4xx and 5xx with these tokens; the latency chart uses series tokens only, so the two never meet in one chart.

**Rules for the palette**

- A series colour follows the endpoint, not its rank: `endpointKey()` maps each method and route to a fixed slot, so filtering or sorting never repaints the survivors.
- More than eight series fold into "Other" rather than generating a new colour.
- Series colours never colour text; labels and values use the text tokens, with a coloured mark beside them.
- Status always comes with a label or icon, never colour alone.

**Validation**, run with an OKLCH lightness, chroma, colour-vision (Machado 2009 protanopia and deuteranopia) and contrast checker:

| Check | Light | Dark | Requirement |
| --- | --- | --- | --- |
| Worst neighbouring pair, colour-blind vision | ΔE 15.9 | ΔE 11.7 | at least 8 |
| Worst neighbouring pair, normal vision | ΔE 24.0 | ΔE 25.3 | at least 15 |
| First three slots, any pair | pass | pass | for charts where any two marks can touch |
| Series vs surface contrast | 5 of 8 below 3:1 | all 8 at least 3:1 | 3:1, or a legend and table view |
| Text, muted text, accent text, status text vs surface | at least 4.5:1 | at least 4.5:1 | 4.5:1 |

Lime, marigold, turquoise, pink and tangerine sit below 3:1 on the cream surface, which is expected for vivid yellows and greens on a light background. Every chart therefore keeps its legend, tooltip and table view; no value is ever shown by a light-mode series colour alone.

### Themes

- The default is the dark theme, the usual choice for a monitoring screen left open for long periods. `ThemeToggle` offers light, dark and system; system follows the operating system through `prefers-color-scheme`.
- `useTheme` sets `data-theme` on `<html>` and remembers every choice in `localStorage`, system included: with nothing stored, the dark default applies. Reads and writes are wrapped, so when storage is blocked the page still works and simply starts dark each visit.
- `tokens.css` defines the light values on `:root`, the dark values under `prefers-color-scheme: dark` (unless `data-theme="light"`), and again under `[data-theme="dark"]`.
- Recharts sets colours through SVG attributes, where CSS variables are not reliably resolved. `useChartColors` reads the resolved token values with `getComputedStyle` and reads them again when the theme changes, so charts use the same palette as the rest of the page.

### Layout

- Mobile first, with `min-width` media queries at two breakpoints: 640 px and 1024 px.
- The page is a CSS grid: one column on phones; from 1024 px, KPIs in four columns, charts in two, tables full width.
- Panels are size containers, and their contents use container queries (`@container`), so a KPI card or chart adapts to the panel's width, not the screen's.
- Tables scroll horizontally inside their panel; the page itself never scrolls sideways.
- Logical properties (`padding-inline`, `margin-block`) throughout.

### Accessibility

- Text meets WCAG AA (4.5:1) in both themes. Chart marks meet 3:1 in dark mode; in light mode the lighter series rely on the legend, tooltip and table view (see the palette validation above).
- Status is never shown by colour alone: a `5xx` also carries a label or icon.
- Every control has a visible `:focus-visible` outline.
- `prefers-reduced-motion` disables transitions and chart animations.

### Rules

- camelCase class names; one module per component.
- No global classes outside `global.css`, no `!important`, no raw colours or pixel spacing outside `tokens.css` (Stylelint enforces the last two).
- Shared patterns are reused with `composes:` rather than copied.
- Stylelint (`stylelint-config-standard` plus a CSS Modules config) runs locally and in CI; Prettier formats CSS.

## Contract and type generation

The backend already builds its OpenAPI schema without a database, so the contract can be exported offline:

1. **Backend:** `make openapi` (in `backend/`) writes `app.openapi()` to `frontend/openapi.json`.
2. **Frontend:** `make api-types` (`npm run generate:api`) runs `openapi-typescript openapi.json -o src/api/schema.gen.ts`.
3. **CI:** Backend CI runs `make openapi-check` and Frontend CI runs `make api-check`. Each regenerates in memory and fails if the committed file differs, so a backend change that alters the contract cannot merge without the frontend seeing it.

Both generated files are committed, so the frontend builds without a running backend. Prettier skips them, so they stay byte-for-byte what the generators write.

### Updating the API contract

After changing a backend route or schema, from `frontend/`:

```bash
make contract   # backend's make openapi, then make api-types: refreshes both files
make check      # type errors show every place the change affects
```

Commit both files with the backend change.

### TypeScript 6 and `openapi-typescript`

`openapi-typescript` 7 declares TypeScript 5 as a peer dependency, and no release supports 6 yet. An `overrides` entry in `package.json` points it at the app's TypeScript instead. It is scoped to that one package, unlike `--legacy-peer-deps`, which would relax peer checks for everything, and it keeps the generator pinned in the lockfile, unlike running it through `npx`. The generator only prints TypeScript through the compiler API, and `check:api` in CI would catch any change in its output. Remove the override once a release supports TypeScript 6.

## Configuration

`VITE_API_URL` sets the backend base URL, so local and deployed environments differ only by configuration. `config.ts` validates it once at startup and fails with a clear message if it is missing or not a URL. It is public: never place secrets in `VITE_*` variables. AI keys live only in the backend.

The Vite dev server runs on port 5173, the backend's default `CORS_ORIGINS` entry, so local development needs no proxy. A router is deliberately left out; the URL query string holds the only state worth sharing, and a router can be added if the dashboard grows beyond one view.

## Development

Requires Node.js 20.19 or later (CI uses 24); every `make` target checks the version first. From `frontend/`:

```bash
make setup   # install dependencies, create .env if missing (points at the local backend)
make run     # http://localhost:5173, with the backend on http://127.0.0.1:8000
```

| Command | Purpose |
| --- | --- |
| `make check` | API-type freshness, ESLint, Stylelint, Prettier, type check and tests, as CI runs them |
| `make test` | Tests once; `make test-watch` reruns them on every save |
| `make build` | Type-check and build the production bundle into `dist/`; `make preview` serves it |
| `make sync` | Install dependencies exactly as locked (`npm ci`); `make install` may update the lockfile |
| `make contract` | Refresh `openapi.json` from the backend, then the generated types |
| `make format` | Format with Prettier |
| `make audit` | Scan dependencies for known vulnerabilities: production strictly, then everything against the reviewed exceptions (see below) |
| `make clean` | Remove build output and tool caches; keeps `.env`, `node_modules` and `package-lock.json` |

Run `make help` for the full list. Each target runs the matching `npm run` script, which also works directly. Frontend CI calls the same targets, so they cannot drift from what CI checks. Stylelint rejects raw colours, pixel spacing, non-camelCase class names and `!important` outside `tokens.css`.

### Dependency audit

`make audit` (and CI) runs two steps:

1. `npm audit --omit=dev` checks what ships to the browser. It allows **no exceptions**.
2. `npm run audit:all` (`scripts/audit.mjs`) checks every dependency, development tools included, and fails on any advisory not listed in `audit-allowlist.json`.

An exception is for an advisory with no fix that cannot affect the app, for example one reached only through a development tool. Each entry needs the advisory's GHSA id, the package, the reason and a `reviewBy` date at most 90 days ahead; once that date passes the audit fails until someone re-checks it. Entries no longer reported are printed as warnings so the list stays short. This follows the rule in `backend/CI.md`: specific identifier, rationale and review date, never a global suppression.

Current exception: `braces` (GHSA-vfj7-8cjw-p6xm), reached only through Stylelint linting our own CSS, with no patched version yet.

## Testing

| Layer | How |
| --- | --- |
| `lib/`, `models/` | Plain Vitest unit tests: formatting edge cases (`null`, `0`, sub-millisecond, over one second), pivoting trends with empty buckets, preset limits |
| `api/` | MSW returns each backend response (success, empty, `422`, `503`, network failure); assert the typed result or the `ApiError` kind |
| `hooks/` | `renderHook` with a test `QueryClient`: query keys, polling on and off, no retry on `4xx`, previous data kept while switching windows |
| `components/` | Testing Library with the typed fixtures: each panel's four states, sorting, keyboard use of the controls |
| `App` | One integration test per fixture: busy, empty and failing backend render the right states end to end |

Fixtures are typed as `MetricsResponse`, so a contract change breaks them at compile time too.

Tests run in the `Asia/Kolkata` time zone (`vite.config.ts`), whatever the machine's zone. The results are the same everywhere, and the half-hour offset shows that times are converted from UTC.

## Build order

Each step is one reviewable pull request that leaves the app working.

| Step | Scope | Done when |
| --- | --- | --- |
| 1. Scaffold | Vite, TypeScript, ESLint, Stylelint, Prettier, Vitest, `config.ts`, `styles/` with light and dark tokens, a `frontend-ci.yml` workflow (install, lint, format, types, tests, build, audit) | CI is green on an empty page |
| 2. Contract | `make openapi`, `openapi.json`, `schema.gen.ts`, `models/`, `api/` with tests, the freshness check in CI | `fetchMetrics` is typed end to end and tested against MSW |
| 3. Pure logic | `lib/` and `models/windows.ts` with unit tests | Formatting and chart pivots are covered, including `null` and empty buckets |
| 4. Data and controls | `hooks/` (including `useTheme`), `controls/`, `feedback/`, `layout/` (including `ThemeToggle`), `App.tsx` | Switching windows and auto-refresh work against the real backend; every state renders |
| 5. KPIs and charts | `kpis/`, `charts/` | Charts match `/metrics` output for a generated traffic run |
| 6. Tables | `tables/` | Sorting, `aria-sort` and narrow-screen scrolling work |
| 7. Polish | Visual check of both themes at phone, tablet and desktop widths, contrast and accessibility pass, README screenshots | Usable at 360 px wide and by keyboard only, AA contrast in both themes |
| 8. AI insights *(later)* | `api/analysis.ts`, `useAnalysis`, `insights/` | Starts once `POST /analyze` exists in the backend |
