import { test, expect } from '@playwright/test'

/**
 * E2E tests for story submission flow.
 *
 * Prerequisites:
 * - Django dev server running on :8000
 * - Vite dev server running on :5173
 * - A test user created and logged in
 */

// Helper to log in before tests
async function login(page: import('@playwright/test').Page) {
  await page.goto('/login')
  await page.fill('input[type="text"], input[name="username"]', 'testuser')
  await page.fill('input[type="password"]', 'testpass123')
  await page.click('button[type="submit"]')
  await page.waitForURL('/')
}

test.describe('Submit Page', () => {
  test('requires authentication', async ({ page }) => {
    await page.goto('/submit')
    await expect(page).toHaveURL(/\/login/)
  })

  test('loads submit page when authenticated', async ({ page }) => {
    await login(page)
    await page.goto('/submit')
    await expect(page).toHaveURL('/submit')
  })
})
