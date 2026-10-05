import { describe, expect, it } from 'vitest'
import { compareValues, sortBy, type SortValue } from './sort'

describe('compareValues', () => {
  it.each([
    [1, 2, 'asc', -1],
    [1, 2, 'desc', 1],
    ['GET', 'POST', 'asc', -1],
    [5, 5, 'asc', 0],
  ] as const)('%j vs %j (%s) has the sign of %i', (a, b, direction, sign) => {
    expect(Math.sign(compareValues(a, b, direction))).toBe(sign)
  })

  it('sorts numbers inside text naturally', () => {
    expect(compareValues('/demo/v2', '/demo/v10', 'asc')).toBeLessThan(0)
  })
})

describe('sortBy', () => {
  const rows = [
    { name: 'b', latency: 50 },
    { name: 'empty', latency: null },
    { name: 'a', latency: 10 },
    { name: 'c', latency: 90 },
  ]
  const latency = (row: (typeof rows)[number]): SortValue => row.latency
  const names = (sorted: typeof rows) => sorted.map((row) => row.name)

  it('puts null last in both directions', () => {
    expect(names(sortBy(rows, latency, 'asc'))).toEqual(['a', 'b', 'c', 'empty'])
    expect(names(sortBy(rows, latency, 'desc'))).toEqual(['c', 'b', 'a', 'empty'])
  })

  it('keeps the original order of equal rows', () => {
    const tied = [
      { name: 'first', latency: 1 },
      { name: 'second', latency: 1 },
      { name: 'third', latency: 1 },
    ]
    expect(names(sortBy(tied, latency, 'desc'))).toEqual(['first', 'second', 'third'])
  })

  it('returns a copy and leaves the input unchanged', () => {
    const before = names(rows)
    const sorted = sortBy(rows, latency, 'asc')
    expect(sorted).not.toBe(rows)
    expect(names(rows)).toEqual(before)
  })
})
