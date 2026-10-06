// A fake backend for tests (Mock Service Worker). It answers at the network level, so the real
// Axios client, interceptors and error handling all run. Tests switch answers with server.use().
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { API_URL } from '../config'
import type { AnalysisResponse } from '../models/analysis'
import type { ErrorResponse, MetricsResponse, ValidationErrorResponse } from '../models/metrics'
import { noDataAnalysis, okAnalysis } from './fixtures/analysis'
import { busyMetrics, emptyMetrics } from './fixtures/metrics'

export const METRICS_URL = `${API_URL}/metrics`
export const ANALYZE_URL = `${API_URL}/analyze`

function errorBody(status: number, code: string, message: string, headers?: HeadersInit) {
  return HttpResponse.json<ErrorResponse>({ error: { code, message } }, { status, headers })
}

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

// The answers POST /analyze gives, with the backend's codes and messages.
export const analysisHandlers = {
  success: http.post(ANALYZE_URL, () => HttpResponse.json<AnalysisResponse>(okAnalysis)),
  noData: http.post(ANALYZE_URL, () => HttpResponse.json<AnalysisResponse>(noDataAnalysis)),
  disabled: http.post(ANALYZE_URL, () =>
    errorBody(503, 'ai_disabled', 'AI analysis is not configured on this server.'),
  ),
  rateLimited: http.post(ANALYZE_URL, () =>
    errorBody(429, 'rate_limited', 'Too many analyses right now; try again later.', {
      'Retry-After': '30',
    }),
  ),
  unavailable: http.post(ANALYZE_URL, () =>
    errorBody(502, 'ai_unavailable', 'The AI provider could not produce an analysis; try again.'),
  ),
  networkError: http.post(ANALYZE_URL, () => HttpResponse.error()),
}

export const server = setupServer(metricsHandlers.success, analysisHandlers.success)
