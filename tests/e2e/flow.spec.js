import { test, expect } from '@playwright/test'

test('live contract server upload to geometry explanation', async ({ page }) => {
  await page.goto('/')
  await page.locator('input[type="file"]').setInputFiles('index.html')
  await page.getByRole('button', { name: /Process/ }).click()
  await expect(page.getByText('Reconciliation pipeline')).toBeVisible()
  await expect(page.getByText('Conflict Queue')).toBeVisible({ timeout: 8_000 })
  await page.getByRole('button', { name: /1042 HIGH/ }).click()
  await expect(page.locator('.detail-panel').getByText('Boundary shift detected').first()).toBeVisible()
  await expect(page.getByText(/24 m² boundary mismatch/)).toBeVisible()
  await page.getByRole('button', { name: 'Drone/ORI' }).click()
  await expect(page.locator('.leaflet-overlay-pane path[stroke-dasharray="8 8"]')).toHaveCount(1)
})

test('live server load and filter at 120 parcels', async ({ page }) => {
  await page.goto('/')
  await page.locator('input[type="file"]').setInputFiles('tests/fixtures/load-120.txt')
  await page.getByRole('button', { name: /Process/ }).click()
  await expect(page.getByText('Conflict Queue')).toBeVisible({ timeout: 8_000 })
  await expect(page.locator('.summary-total')).toContainText('120')
  const before = await page.getByRole('heading', { name: /Conflict Queue/ }).innerText()
  await page.getByRole('combobox', { name: 'Filter by priority' }).selectOption('HIGH')
  const after = await page.getByRole('heading', { name: /Conflict Queue/ }).innerText()
  expect(Number(after.match(/\d+/)?.[0])).toBeLessThan(Number(before.match(/\d+/)?.[0]))
})
