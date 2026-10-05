import { describe, expect, it } from 'vitest'
import { ApiError, type ApiErrorKind } from '../api/errors'
import { shouldRetry } from './queryClient'

describe('shouldRetry', () => {
  it.each<[ApiErrorKind, boolean]>([
    ['network', true],
    ['timeout', true],
    ['server', true],
    ['validation', false],
    ['unknown', false],
  ])('retries a %s error: %s', (kind, expected) => {
    expect(shouldRetry(0, new ApiError(kind, 'failed'))).toBe(expected)
  })

  it('gives up after two retries', () => {
    const error = new ApiError('server', 'failed')
    expect(shouldRetry(1, error)).toBe(true)
    expect(shouldRetry(2, error)).toBe(false)
  })

  it('never retries an error the API layer did not produce', () => {
    expect(shouldRetry(0, new TypeError('bug'))).toBe(false)
  })
})
