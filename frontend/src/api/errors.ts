import { AxiosError, isAxiosError } from 'axios'
import type { ErrorResponse } from '../models/metrics'

// What went wrong, in terms the UI can act on: retry, point at the backend, or show the message.
export type ApiErrorKind = 'network' | 'timeout' | 'validation' | 'server' | 'unknown'

interface ApiErrorDetails {
  status?: number
  code?: string
  cause?: unknown
}

// Every failure the API layer throws. `message` is always safe to show; raw responses never are.
export class ApiError extends Error {
  override readonly name = 'ApiError'
  readonly kind: ApiErrorKind
  // The HTTP status, when the server answered at all.
  readonly status: number | undefined
  // The server's machine-readable code, such as service_unavailable.
  readonly code: string | undefined

  constructor(kind: ApiErrorKind, message: string, { status, code, cause }: ApiErrorDetails = {}) {
    super(message, { cause })
    this.kind = kind
    this.status = status
    this.code = code
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

// The shared { error: { code, message } } body the backend sends for 5xx responses.
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

  const { status, data } = response
  if (status === 422) {
    const message = readValidationMessage(data) ?? 'The API rejected the request parameters.'
    return new ApiError('validation', message, { status, cause: error })
  }
  if (status >= 500) {
    const body = readErrorBody(data)
    const message = body?.message ?? 'The server could not complete the request.'
    return new ApiError('server', message, { status, code: body?.code, cause: error })
  }
  return new ApiError('unknown', `Unexpected response from the API (HTTP ${status}).`, {
    status,
    cause: error,
  })
}
