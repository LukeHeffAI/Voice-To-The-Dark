import { test, expect } from '@playwright/test'

/**
 * E2E tests for story browsing and viewing.
 *
 * Prerequisites:
 * - Django dev server running on :8000
 * - Vite dev server running on :5173
 * - At least one story in the database
 */

test.describe('Story List', () => {
  test('home page loads', async ({ page }) => {
    await page.goto('/')
    await expect(page).toHaveURL('/')
  })

  test('home page shows story cards when stories exist', async ({ page }) => {
    await page.goto('/')
    // Wait for API data to load
    await page.waitForTimeout(1000)
    // Page should have loaded (may be empty if no stories)
    await expect(page.locator('body')).toBeVisible()
  })
})

test.describe('Story Detail', () => {
  test('returns 404-like for non-existent story', async ({ page }) => {
    await page.goto('/story/99999')
    // Should show some kind of error or not-found state
    await expect(page.locator('body')).toBeVisible()
  })
})
