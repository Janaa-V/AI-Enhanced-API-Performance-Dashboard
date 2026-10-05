// A fake backend for tests (Mock Service Worker). It answers at the network level, so the real
// Axios client, interceptors and error handling all run. Tests switch answers with server.use().
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { API_URL } from '../config'
import type { ErrorResponse, MetricsResponse, ValidationErrorResponse } from '../models/metrics'
import { busyMetrics, emptyMetrics } from './fixtures/metrics'

export const METRICS_URL = `${API_URL}/metrics`

export const metricsHandlers = {
  success: http.get(METRICS_URL, () => HttpResponse.json<MetricsResponse>(busyMetrics)),
  empty: http.get(METRICS_URL, () => HttpResponse.json<MetricsResponse>(emptyMetrics)),
  // The body the backend sends when window_minutes / bucket_minutes exceeds 288.
  validationError: http.get(METRICS_URL, () =>
    HttpResponse.json<ValidationErrorResponse>(
      {
        detail: [
          {
            type: 'value_error',
            loc: ['query', 'bucket_minutes'],
            msg: 'Too many buckets: window_minutes / bucket_minutes must be at most 288; use bucket_minutes of at least 5.',
            input: 1,
          },
        ],
      },
      { status: 422 },
    ),
  ),
  unavailable: http.get(METRICS_URL, () =>
    HttpResponse.json<ErrorResponse>(
      {
        error: {
          code: 'service_unavailable',
          message: 'The service is temporarily unavailable.',
        },
      },
      { status: 503 },
    ),
  ),
  // The backend is down or unreachable: no response at all.
  networkError: http.get(METRICS_URL, () => HttpResponse.error()),
}

export const server = setupServer(metricsHandlers.success)
