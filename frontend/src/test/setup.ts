// Runs before every test file (vite.config.ts, test.setupFiles).
import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterAll, afterEach, beforeAll } from 'vitest'
import { server } from './server'

// A request with no handler fails the test instead of silently reaching the network.
beforeAll(() => {
  server.listen({ onUnhandledRequest: 'error' })
})

afterEach(() => {
  // Testing Library cleans up by itself only when Vitest globals are on; they are off here.
  cleanup()
  // Undo any server.use() from the test, back to the default success handler.
  server.resetHandlers()
})

afterAll(() => {
  server.close()
})
