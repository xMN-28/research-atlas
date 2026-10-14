import { chromium } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';

const output = path.resolve('../docs/screenshots');
await mkdir(output, { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
const errors = [];
page.on('pageerror', e => errors.push(e.message));
async function ready(route, chart = true) {
  await page.goto(`http://127.0.0.1:3000${route}`);
  await page.locator('.page-title').waitFor();
  await page.waitForFunction(() => getComputedStyle(document.querySelector('.page-title')).opacity === '1');
  await page.evaluate(() => document.fonts.ready);
  if (chart) await page.locator('.js-plotly-plot').first().waitFor();
  else if (route === '/network') await page.locator('.network-canvas canvas').first().waitFor();
  else await page.locator('tbody tr').first().waitFor();
}
async function capture(name, fullPage = false) {
  await page.screenshot({ path: path.join(output, `${name}.png`), fullPage });
  console.log(`Saved ${name}.png`);
}
for (const [route, name, chart] of [
  ['/', 'dashboard', true], ['/literature', 'literature-explorer', false],
  ['/topics', 'topics-nmf', true], ['/trends', 'research-trends', true],
  ['/network', 'concept-network', false], ['/gaps', 'research-gaps', true],
  ['/evaluation', 'model-evaluation', true],
]) {
  await ready(route, chart);
  await capture(name);
}
await ready('/topics');
await Promise.all([
  page.waitForResponse(r => r.url().includes('/api/topics/0?model=lda') && r.status() === 200),
  page.getByRole('button', { name: 'LDA', exact: true }).click(),
]);
await page.getByText('Term counts · probabilistic topic mixtures').waitFor();
await page.locator('.js-plotly-plot').first().waitFor();
await capture('topics-lda');
await ready('/literature', false);
await Promise.all([
  page.waitForResponse(r => r.url().includes('source=title-and-abstract') && r.status() === 200),
  page.getByLabel('Text coverage').selectOption('title-and-abstract'),
]);
await page.locator('.paper-title-button').first().click();
await page.locator('dialog').waitFor();
const rect = await page.locator('dialog').boundingBox();
if (Math.abs(rect.x + rect.width / 2 - 720) > 2 || Math.abs(rect.y + rect.height / 2 - 500) > 2) throw new Error('Paper dialog is not centered');
await capture('paper-details');
await page.getByRole('button', { name: 'Close paper details' }).click();
await Promise.all([
  page.waitForResponse(r => r.url().includes('source=title-only') && r.status() === 200),
  page.getByLabel('Text coverage').selectOption('title-only'),
]);
await page.locator('.paper-title-button').first().click();
await page.locator('dialog').waitFor();
await capture('paper-title-only');
await page.getByRole('button', { name: 'Close paper details' }).click();
await ready('/evaluation');
await page.getByRole('button', { name: 'Dark appearance' }).click();
await page.waitForFunction(() => document.documentElement.dataset.theme === 'dark');
await capture('dark-evaluation');
await page.getByRole('button', { name: 'Light appearance' }).click();
await page.setViewportSize({ width: 390, height: 844 });
await ready('/', true);
await capture('mobile-dashboard');
await browser.close();
if (errors.length) throw new Error(errors.join('\n'));
console.log('All screenshots captured; centered modal geometry verified.');
