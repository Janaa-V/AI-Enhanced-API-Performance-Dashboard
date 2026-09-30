// Readable names for the generated API types. The rest of the app imports from here, never from
// schema.gen.ts, so regenerating the schema never ripples through components.
// Units follow the backend: latency in milliseconds, rates as fractions from 0 to 1, timestamps
// as UTC ISO strings, and null (never 0) when a window has nothing to measure.

import type { components, paths } from '../api/schema.gen'

type Schemas = components['schemas']

export type MetricsResponse = Schemas['MetricsResponse']
export type MetricsWindow = Schemas['MetricsWindow']
export type Summary = Schemas['Summary']
export type EndpointMetrics = Schemas['EndpointMetrics']
export type StatusCodeCount = Schemas['StatusCodeCount']
export type LatencyTrend = Schemas['LatencyTrend']
export type EndpointTrend = Schemas['EndpointTrend']
export type TrendBucket = Schemas['TrendBucket']
export type RecentRequest = Schemas['RecentRequest']

// Error bodies: the shared { error: { code, message } } shape, and FastAPI's 422.
export type ErrorResponse = Schemas['ErrorResponse']
export type ValidationErrorResponse = Schemas['HTTPValidationError']

// The query string GET /metrics accepts, in the backend's snake_case.
export type MetricsQuery = NonNullable<paths['/metrics']['get']['parameters']['query']>
