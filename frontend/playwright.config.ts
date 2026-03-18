import { defineConfig, devices } from '@playwright/test'

/**
 * Playwright E2E configuration for Voice In The Dark.
 *
 * Requires the Django dev server (port 8000) and Vite dev server (port 5173)
 * to be running. Start them with:
 *   python manage.py runserver  (from project root)
 *   npm run dev                 (from frontend/)
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})
