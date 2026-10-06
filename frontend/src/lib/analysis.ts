// Display text for the analysis contract's fixed values. Typed as Record<Metric, string>, so a
// metric the backend adds later is a compile error here until it has a label.
import type { Confidence, Metric } from '../models/analysis'

export const METRIC_LABELS: Record<Metric, string> = {
  total_requests: 'Requests',
  requests_per_minute: 'Requests per minute',
  error_rate: 'Error rate',
  client_errors: 'Client errors',
  avg_latency_ms: 'Average latency',
  p95_latency_ms: 'p95 latency',
}

// Spelled out, never colour alone. The backend caps confidence at "medium": aggregates cannot
// prove a cause.
export const CONFIDENCE_LABELS: Record<Confidence, string> = {
  low: 'Low confidence',
  medium: 'Medium confidence',
}

// An observation about the whole API has no endpoint.
export function observationScope(endpoint: string | null): string {
  return endpoint ?? 'All endpoints'
}
