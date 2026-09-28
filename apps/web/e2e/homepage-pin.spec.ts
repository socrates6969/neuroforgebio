// Homepage-unchanged pin (WEB-PLAN.md hard rule 1): nobody may alter built `/`. This snapshots the
// *visible text* of #main on the home page per theme, not pixels, so it is stable across OS/font
// rendering and works the same locally and in CI (unlike visual.spec.ts's screenshot diffs).
// First run writes e2e/__snapshots__/<theme>/<platform>/homepage-pin.spec.ts/home-content.txt;
// generate it only via scripts/homepage-pin-baseline.mjs --init (first time) or --owner-approved (a
// later, owner-approved change), never by hand, and commit with origin/main's sha in the message.
// A failure here means the homepage content changed -- that needs web-queen + the lead, not a fix here.
import { expect, test } from '@playwright/test';

test('home page visible text is unchanged', async ({ page }) => {
  await page.goto('/');
  const text = await page.locator('#main').innerText();
  expect(text).toMatchSnapshot('home-content.txt');
});

test('home page <title> and meta description are unchanged', async ({ page }) => {
  await page.goto('/');
  const title = await page.title();
  const description = await page.locator('meta[name="description"]').getAttribute('content');
  expect(`${title}\n${description}`).toMatchSnapshot('home-meta.txt');
});
