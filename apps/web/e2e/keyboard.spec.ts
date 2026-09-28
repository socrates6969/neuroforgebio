// Keyboard tests: audience tabs (ARIA tabs), mobile menu, figure readouts. Runs locally too
// (bci-queen slot) and in CI.
import { expect, test } from '@playwright/test';

test('audience tabs: arrows, Home/End, one panel visible', async ({ page }) => {
  await page.goto('/');
  const tabs = page.locator('#audience [role="tab"]');
  await expect(tabs).toHaveCount(2);
  await tabs.first().focus();
  await expect(tabs.first()).toHaveAttribute('aria-selected', 'true');
  await page.keyboard.press('ArrowRight');
  await expect(tabs.nth(1)).toBeFocused();
  await expect(tabs.nth(1)).toHaveAttribute('aria-selected', 'true');
  await expect(tabs.first()).toHaveAttribute('tabindex', '-1');
  await expect(page.locator('#audience [role="tabpanel"]:visible')).toHaveCount(1);
  await page.keyboard.press('ArrowRight'); // wraps
  await expect(tabs.first()).toBeFocused();
  await page.keyboard.press('End');
  await expect(tabs.nth(1)).toBeFocused();
  await page.keyboard.press('Home');
  await expect(tabs.first()).toBeFocused();
});

test('mobile menu: toggle, Escape closes and returns focus', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto('/');
  const btn = page.locator('.menu-btn');
  const list = page.locator('#nf-navlist');
  await expect(btn).toBeVisible();
  await expect(list).toBeHidden();
  await btn.focus();
  await page.keyboard.press('Enter');
  await expect(btn).toHaveAttribute('aria-expanded', 'true');
  await expect(list).toBeVisible();
  await page.keyboard.press('Tab');
  await expect(list.locator('a').first()).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(btn).toHaveAttribute('aria-expanded', 'false');
  await expect(btn).toBeFocused();
  await expect(list).toBeHidden();
});

test('figure: keyboard readout', async ({ page }) => {
  await page.goto('/research/somatosensory-closed-loop/');
  const fig = page.locator('[data-nf-fig]').first();
  await fig.focus();
  await page.keyboard.press('ArrowRight');
  const out = fig.locator('[data-readout-out]');
  await expect(out).toBeVisible();
  await expect(out).not.toBeEmpty();
  const first = await out.textContent();
  await page.keyboard.press('ArrowRight');
  await expect(out).not.toHaveText(first ?? '');
});

test('figures render as SVG with JS disabled', async ({ browser }, info) => {
  const ctx = await browser.newContext({
    javaScriptEnabled: false,
    baseURL: info.project.use.baseURL,
  });
  const page = await ctx.newPage();
  await page.goto('/research/somatosensory-closed-loop/');
  const svgs = page.locator('svg.nf-plot-svg[role="img"]');
  expect(await svgs.count()).toBeGreaterThan(0);
  await expect(svgs.first()).toBeVisible();
  await ctx.close();
});
