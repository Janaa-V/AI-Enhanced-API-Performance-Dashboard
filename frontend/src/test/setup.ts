// Runs before every test file (vite.config.ts, test.setupFiles).
import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// Testing Library cleans up by itself only when Vitest globals are on; they are off here.
afterEach(() => {
  cleanup()
})
