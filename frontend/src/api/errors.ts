import { AxiosError, isAxiosError } from 'axios'
import type { ErrorResponse } from '../models/metrics'

// What went wrong, in terms the UI can act on: retry, wait, point at the backend, or show the
// message.
export type ApiErrorKind =
  'network' | 'timeout' | 'validation' | 'rate_limited' | 'server' | 'unknown'

interface ApiErrorDetails {
  status?: number | undefined
  code?: string | undefined
  retryAfterSeconds?: number | undefined
  cause?: unknown
}

// Every failure the API layer throws. `message` is always safe to show; raw responses never are.
export class ApiError extends Error {
  override readonly name = 'ApiError'
  readonly kind: ApiErrorKind
  // The HTTP status, when the server answered at all.
  readonly status: number | undefined
  // The server's machine-readable code, such as service_unavailable or ai_disabled.
  readonly code: string | undefined
  // From a 429's Retry-After header: how long to wait before trying again, when the server says.
  readonly retryAfterSeconds: number | undefined

  constructor(
    kind: ApiErrorKind,
    message: string,
    { status, code, retryAfterSeconds, cause }: ApiErrorDetails = {},
  ) {
    super(message, { cause })
    this.kind = kind
    this.status = status
    this.code = code
    this.retryAfterSeconds = retryAfterSeconds
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

// The shared { error: { code, message } } body the backend sends for its own errors: every 5xx,
// and 429 from POST /analyze.
function readErrorBody(data: unknown): ErrorResponse['error'] | undefined {
  if (!isRecord(data) || !isRecord(data.error)) return undefined
  const { code, message } = data.error
  return typeof code === 'string' && typeof message === 'string' ? { code, message } : undefined
}

// FastAPI's 422 body: { detail: [{ msg, ... }] }. The first message is the useful one, such as
// the "too many buckets" hint from GET /metrics.
function readValidationMessage(data: unknown): string | undefined {
  if (!isRecord(data) || !Array.isArray(data.detail)) return undefined
  const first: unknown = data.detail[0]
  return isRecord(first) && typeof first.msg === 'string' ? first.msg : undefined
}

// Retry-After is either whole seconds ("30") or an HTTP date. The backend sends seconds; a date
// is accepted too, since a proxy in front of it may answer instead. Undefined when missing or
// unreadable: the UI then lets the user retry at once.
export function parseRetryAfter(value: unknown, now = Date.now()): number | undefined {
  if (typeof value !== 'string' || value.trim() === '') return undefined
  const text = value.trim()
  if (/^\d+$/.test(text)) return Number(text)
  // An HTTP date always ends in GMT. Checked first because Date.parse is lenient: it reads
  // "-5" or "1.5" as dates.
  if (!text.endsWith(' GMT')) return undefined
  const date = Date.parse(text)
  if (Number.isNaN(date)) return undefined
  return Math.max(0, Math.ceil((date - now) / 1000))
}

export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error
  if (!isAxiosError(error)) {
    return new ApiError('unknown', 'Something went wrong while contacting the API.', {
      cause: error,
    })
  }

  const { response } = error
  if (!response) {
    // client.ts sets clarifyTimeoutError, so only a timeout reports ETIMEDOUT.
    if (error.code === AxiosError.ETIMEDOUT) {
      return new ApiError('timeout', 'The API took too long to respond.', { cause: error })
    }
    return new ApiError('network', 'Could not reach the API. Check that the backend is running.', {
      cause: error,
    })
  }

  const { status, data, headers } = response
  if (status === 422) {
    const message = readValidationMessage(data) ?? 'The API rejected the request parameters.'
    return new ApiError('validation', message, { status, cause: error })
  }

  // Any other status may carry the shared body; its code tells apart failures that share a
  // status, such as 503 ai_disabled and 503 service_unavailable.
  const body = readErrorBody(data)
  const details = { status, code: body?.code, cause: error }
  if (status === 429) {
    const message = body?.message ?? 'Too many requests right now; try again later.'
    const retryAfterSeconds = parseRetryAfter(headers['retry-after'])
    return new ApiError('rate_limited', message, { ...details, retryAfterSeconds })
  }
  if (status >= 500) {
    const message = body?.message ?? 'The server could not complete the request.'
    return new ApiError('server', message, details)
  }
  const message = body?.message ?? `Unexpected response from the API (HTTP ${status}).`
  return new ApiError('unknown', message, details)
}
