import { AxiosError, AxiosHeaders, type AxiosResponse } from 'axios'
import { describe, expect, it } from 'vitest'
import { ApiError, toApiError } from './errors'

const config = { headers: new AxiosHeaders() }

function responseError(status: number, data: unknown): AxiosError {
  const response: AxiosResponse = { status, statusText: '', data, headers: {}, config }
  return new AxiosError(`HTTP ${status}`, AxiosError.ERR_BAD_RESPONSE, config, {}, response)
}

describe('toApiError', () => {
  it('returns an ApiError unchanged', () => {
    const error = new ApiError('server', 'Already converted.')
    expect(toApiError(error)).toBe(error)
  })

  it('treats a non-Axios error as unknown and keeps it as the cause', () => {
    const cause = new TypeError('boom')
    const error = toApiError(cause)
    expect(error).toMatchObject({ kind: 'unknown', status: undefined, cause })
    expect(error.message).not.toContain('boom')
  })

  it('reports a timeout', () => {
    const error = toApiError(new AxiosError('timeout of 10000ms exceeded', AxiosError.ETIMEDOUT))
    expect(error).toMatchObject({ kind: 'timeout', status: undefined })
  })

  it.each([AxiosError.ERR_NETWORK, AxiosError.ECONNABORTED])(
    'reports %s without a response as a network error',
    (code) => {
      expect(toApiError(new AxiosError('failed', code)).kind).toBe('network')
    },
  )

  it('keeps the first validation message from a 422', () => {
    const error = toApiError(
      responseError(422, {
        detail: [
          { loc: ['query', 'bucket_minutes'], msg: 'Too many buckets.', type: 'value_error' },
          { loc: ['query', 'recent_limit'], msg: 'Second message.', type: 'value_error' },
        ],
      }),
    )
    expect(error).toMatchObject({ kind: 'validation', status: 422, message: 'Too many buckets.' })
  })

  it.each([undefined, 'Unprocessable', { detail: [] }, { detail: [{ msg: 42 }] }])(
    'falls back to a generic message for a malformed 422 body: %j',
    (data) => {
      expect(toApiError(responseError(422, data))).toMatchObject({
        kind: 'validation',
        message: 'The API rejected the request parameters.',
      })
    },
  )

  it("uses the server's code and message for a 5xx", () => {
    const error = toApiError(
      responseError(503, {
        error: { code: 'service_unavailable', message: 'The service is temporarily unavailable.' },
      }),
    )
    expect(error).toMatchObject({
      kind: 'server',
      status: 503,
      code: 'service_unavailable',
      message: 'The service is temporarily unavailable.',
    })
  })

  it.each([undefined, '<html>Bad Gateway</html>', { error: 'oops' }, { error: { code: 1 } }])(
    'never shows a malformed 5xx body: %j',
    (data) => {
      expect(toApiError(responseError(502, data))).toMatchObject({
        kind: 'server',
        status: 502,
        code: undefined,
        message: 'The server could not complete the request.',
      })
    },
  )

  it('reports other statuses as unknown, with the status', () => {
    expect(toApiError(responseError(404, { detail: 'Not Found' }))).toMatchObject({
      kind: 'unknown',
      status: 404,
      message: 'Unexpected response from the API (HTTP 404).',
    })
  })
})
