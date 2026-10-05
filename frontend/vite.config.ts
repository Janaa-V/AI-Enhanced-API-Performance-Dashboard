import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react()],
  // The backend's default CORS_ORIGINS allows only this port, so fail instead of moving to another.
  server: { port: 5173, strictPort: true },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    env: {
      // Tests never reach a real backend; this only satisfies config.ts.
      VITE_API_URL: 'http://api.test',
      // A fixed zone, with a half-hour offset and no daylight saving, so time formatting gives
      // the same result on every machine and shows the UTC-to-local conversion.
      TZ: 'Asia/Kolkata',
    },
    restoreMocks: true,
    unstubEnvs: true,
  },
})
