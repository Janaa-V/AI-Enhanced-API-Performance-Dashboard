import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react()],
  // The backend's default CORS_ORIGINS allows only this port, so fail instead of moving to another.
  server: { port: 5173, strictPort: true },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    // Tests never reach a real backend; this only satisfies config.ts.
    env: { VITE_API_URL: 'http://api.test' },
    restoreMocks: true,
    unstubEnvs: true,
  },
})
