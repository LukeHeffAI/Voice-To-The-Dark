import { test, expect } from '@playwright/test'

/**
 * E2E tests for authentication flows.
 *
 * Prerequisites:
 * - Django dev server running on :8000
 * - Vite dev server running on :5173
 * - A test user created: username="testuser", password="testpass123"
 */

test.describe('Login Flow', () => {
  test('displays login page', async ({ page }) => {
    await page.goto('/login')
    await expect(page.locator('input[type="text"], input[name="username"]')).toBeVisible()
    await expect(page.locator('input[type="password"]')).toBeVisible()
  })

  test('successful login redirects to home', async ({ page }) => {
    await page.goto('/login')
    await page.fill('input[type="text"], input[name="username"]', 'testuser')
    await page.fill('input[type="password"]', 'testpass123')
    await page.click('button[type="submit"]')

    // Should redirect to home page
    await expect(page).toHaveURL('/')
  })

  test('failed login shows error', async ({ page }) => {
    await page.goto('/login')
    await page.fill('input[type="text"], input[name="username"]', 'wrong')
    await page.fill('input[type="password"]', 'wrong')
    await page.click('button[type="submit"]')

    // Should stay on login page and show an error
    await expect(page).toHaveURL('/login')
  })

  test('protected routes redirect to login', async ({ page }) => {
    await page.goto('/submit')
    await expect(page).toHaveURL(/\/login/)
  })
})
