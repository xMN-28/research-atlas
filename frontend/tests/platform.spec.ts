import { test, expect } from '@playwright/test';

test('all seven pages render real analysis without browser errors', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', e => errors.push(e.message));
  for (const [route, heading] of [
    ['/', 'A clearer view of research.'], ['/literature', 'Explore the evidence.'],
    ['/topics', 'From papers to patterns.'], ['/trends', 'Watch ideas evolve.'],
    ['/network', 'Connect the concepts.'], ['/gaps', 'Find your next question.'],
    ['/evaluation', 'Measure before you trust.'],
  ]) {
    await page.goto(route);
    await expect(page.getByRole('heading', { level: 1, name: heading })).toBeVisible();
    await expect(page.getByText('Loading saved research analysis…')).toHaveCount(0);
    await expect(page.getByText('We couldn’t load this analysis')).toHaveCount(0);
    if (route !== '/literature' && route !== '/network') await expect(page.locator('.js-plotly-plot').first()).toBeVisible();
    if (route === '/network') await expect(page.locator('.network-canvas canvas').first()).toBeVisible();
  }
  expect(errors).toEqual([]);
});

test('paper search, filters, modal, pagination and empty state', async ({ page }) => {
  await page.goto('/literature');
  await page.getByRole('textbox', { name: 'Search papers' }).fill('neural');
  await expect(page.getByRole('heading', { name: /papers found/ })).toBeVisible();
  await page.getByRole('combobox', { name: 'Year', exact: true }).selectOption('2020');
  await page.getByLabel('Text coverage').selectOption('title-and-abstract');
  await expect(page.locator('tbody tr').first().locator('td').nth(1)).toHaveText('2020');
  await page.getByLabel('Sort papers').selectOption('relevance');
  await page.locator('.paper-title-button').first().click();
  await expect(page.locator('dialog')).toBeVisible();
  const dialogBounds = await page.locator('dialog').boundingBox();
  const viewport = page.viewportSize()!;
  expect(Math.abs(dialogBounds!.x + dialogBounds!.width / 2 - viewport.width / 2)).toBeLessThan(2);
  expect(Math.abs(dialogBounds!.y + dialogBounds!.height / 2 - viewport.height / 2)).toBeLessThan(2);
  await expect(page.getByRole('link', { name: 'View in OpenAlex' })).toHaveAttribute('href', /https:\/\/openalex.org\/W\d+/);
  await page.getByRole('button', { name: 'Close paper details' }).click();
  await page.getByRole('button', { name: 'Reset filters' }).click();
  await page.getByRole('button', { name: 'Next', exact: true }).click();
  await expect(page.getByText('Page 2', { exact: true })).toBeVisible();
  await page.getByRole('textbox', { name: 'Search papers' }).fill('zzzxxyynonexistent');
  await expect(page.getByRole('heading', { name: 'No matching papers' })).toBeVisible();
  await page.getByRole('button', { name: 'Clear filters' }).click();
  await expect(page.locator('tbody tr').first()).toBeVisible();
});

test('topic models, temporal filters, graph evidence and gap evidence', async ({ page }) => {
  await page.goto('/topics');
  await page.getByRole('button', { name: 'LDA', exact: true }).click();
  await expect(page.getByText('Term counts · probabilistic topic mixtures')).toBeVisible();
  await page.locator('.topic-card').nth(2).click();
  await expect(page.locator('.paper-list .paper-row').first()).toBeVisible();
  await page.goto('/trends');
  await page.getByLabel('Trend topic').selectOption('0');
  await page.getByRole('combobox', { name: 'From', exact: true }).selectOption('2020');
  await page.getByLabel('Abstract-bearing only').check();
  await expect(page.getByText(/abstract-bearing records/).first()).toBeVisible();
  await expect(page.locator('.js-plotly-plot').first()).toBeVisible();
  await page.goto('/network');
  await page.getByLabel('Select concept').selectOption('t5');
  await expect(page.locator('.concept-stat strong')).toBeVisible();
  await page.getByRole('button', { name: 'Zoom in' }).click();
  await page.getByRole('button', { name: 'Fit graph' }).click();
  await page.getByLabel('Minimum shared papers').focus();
  await page.getByLabel('Minimum shared papers').press('End');
  await expect(page.getByText('500', { exact: true })).toBeVisible();
  await expect(page.locator('.paper-row').first()).toBeVisible();
  await page.goto('/gaps');
  await page.locator('.gap-candidate').nth(1).click();
  await expect(page.locator('.gap-stat-grid')).toBeVisible();
  await expect(page.getByText('Existing intersection papers · counter-evidence', { exact: false })).toBeVisible();
  await page.locator('details').nth(1).locator('summary').click();
  await expect(page.locator('details').nth(1).locator('.paper-row').first()).toBeVisible();
  await page.locator('details').nth(1).locator('.paper-row').first().click();
  await expect(page.locator('dialog')).toBeVisible();
});

test('theme persistence, export, mobile navigation and screenshots', async ({ page }) => {
  await page.goto('/evaluation');
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export results' }).click();
  expect((await download).suggestedFilename()).toBe('research-atlas-evaluation.json');
  await page.getByRole('button', { name: 'Dark appearance' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await expect(page.locator('.js-plotly-plot').first()).toBeVisible();
  await expect(page.locator('.page-title')).toHaveCSS('opacity', '1');
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: '../verification/evaluation-dark.png', fullPage: true });
  await page.getByRole('button', { name: 'Light appearance' }).click();
  await page.goto('/');
  await expect(page.locator('.js-plotly-plot').first()).toBeVisible();
  await expect(page.locator('.page-title')).toHaveCSS('opacity', '1');
  await page.screenshot({ path: '../verification/dashboard.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('button', { name: 'Open navigation' }).click();
  await page.getByRole('link', { name: 'Literature explorer', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Explore the evidence.' })).toBeVisible();
  const widths = await page.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
  expect(widths[0]).toBeLessThanOrEqual(widths[1]);
  await expect(page.locator('tbody tr').first()).toBeVisible();
  await expect(page.locator('.page-title')).toHaveCSS('opacity', '1');
  await page.screenshot({ path: '../verification/mobile-literature.png', fullPage: false });
});

test('backend failures produce a recoverable error state', async ({ page }) => {
  await page.route('**/api/overview', route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Temporary test outage' }) }));
  await page.goto('/');
  await expect(page.getByText('Temporary test outage')).toBeVisible();
  await page.unroute('**/api/overview');
  await page.getByRole('button', { name: 'Try again' }).click();
  await expect(page.getByText('10,000', { exact: true })).toBeVisible();
});
