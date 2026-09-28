// axe: zero serious/critical violations on every page in both themes. Runs locally too (bci-queen
// slot) and in CI.
import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { PAGES, collectErrors } from './util';

for (const path of PAGES) {
  test(`axe ${path}`, async ({ page }) => {
    const errors = collectErrors(page);
    await page.goto(path);
    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      .analyze();
    const bad = results.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical');
    expect(bad.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`)).toEqual(
      [],
    );
    expect(errors.filter((e) => !e.includes('404'))).toEqual([]);
  });
}

test('skip link moves focus to main', async ({ page }) => {
  await page.goto('/');
  await page.keyboard.press('Tab');
  await expect(page.locator('.nf-skip')).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.locator('#main')).toBeFocused();
});
