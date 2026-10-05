import { describe, expect, it } from 'vitest'
import { parseApiUrl } from './config'

describe('parseApiUrl', () => {
  it('accepts an http URL and drops the trailing slash', () => {
    expect(parseApiUrl('http://127.0.0.1:8000/')).toBe('http://127.0.0.1:8000')
  })

  it('keeps a path prefix', () => {
    expect(parseApiUrl('https://example.com/api/')).toBe('https://example.com/api')
  })

  it.each([undefined, ''])('rejects a missing value (%j)', (raw) => {
    expect(() => parseApiUrl(raw)).toThrow('VITE_API_URL is not set')
  })

  it('rejects text that is not a URL', () => {
    expect(() => parseApiUrl('not a url')).toThrow('not a valid URL')
  })

  // "localhost:8000" parses as a URL whose scheme is "localhost:", so it needs this check.
  it.each(['localhost:8000', 'ftp://example.com'])('rejects a non-http URL (%s)', (raw) => {
    expect(() => parseApiUrl(raw)).toThrow('must start with http')
  })
})
