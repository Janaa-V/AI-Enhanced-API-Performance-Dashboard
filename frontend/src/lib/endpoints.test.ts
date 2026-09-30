import { expect, it } from 'vitest'
import { endpointKey } from './endpoints'

it('keeps GET and POST on the same route apart', () => {
  const get = endpointKey({ method: 'GET', endpoint: '/demo/orders' })
  const post = endpointKey({ method: 'POST', endpoint: '/demo/orders' })
  expect(get).toBe('GET /demo/orders')
  expect(post).toBe('POST /demo/orders')
})
