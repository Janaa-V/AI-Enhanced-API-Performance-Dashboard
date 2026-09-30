import { describe, expect, it } from 'vitest'
import { assignSeriesSlots } from './series'

describe('assignSeriesSlots', () => {
  it('gives every demo endpoint its fixed slot, whatever the order or subset', () => {
    const all = assignSeriesSlots([
      'GET /demo/reports',
      'GET /demo/users',
      'POST /demo/orders',
      'GET /demo/orders',
    ])
    expect(Object.fromEntries(all)).toEqual({
      'GET /demo/orders': 2,
      'GET /demo/reports': 6,
      'GET /demo/users': 1,
      'POST /demo/orders': 3,
    })
    // Filtering never repaints the survivors.
    expect(assignSeriesSlots(['POST /demo/orders']).get('POST /demo/orders')).toBe(3)
  })

  it('gives unknown endpoints the spare slots in key order, then none', () => {
    const slots = assignSeriesSlots(['GET /c', 'GET /demo/users', 'GET /a', 'GET /b'])
    expect(Object.fromEntries(slots)).toEqual({
      'GET /a': 7,
      'GET /b': 8,
      'GET /c': null,
      'GET /demo/users': 1,
    })
  })
})
