import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  use: { baseURL: 'http://127.0.0.1:5180', headless: true },
  webServer: [
    { command: 'node server/mock-server.mjs', url: 'http://127.0.0.1:8000/api/parcels', reuseExistingServer: true, timeout: 15_000 },
    { command: 'npm run dev -- --host 127.0.0.1 --port 5180', url: 'http://127.0.0.1:5180', reuseExistingServer: false, timeout: 15_000 },
  ],
})
